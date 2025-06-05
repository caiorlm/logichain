"""
LogiChain Offline Mesh Validator
Handles offline contract validation and LoRa mesh networking
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from ..crypto.keys import sign_message, verify_signature
from ..storage.database import BlockchainDB
from ..core.blockchain import Blockchain
from .hybrid_manager import HybridMeshManager
from .mesh_logger import MeshLogger

logger = logging.getLogger(__name__)

class ContractStatus(Enum):
    """Contract validation status"""
    PENDING = "pending"
    HANDSHAKE = "handshake"
    VALIDATED = "validated"
    INVALID = "invalid"
    PENALIZED = "penalized"

@dataclass
class ContractSnapshot:
    """Contract state snapshot"""
    timestamp: int
    location: Optional[str]
    data_hash: str
    signature: str
    node_id: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp,
            "location": self.location,
            "data_hash": self.data_hash,
            "signature": self.signature,
            "node_id": self.node_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ContractSnapshot":
        """Create from dictionary"""
        return cls(**data)

@dataclass
class MeshContract:
    """Offline mesh contract"""
    contract_id: str
    genesis_hash: str
    value: float
    snapshot_a: ContractSnapshot
    snapshot_b: Optional[ContractSnapshot]
    status: ContractStatus
    penalties: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "contract_id": self.contract_id,
            "genesis_hash": self.genesis_hash,
            "value": self.value,
            "snapshot_a": self.snapshot_a.to_dict(),
            "snapshot_b": self.snapshot_b.to_dict() if self.snapshot_b else None,
            "status": self.status.value,
            "penalties": self.penalties
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MeshContract":
        """Create from dictionary"""
        return cls(
            contract_id=data["contract_id"],
            genesis_hash=data["genesis_hash"],
            value=data["value"],
            snapshot_a=ContractSnapshot.from_dict(data["snapshot_a"]),
            snapshot_b=ContractSnapshot.from_dict(data["snapshot_b"]) if data["snapshot_b"] else None,
            status=ContractStatus(data["status"]),
            penalties=data["penalties"]
        )

class OfflineMeshValidator:
    """Validates contracts in offline mesh network"""
    
    def __init__(
        self,
        db: BlockchainDB,
        node_id: str,
        private_key: str,
        contracts_dir: str = "offline_contracts"
    ):
        self.db = db
        self.node_id = node_id
        self.private_key = private_key
        self.contracts_dir = contracts_dir
        self.pending_contracts: Dict[str, MeshContract] = {}
        
    def broadcast_handshake(
        self,
        contract_id: str,
        value: float,
        location: Optional[str] = None
    ) -> Tuple[str, ContractSnapshot]:
        """Initiate contract handshake"""
        # Create genesis hash
        timestamp = int(time.time())
        data = f"{contract_id}:{value}:{timestamp}"
        genesis_hash = hashlib.sha256(data.encode()).hexdigest()
        
        # Create snapshot
        data_hash = hashlib.sha256(
            f"{genesis_hash}:{location}:{timestamp}".encode()
        ).hexdigest()
        
        signature = sign_message(data_hash, self.private_key)
        
        snapshot = ContractSnapshot(
            timestamp=timestamp,
            location=location,
            data_hash=data_hash,
            signature=signature,
            node_id=self.node_id
        )
        
        # Create contract
        contract = MeshContract(
            contract_id=contract_id,
            genesis_hash=genesis_hash,
            value=value,
            snapshot_a=snapshot,
            snapshot_b=None,
            status=ContractStatus.PENDING,
            penalties=[]
        )
        
        # Store pending contract
        self.pending_contracts[contract_id] = contract
        self._save_contract(contract)
        
        return genesis_hash, snapshot
        
    def receive_handshake(
        self,
        contract_id: str,
        genesis_hash: str,
        snapshot_a: ContractSnapshot,
        value: float,
        location: Optional[str] = None
    ) -> ContractSnapshot:
        """Receive and validate handshake"""
        # Verify snapshot A
        if not self._verify_snapshot(snapshot_a, genesis_hash):
            raise ValueError("Invalid snapshot A")
            
        # Create snapshot B
        timestamp = int(time.time())
        data_hash = hashlib.sha256(
            f"{genesis_hash}:{location}:{timestamp}".encode()
        ).hexdigest()
        
        signature = sign_message(data_hash, self.private_key)
        
        snapshot_b = ContractSnapshot(
            timestamp=timestamp,
            location=location,
            data_hash=data_hash,
            signature=signature,
            node_id=self.node_id
        )
        
        # Create contract
        contract = MeshContract(
            contract_id=contract_id,
            genesis_hash=genesis_hash,
            value=value,
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            status=ContractStatus.HANDSHAKE,
            penalties=[]
        )
        
        # Store contract
        self.pending_contracts[contract_id] = contract
        self._save_contract(contract)
        
        return snapshot_b
        
    def validate_snapshot_pair(
        self,
        contract_id: str,
        snapshot_b: ContractSnapshot
    ) -> bool:
        """Validate snapshot pair"""
        contract = self.pending_contracts.get(contract_id)
        if not contract:
            raise ValueError("Contract not found")
            
        # Verify snapshot B
        if not self._verify_snapshot(snapshot_b, contract.genesis_hash):
            return False
            
        # Update contract
        contract.snapshot_b = snapshot_b
        contract.status = ContractStatus.VALIDATED
        self._save_contract(contract)
        
        return True
        
    def finalize_contract_if_valid(
        self,
        contract_id: str
    ) -> bool:
        """Finalize contract if valid"""
        contract = self.pending_contracts.get(contract_id)
        if not contract:
            raise ValueError("Contract not found")
            
        # Check if contract is validated
        if contract.status != ContractStatus.VALIDATED:
            return False
            
        # Check snapshots
        if not contract.snapshot_b:
            return False
            
        # Verify time window
        time_diff = abs(
            contract.snapshot_b.timestamp - contract.snapshot_a.timestamp
        )
        if time_diff > 3600:  # 1 hour max
            self.penalize_fraudulent_wallet(
                contract_id,
                "Time window exceeded"
            )
            return False
            
        # Execute contract
        try:
            self._execute_contract(contract)
            del self.pending_contracts[contract_id]
            return True
        except Exception as e:
            print(f"Failed to execute contract: {str(e)}")
            return False
            
    def penalize_fraudulent_wallet(
        self,
        contract_id: str,
        reason: str
    ):
        """Penalize fraudulent wallet"""
        contract = self.pending_contracts.get(contract_id)
        if not contract:
            raise ValueError("Contract not found")
            
        # Add penalty
        contract.penalties.append(reason)
        contract.status = ContractStatus.PENALIZED
        
        # Burn tokens
        self._burn_tokens(contract)
        
        # Save contract
        self._save_contract(contract)
        
    def sync_offline_contracts(self):
        """Sync offline contracts with blockchain"""
        for contract_id, contract in self.pending_contracts.items():
            if contract.status == ContractStatus.VALIDATED:
                self.finalize_contract_if_valid(contract_id)
                
    def _verify_snapshot(
        self,
        snapshot: ContractSnapshot,
        genesis_hash: str
    ) -> bool:
        """Verify snapshot signature"""
        # Get node's public key
        public_key = self.db.get_node_key(snapshot.node_id)
        if not public_key:
            return False
            
        # Verify data hash
        data = f"{genesis_hash}:{snapshot.location}:{snapshot.timestamp}"
        if snapshot.data_hash != hashlib.sha256(data.encode()).hexdigest():
            return False
            
        # Verify signature
        return verify_signature(
            snapshot.data_hash,
            snapshot.signature,
            public_key
        )
        
    def _save_contract(self, contract: MeshContract):
        """Save contract to file"""
        path = f"{self.contracts_dir}/{contract.contract_id}.json"
        with open(path, "w") as f:
            json.dump(contract.to_dict(), f, indent=2)
            
    def _execute_contract(self, contract: MeshContract):
        """Execute validated contract"""
        # Transfer tokens to recipient
        self.db.transfer_tokens(
            sender=contract.snapshot_a.node_id,
            recipient=contract.snapshot_b.node_id,
            amount=contract.value
        )
        
        # Archive contract
        self._archive_contract(contract)
        
    def _burn_tokens(self, contract: MeshContract):
        """Burn tokens from fraudulent wallet"""
        # Get fraudulent node
        if len(contract.penalties) == 1:
            # Only one node penalized
            node_id = contract.snapshot_b.node_id if contract.snapshot_b else contract.snapshot_a.node_id
        else:
            # Both nodes penalized
            return
            
        # Burn tokens
        self.db.burn_tokens(
            address=node_id,
            amount=contract.value
        )
        
    def _archive_contract(self, contract: MeshContract):
        """Archive executed contract"""
        path = f"{self.contracts_dir}/archive/{contract.contract_id}.json"
        with open(path, "w") as f:
            json.dump(contract.to_dict(), f, indent=2)

class MeshValidator:
    """Mesh network validator"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        hybrid_manager: HybridMeshManager,
        mesh_logger: MeshLogger
    ):
        self.blockchain = blockchain
        self.hybrid_manager = hybrid_manager
        self.mesh_logger = mesh_logger
        
    def validate_node(
        self,
        node_id: str,
        node_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate node data"""
        try:
            # Check required fields
            required_fields = ["status", "stake", "last_seen"]
            for field in required_fields:
                if field not in node_data:
                    return ValidationResult(
                        valid=False,
                        error=f"Missing required field: {field}"
                    )
                    
            # Validate stake
            stake = float(node_data["stake"])
            if stake < 0:
                return ValidationResult(
                    valid=False,
                    error="Invalid stake amount"
                )
                
            # Validate timestamp
            last_seen = int(node_data["last_seen"])
            current_time = int(time.time())
            if last_seen > current_time:
                return ValidationResult(
                    valid=False,
                    error="Future timestamp"
                )
                
            # Validate status
            status = str(node_data["status"]).lower()
            if status not in ["online", "offline", "bridge"]:
                return ValidationResult(
                    valid=False,
                    error="Invalid status"
                )
                
            # Node is valid
            return ValidationResult(
                valid=True,
                details={
                    "node_id": node_id,
                    "status": status,
                    "stake": stake,
                    "last_seen": last_seen
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}"
            )
            
    def validate_contract(
        self,
        contract_id: str,
        contract_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate contract data"""
        try:
            # Check required fields
            required_fields = [
                "initiator",
                "timestamp",
                "coordinates",
                "value",
                "signature"
            ]
            for field in required_fields:
                if field not in contract_data:
                    return ValidationResult(
                        valid=False,
                        error=f"Missing required field: {field}"
                    )
                    
            # Validate initiator
            initiator = str(contract_data["initiator"])
            if not self.blockchain.is_valid_address(initiator):
                return ValidationResult(
                    valid=False,
                    error="Invalid initiator address"
                )
                
            # Validate timestamp
            timestamp = int(contract_data["timestamp"])
            current_time = int(time.time())
            if timestamp > current_time:
                return ValidationResult(
                    valid=False,
                    error="Future timestamp"
                )
                
            # Validate coordinates
            coordinates = contract_data["coordinates"]
            if not isinstance(coordinates, dict):
                return ValidationResult(
                    valid=False,
                    error="Invalid coordinates format"
                )
                
            # Validate value
            value = float(contract_data["value"])
            if value <= 0:
                return ValidationResult(
                    valid=False,
                    error="Invalid contract value"
                )
                
            # Validate signature
            signature = str(contract_data["signature"])
            if not self.blockchain.verify_signature(
                contract_data,
                signature,
                initiator
            ):
                return ValidationResult(
                    valid=False,
                    error="Invalid signature"
                )
                
            # Contract is valid
            return ValidationResult(
                valid=True,
                details={
                    "contract_id": contract_id,
                    "initiator": initiator,
                    "timestamp": timestamp,
                    "value": value
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}"
            )
            
    def validate_pod(
        self,
        contract_id: str,
        pod_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate proof of delivery"""
        try:
            # Check required fields
            required_fields = [
                "validator",
                "timestamp",
                "coordinates",
                "status",
                "signature"
            ]
            for field in required_fields:
                if field not in pod_data:
                    return ValidationResult(
                        valid=False,
                        error=f"Missing required field: {field}"
                    )
                    
            # Validate validator
            validator = str(pod_data["validator"])
            if not self.blockchain.is_valid_address(validator):
                return ValidationResult(
                    valid=False,
                    error="Invalid validator address"
                )
                
            # Validate timestamp
            timestamp = int(pod_data["timestamp"])
            current_time = int(time.time())
            if timestamp > current_time:
                return ValidationResult(
                    valid=False,
                    error="Future timestamp"
                )
                
            # Validate coordinates
            coordinates = pod_data["coordinates"]
            if not isinstance(coordinates, dict):
                return ValidationResult(
                    valid=False,
                    error="Invalid coordinates format"
                )
                
            # Validate status
            status = str(pod_data["status"]).lower()
            if status not in ["pending", "delivered", "failed"]:
                return ValidationResult(
                    valid=False,
                    error="Invalid status"
                )
                
            # Validate signature
            signature = str(pod_data["signature"])
            if not self.blockchain.verify_signature(
                pod_data,
                signature,
                validator
            ):
                return ValidationResult(
                    valid=False,
                    error="Invalid signature"
                )
                
            # PoD is valid
            return ValidationResult(
                valid=True,
                details={
                    "contract_id": contract_id,
                    "validator": validator,
                    "timestamp": timestamp,
                    "status": status
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}"
            )
            
    def validate_sync(
        self,
        node_id: str,
        sync_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate sync data"""
        try:
            # Check required fields
            required_fields = [
                "height",
                "latest_hash",
                "state_hash",
                "timestamp",
                "signature"
            ]
            for field in required_fields:
                if field not in sync_data:
                    return ValidationResult(
                        valid=False,
                        error=f"Missing required field: {field}"
                    )
                    
            # Validate height
            height = int(sync_data["height"])
            if height < 0:
                return ValidationResult(
                    valid=False,
                    error="Invalid block height"
                )
                
            # Validate hashes
            latest_hash = str(sync_data["latest_hash"])
            state_hash = str(sync_data["state_hash"])
            if not (latest_hash and state_hash):
                return ValidationResult(
                    valid=False,
                    error="Invalid hash values"
                )
                
            # Validate timestamp
            timestamp = int(sync_data["timestamp"])
            current_time = int(time.time())
            if timestamp > current_time:
                return ValidationResult(
                    valid=False,
                    error="Future timestamp"
                )
                
            # Validate signature
            signature = str(sync_data["signature"])
            if not self.blockchain.verify_signature(
                sync_data,
                signature,
                node_id
            ):
                return ValidationResult(
                    valid=False,
                    error="Invalid signature"
                )
                
            # Sync data is valid
            return ValidationResult(
                valid=True,
                details={
                    "node_id": node_id,
                    "height": height,
                    "latest_hash": latest_hash,
                    "state_hash": state_hash
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}"
            )
            
    def validate_snapshot(
        self,
        node_id: str,
        snapshot_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate blockchain snapshot"""
        try:
            # Check required fields
            required_fields = [
                "height",
                "blocks",
                "state",
                "timestamp",
                "signature"
            ]
            for field in required_fields:
                if field not in snapshot_data:
                    return ValidationResult(
                        valid=False,
                        error=f"Missing required field: {field}"
                    )
                    
            # Validate height
            height = int(snapshot_data["height"])
            if height < 0:
                return ValidationResult(
                    valid=False,
                    error="Invalid block height"
                )
                
            # Validate blocks
            blocks = snapshot_data["blocks"]
            if not isinstance(blocks, list):
                return ValidationResult(
                    valid=False,
                    error="Invalid blocks format"
                )
                
            if len(blocks) != height + 1:
                return ValidationResult(
                    valid=False,
                    error="Block count mismatch"
                )
                
            # Validate state
            state = snapshot_data["state"]
            if not isinstance(state, dict):
                return ValidationResult(
                    valid=False,
                    error="Invalid state format"
                )
                
            # Validate timestamp
            timestamp = int(snapshot_data["timestamp"])
            current_time = int(time.time())
            if timestamp > current_time:
                return ValidationResult(
                    valid=False,
                    error="Future timestamp"
                )
                
            # Validate signature
            signature = str(snapshot_data["signature"])
            if not self.blockchain.verify_signature(
                snapshot_data,
                signature,
                node_id
            ):
                return ValidationResult(
                    valid=False,
                    error="Invalid signature"
                )
                
            # Snapshot is valid
            return ValidationResult(
                valid=True,
                details={
                    "node_id": node_id,
                    "height": height,
                    "blocks": len(blocks),
                    "state_size": len(json.dumps(state))
                }
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}"
            )
            
    def log_validation(
        self,
        result: ValidationResult,
        validation_type: str,
        entity_id: str
    ):
        """Log validation result"""
        if result.valid:
            self.mesh_logger.log_validation_event(
                contract_id=entity_id,
                validator_id=self.blockchain.node_id,
                status="success",
                details=result.details
            )
        else:
            self.mesh_logger.log_error(
                error_type=f"{validation_type}_validation_failed",
                message=result.error or "Unknown error",
                node_id=entity_id,
                details=result.details
            ) 