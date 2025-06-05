"""
LogiChain OfflineMesh Module
Core implementation of offline mesh operations
"""

import os
import time
import json
import logging
import threading
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from ..core.blockchain import Blockchain
from ..core.transaction import Transaction
from ..core.wallet import Wallet
from .config_offline_mesh import OfflineMeshConfig
from .hybrid_manager import HybridMeshManager
from .lora import LoRaManager

logger = logging.getLogger(__name__)

class ContractStatus(Enum):
    """Contract validation status"""
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    FINALIZED = "finalized"
    PENALIZED = "penalized"

@dataclass
class ContractSnapshot:
    """Contract state snapshot"""
    contract_id: str
    timestamp: int
    block_height: int
    location: Optional[str]
    data_hash: str
    signature: str
    node_id: str
    stake_amount: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "contract_id": self.contract_id,
            "timestamp": self.timestamp,
            "block_height": self.block_height,
            "location": self.location,
            "data_hash": self.data_hash,
            "signature": self.signature,
            "node_id": self.node_id,
            "stake_amount": self.stake_amount
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ContractSnapshot":
        """Create from dictionary"""
        return cls(**data)

@dataclass
class OfflineContract:
    """Offline contract with validation"""
    contract_id: str
    transaction: Transaction
    status: ContractStatus
    snapshots: List[ContractSnapshot]
    validators: Set[str]
    penalties: List[str]
    created_at: int
    updated_at: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "contract_id": self.contract_id,
            "transaction": self.transaction.to_dict(),
            "status": self.status.value,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "validators": list(self.validators),
            "penalties": self.penalties,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "OfflineContract":
        """Create from dictionary"""
        return cls(
            contract_id=data["contract_id"],
            transaction=Transaction.from_dict(data["transaction"]),
            status=ContractStatus(data["status"]),
            snapshots=[ContractSnapshot.from_dict(s) for s in data["snapshots"]],
            validators=set(data["validators"]),
            penalties=data["penalties"],
            created_at=data["created_at"],
            updated_at=data["updated_at"]
        )

@dataclass
class StakeProof:
    stake_amount: float
    stake_time: int
    stake_signature: str

class OfflineMeshValidator:
    def __init__(self):
        self.min_stake_amount = 100.0  # Minimum stake required
        self.min_stake_age = 24 * 60 * 60  # 24 hours in seconds
        self.max_offline_amount = 1000.0  # Maximum amount for offline tx
        self.processed_txs: Set[str] = set()
        self.stake_registry: Dict[str, StakeProof] = {}
        
    def validate_offline_transaction(
        self,
        transaction: Dict,
        stake_proof: StakeProof
    ) -> bool:
        """
        Validate offline transaction with stake-based security
        """
        try:
            # 1. Verify stake requirements
            if not self._verify_stake(stake_proof):
                return False
                
            # 2. Verify transaction basics
            if not self._verify_transaction_basics(transaction):
                return False
                
            # 3. Verify amount limits
            if transaction["amount"] > self.max_offline_amount:
                return False
                
            # 4. Verify double spending
            if not self._verify_no_double_spend(transaction):
                return False
                
            # 5. Verify signatures
            if not self._verify_signatures(transaction, stake_proof):
                return False
                
            # 6. Add to processed transactions
            self.processed_txs.add(transaction["id"])
            
            return True
            
        except Exception:
            return False
            
    def _verify_stake(self, stake_proof: StakeProof) -> bool:
        """Verify stake meets minimum requirements"""
        # Check stake amount
        if stake_proof.stake_amount < self.min_stake_amount:
            return False
            
        # Check stake age
        current_time = int(time.time())
        if current_time - stake_proof.stake_time < self.min_stake_age:
            return False
            
        # Verify stake signature
        if not self._verify_stake_signature(stake_proof):
            return False
            
        return True
        
    def _verify_transaction_basics(self, transaction: Dict) -> bool:
        """Verify basic transaction properties"""
        required_fields = ["id", "from", "to", "amount", "timestamp", "signature"]
        
        # Check required fields
        for field in required_fields:
            if field not in transaction:
                return False
                
        # Check timestamp
        current_time = int(time.time())
        if abs(transaction["timestamp"] - current_time) > 3600:  # 1 hour window
            return False
            
        # Verify amount
        if transaction["amount"] <= 0:
            return False
            
        return True
        
    def _verify_no_double_spend(self, transaction: Dict) -> bool:
        """Verify transaction is not double spent"""
        # Check if already processed
        if transaction["id"] in self.processed_txs:
            return False
            
        # Check input UTXOs not spent
        for input_tx in transaction.get("inputs", []):
            if input_tx["id"] in self.processed_txs:
                return False
                
        return True
        
    def _verify_signatures(
        self,
        transaction: Dict,
        stake_proof: StakeProof
    ) -> bool:
        """Verify all transaction signatures"""
        try:
            # Verify transaction signature
            tx_data = {k:v for k,v in transaction.items() if k != "signature"}
            tx_hash = hashlib.sha256(
                json.dumps(tx_data, sort_keys=True).encode()
            ).hexdigest()
            
            if not self._verify_signature(
                tx_hash,
                transaction["signature"],
                transaction["from"]
            ):
                return False
                
            # Verify stake signature
            stake_data = f"{stake_proof.stake_amount}:{stake_proof.stake_time}"
            if not self._verify_signature(
                stake_data,
                stake_proof.stake_signature,
                transaction["from"]
            ):
                return False
                
            return True
            
        except Exception:
            return False
            
    def _verify_signature(
        self,
        message: str,
        signature: str,
        public_key: str
    ) -> bool:
        """Verify cryptographic signature"""
        try:
            # Implementation depends on crypto library used
            return True # TODO: Implement actual signature verification
        except Exception:
            return False
            
    def _verify_stake_signature(self, stake_proof: StakeProof) -> bool:
        """Verify stake proof signature"""
        try:
            # Implementation depends on crypto library used
            return True # TODO: Implement actual stake signature verification
        except Exception:
            return False

class OfflineMeshModule:
    """Main OfflineMesh module implementation"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        config: OfflineMeshConfig
    ):
        self.blockchain = blockchain
        self.config = config
        self.enabled = False
        self.running = False
        
        # Components
        self.lora: Optional[LoRaManager] = None
        self.hybrid: Optional[HybridMeshManager] = None
        
        # State
        self.contracts: Dict[str, OfflineContract] = {}
        self.pending_sync: Set[str] = set()
        self.banned_nodes: Set[str] = set()
        
        # Locks
        self._contract_lock = threading.Lock()
        self._sync_lock = threading.Lock()
        
    def start(self) -> bool:
        """Start offline mesh module"""
        if not self.config.enabled:
            logger.info("OfflineMesh module is disabled")
            return False
            
        if not self.config.validate():
            logger.error("Invalid configuration")
            return False
            
        try:
            # Initialize components
            self._init_components()
            
            # Load persisted state
            self._load_state()
            
            # Start background tasks
            self.running = True
            threading.Thread(
                target=self._cleanup_loop,
                daemon=True
            ).start()
            threading.Thread(
                target=self._sync_loop,
                daemon=True
            ).start()
            
            self.enabled = True
            logger.info("OfflineMesh module started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start module: {str(e)}")
            self.stop()
            return False
            
    def stop(self):
        """Stop offline mesh module"""
        try:
            # Stop components
            if self.hybrid:
                self.hybrid.stop()
            if self.lora:
                self.lora.stop()
                
            # Save state
            self._save_state()
            
            self.running = False
            self.enabled = False
            logger.info("OfflineMesh module stopped")
            
        except Exception as e:
            logger.error(f"Error stopping module: {str(e)}")
            
    def create_contract(
        self,
        wallet: Wallet,
        recipient: str,
        amount: float,
        location: Optional[str] = None
    ) -> Optional[str]:
        """Create new offline contract"""
        if not self.enabled:
            logger.error("Module is not enabled")
            return None
            
        try:
            # Verify wallet stake
            if not self._verify_stake(wallet.address):
                logger.error(f"Insufficient stake for {wallet.address}")
                return None
                
            # Create and sign transaction
            tx = Transaction(
                sender=wallet.address,
                recipient=recipient,
                amount=amount,
                timestamp=int(time.time())
            )
            tx.sign(wallet.private_key)
            
            # Create contract
            contract = OfflineContract(
                contract_id=tx.hash,
                transaction=tx,
                status=ContractStatus.PENDING,
                snapshots=[],
                validators=set(),
                penalties=[],
                created_at=int(time.time()),
                updated_at=int(time.time())
            )
            
            # Add initial snapshot
            snapshot = self._create_snapshot(
                contract.contract_id,
                wallet.address,
                location
            )
            contract.snapshots.append(snapshot)
            
            # Store contract
            with self._contract_lock:
                self.contracts[contract.contract_id] = contract
                self._save_contract(contract)
                
            return contract.contract_id
            
        except Exception as e:
            logger.error(f"Failed to create contract: {str(e)}")
            return None
            
    def validate_contract(
        self,
        contract_id: str,
        wallet: Wallet,
        location: Optional[str] = None
    ) -> bool:
        """Validate offline contract"""
        if not self.enabled:
            logger.error("Module is not enabled")
            return False
            
        try:
            # Get contract
            contract = self.contracts.get(contract_id)
            if not contract:
                logger.error(f"Contract {contract_id} not found")
                return False
                
            # Verify wallet stake
            if not self._verify_stake(wallet.address):
                logger.error(f"Insufficient stake for {wallet.address}")
                return False
                
            # Check if already validated
            if wallet.address in contract.validators:
                logger.error(f"Already validated by {wallet.address}")
                return False
                
            # Create validation snapshot
            snapshot = self._create_snapshot(
                contract_id,
                wallet.address,
                location
            )
            
            # Update contract
            with self._contract_lock:
                contract.snapshots.append(snapshot)
                contract.validators.add(wallet.address)
                contract.updated_at = int(time.time())
                
                # Check if enough validators
                if len(contract.validators) >= self.config.security.min_validators:
                    contract.status = ContractStatus.VALIDATED
                    
                self._save_contract(contract)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate contract: {str(e)}")
            return False
            
    def get_contract(self, contract_id: str) -> Optional[Dict]:
        """Get contract details"""
        contract = self.contracts.get(contract_id)
        return contract.to_dict() if contract else None
        
    def get_pending_contracts(self) -> List[Dict]:
        """Get all pending contracts"""
        return [
            contract.to_dict()
            for contract in self.contracts.values()
            if contract.status in [ContractStatus.PENDING, ContractStatus.VALIDATING]
        ]
        
    def _init_components(self):
        """Initialize module components"""
        # Create LoRa manager
        self.lora = LoRaManager(
            node_id=self.blockchain.node_id,
            port=self.config.lora.port,
            baudrate=self.config.lora.baudrate
        )
        
        # Create hybrid manager
        self.hybrid = HybridMeshManager(
            blockchain=self.blockchain,
            lora=self.lora,
            config=self.config
        )
        
        # Start components
        self.lora.start()
        self.hybrid.start()
        
    def _verify_stake(self, address: str) -> bool:
        """Verify if address has sufficient stake"""
        try:
            # Check if banned
            if address in self.banned_nodes:
                return False
                
            # Get balance
            balance = self.blockchain.get_balance(address)
            return balance >= self.config.security.min_stake_amount
            
        except Exception:
            return False
            
    def _create_snapshot(
        self,
        contract_id: str,
        node_id: str,
        location: Optional[str]
    ) -> ContractSnapshot:
        """Create contract snapshot"""
        timestamp = int(time.time())
        block_height = self.blockchain.get_height()
        
        # Create data hash
        data = f"{contract_id}:{timestamp}:{block_height}:{location}"
        data_hash = self.blockchain.hash(data.encode())
        
        # Sign data
        signature = self.blockchain.sign(
            data_hash.encode(),
            self.blockchain.private_key
        )
        
        # Get stake amount
        stake_amount = self.blockchain.get_balance(node_id)
        
        return ContractSnapshot(
            contract_id=contract_id,
            timestamp=timestamp,
            block_height=block_height,
            location=location,
            data_hash=data_hash,
            signature=signature,
            node_id=node_id,
            stake_amount=stake_amount
        )
        
    def _cleanup_loop(self):
        """Cleanup expired contracts"""
        while self.running:
            try:
                current_time = int(time.time())
                current_height = self.blockchain.get_height()
                
                with self._contract_lock:
                    # Find expired contracts
                    expired = [
                        contract_id
                        for contract_id, contract in self.contracts.items()
                        if self._is_contract_expired(contract, current_time, current_height)
                    ]
                    
                    # Remove expired contracts
                    for contract_id in expired:
                        contract = self.contracts.pop(contract_id)
                        self._handle_expired_contract(contract)
                        
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
                time.sleep(60)
                
    def _sync_loop(self):
        """Synchronize contracts with blockchain"""
        while self.running:
            try:
                with self._sync_lock:
                    # Find contracts to sync
                    to_sync = [
                        contract
                        for contract in self.contracts.values()
                        if contract.status == ContractStatus.VALIDATED
                        and contract.contract_id not in self.pending_sync
                    ]
                    
                    # Sync contracts
                    for contract in to_sync:
                        self._sync_contract(contract)
                        
                time.sleep(self.config.network.sync_interval)
                
            except Exception as e:
                logger.error(f"Sync error: {str(e)}")
                time.sleep(60)
                
    def _is_contract_expired(
        self,
        contract: OfflineContract,
        current_time: int,
        current_height: int
    ) -> bool:
        """Check if contract is expired"""
        # Check time expiration
        if current_time - contract.created_at > self.config.security.signature_timeout:
            return True
            
        # Check block expiration
        if current_height - contract.snapshots[0].block_height > self.config.security.max_offline_blocks:
            return True
            
        return False
        
    def _handle_expired_contract(self, contract: OfflineContract):
        """Handle expired contract"""
        try:
            # Penalize contract creator
            penalty_amount = self._penalize_node(
                contract.transaction.sender,
                f"Contract {contract.contract_id} expired"
            )
            
            # Compensate recipient
            if penalty_amount > 0:
                self._compensate_innocent_party(
                    contract.transaction.recipient,
                    penalty_amount,
                    f"Compensation for expired contract {contract.contract_id}"
                )
            
            # Save as expired
            contract.status = ContractStatus.REJECTED
            self._save_contract(contract)
            
        except Exception as e:
            logger.error(f"Failed to handle expired contract: {str(e)}")
            
    def _sync_contract(self, contract: OfflineContract):
        """Synchronize contract with blockchain"""
        try:
            # Mark as syncing
            self.pending_sync.add(contract.contract_id)
            
            # Submit transaction
            success = self.blockchain.submit_transaction(
                contract.transaction
            )
            
            if success:
                # Reward validators
                self._reward_validators(contract)
                
                # Update contract
                contract.status = ContractStatus.FINALIZED
                self._save_contract(contract)
            else:
                # Penalize participants
                for validator in contract.validators:
                    self._penalize_node(
                        validator,
                        f"Invalid contract {contract.contract_id}"
                    )
                contract.status = ContractStatus.PENALIZED
                self._save_contract(contract)
                
        except Exception as e:
            logger.error(f"Failed to sync contract: {str(e)}")
            
        finally:
            # Remove from pending
            self.pending_sync.remove(contract.contract_id)
            
    def _reward_validators(self, contract: OfflineContract):
        """Reward contract validators"""
        try:
            # Calculate reward
            total_value = contract.transaction.amount
            reward_per_validator = (total_value * 0.01) / len(contract.validators)
            
            # Reward each validator
            for validator in contract.validators:
                self.blockchain.mint_tokens(
                    address=validator,
                    amount=reward_per_validator
                )
                logger.info(f"Rewarded validator {validator} with {reward_per_validator} tokens")
                
        except Exception as e:
            logger.error(f"Failed to reward validators: {str(e)}")
            
    def _penalize_node(self, node_id: str, reason: str) -> float:
        """Penalize fraudulent node"""
        try:
            # Calculate penalty
            balance = self.blockchain.get_balance(node_id)
            penalty = min(
                balance,
                self.config.security.penalty_amount
            )
            
            if penalty <= 0:
                return 0
            
            # Burn stake
            self.blockchain.burn_tokens(
                address=node_id,
                amount=penalty
            )
            
            # Ban node
            self.banned_nodes.add(node_id)
            
            logger.warning(f"Penalized node {node_id}: {reason}")
            return penalty
            
        except Exception as e:
            logger.error(f"Failed to penalize node: {str(e)}")
            return 0
            
    def _compensate_innocent_party(
        self,
        address: str,
        amount: float,
        reason: str
    ):
        """Compensate innocent party"""
        try:
            # Mint compensation tokens
            self.blockchain.mint_tokens(
                address=address,
                amount=amount
            )
            
            logger.info(
                f"Compensated {address} with {amount} tokens: {reason}"
            )
            
        except Exception as e:
            logger.error(f"Failed to compensate party: {str(e)}")
            
    def _save_contract(self, contract: OfflineContract):
        """Save contract to file"""
        try:
            path = os.path.join(
                self.config.contracts_dir,
                f"{contract.contract_id}.json"
            )
            with open(path, "w") as f:
                json.dump(contract.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save contract: {str(e)}")
            
    def _load_state(self):
        """Load persisted state"""
        try:
            # Load contracts
            for filename in os.listdir(self.config.contracts_dir):
                if filename.endswith(".json"):
                    path = os.path.join(self.config.contracts_dir, filename)
                    with open(path) as f:
                        data = json.load(f)
                        contract = OfflineContract.from_dict(data)
                        self.contracts[contract.contract_id] = contract
                        
            logger.info(f"Loaded {len(self.contracts)} contracts")
            
        except Exception as e:
            logger.error(f"Failed to load state: {str(e)}")
            
    def _save_state(self):
        """Save module state"""
        try:
            # Save all contracts
            for contract in self.contracts.values():
                self._save_contract(contract)
                
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}") 