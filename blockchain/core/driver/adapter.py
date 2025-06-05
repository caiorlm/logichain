import time
import json
import hashlib
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from ..blockchain import Transaction, TransactionType, Block
from ..wallet import Wallet
from ..pod import ProofOfDelivery
from ..network import P2PProtocol
from ..mempool import MemPool
from ..merkle import MerkleTree
from ..utils.crypto import sign_message, verify_signature
from ..utils.validation import validate_gps_point
from ..location.gps_manager import GPSPoint, LocationProof
from .gps_diagnostics import GPSDiagnostics, DiagnosticResult

@dataclass
class DeliveryLocationTransaction(Transaction):
    gps_hash: str
    signature: str
    encrypted_timestamp: str
    local_nonce: int
    route_id: str
    
    def validate(self) -> bool:
        """Validates the GPS location transaction"""
        try:
            # Verify signature
            if not verify_signature(
                self.gps_hash.encode(),
                self.signature,
                self.sender_address
            ):
                return False
                
            # Verify timestamp format
            if not self.encrypted_timestamp:
                return False
                
            # Additional validation can be added here
            return True
        except Exception:
            return False

class DriverNodeAdapter:
    def __init__(
        self,
        wallet: Wallet,
        mempool: MemPool,
        gps_manager: 'GPSManager',
        p2p: P2PProtocol,
        pod: ProofOfDelivery,
        storage_path: str = "driver_data",
        required_gps_points: int = 10,
        gps_accuracy_limit: float = 10.0
    ):
        self.wallet = wallet
        self.mempool = mempool
        self.gps_manager = gps_manager
        self.p2p = p2p
        self.pod = pod
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # GPS diagnostics
        self.gps_diagnostics = GPSDiagnostics(
            required_points=required_gps_points,
            accuracy_limit=gps_accuracy_limit
        )
        
        # Contract state
        self.contracts_unlocked = False
        self.current_route_id: Optional[str] = None
        self.pending_points: List[Dict] = []
        self.merkle_tree = MerkleTree()
        
        # Setup P2P handlers
        self.p2p.register_handler(
            "pending_route_proof",
            self._handle_pending_route
        )
        
    async def verify_gps_device(self) -> Tuple[bool, str]:
        """Verifies GPS device and unlocks contract functionality"""
        # Run GPS diagnostic test
        result = await self.gps_diagnostics.run_test(self.gps_manager)
        
        if result.success:
            self.contracts_unlocked = True
            return True, "GPS verificado com sucesso"
        else:
            self.contracts_unlocked = False
            return False, result.error_message
            
    async def get_available_contracts(self) -> List[Dict]:
        """Gets available delivery contracts"""
        if not self.contracts_unlocked:
            raise ValueError(
                "GPS não verificado. Execute verify_gps_device() primeiro."
            )
            
        # Get contracts from blockchain
        return await self.pod.get_available_contracts(self.wallet.address)
        
    async def accept_contract(self, contract_id: str) -> bool:
        """Accepts a delivery contract"""
        if not self.contracts_unlocked:
            raise ValueError(
                "GPS não verificado. Execute verify_gps_device() primeiro."
            )
            
        # Verify contract exists and is available
        contract = await self.pod.get_contract(contract_id)
        if not contract or contract["status"] != "available":
            return False
            
        # Start route tracking
        await self.start_route(contract_id)
        
        # Accept contract on blockchain
        return await self.pod.accept_contract(
            contract_id,
            self.wallet.address,
            self.wallet.sign_message(contract_id.encode())
        )
        
    async def start_route(self, route_id: str):
        """Starts tracking a new delivery route"""
        if not self.contracts_unlocked:
            raise ValueError(
                "GPS não verificado. Execute verify_gps_device() primeiro."
            )
            
        self.current_route_id = route_id
        self.pending_points = []
        self.merkle_tree = MerkleTree()
        
        # Start GPS collection if not already running
        if not self.gps_manager._running:
            self.gps_manager.start_collection()
            
    async def process_gps_point(self, point: GPSPoint):
        """Processes a new GPS point and creates blockchain transaction"""
        if not self.current_route_id:
            return
            
        # Validate point
        if not self.gps_diagnostics._validate_point(point):
            return
            
        # Create proof
        proof = LocationProof(self.wallet.private_key).create_proof(
            point,
            self.pending_points[-1]["hash"] if self.pending_points else None
        )
        
        # Create transaction
        tx = DeliveryLocationTransaction(
            tx_type=TransactionType.DELIVERY_LOCATION,
            sender_address=self.wallet.address,
            recipient_address=self.current_route_id,
            amount=0,
            timestamp=time.time(),
            gps_hash=proof["signature"],
            signature=sign_message(
                proof["signature"].encode(),
                self.wallet.private_key
            ),
            encrypted_timestamp=str(point.timestamp),
            local_nonce=len(self.pending_points),
            route_id=self.current_route_id
        )
        
        # Store locally
        point_data = {
            "point": point.to_dict(),
            "proof": proof,
            "transaction": tx.__dict__,
            "hash": proof["signature"]
        }
        self.pending_points.append(point_data)
        
        # Add to Merkle tree
        self.merkle_tree.add_leaf(json.dumps(point_data))
        
        # Try to submit to blockchain
        await self._try_submit_to_chain()
        
        # Broadcast to P2P network
        await self.p2p.broadcast(
            "pending_route_proof",
            {
                "route_id": self.current_route_id,
                "point": point_data
            }
        )
        
    async def _try_submit_to_chain(self):
        """Attempts to submit pending points to blockchain"""
        if not self.pending_points:
            return
            
        try:
            # Create transactions for all pending points
            for point_data in self.pending_points:
                tx = point_data["transaction"]
                if self.mempool.add_transaction(tx):
                    # Save successful submission
                    self._save_point(point_data)
                    
            # Clear submitted points
            self.pending_points = []
            
        except Exception as e:
            print(f"Failed to submit to blockchain: {str(e)}")
            
    def _save_point(self, point_data: Dict):
        """Saves point data to local storage"""
        timestamp = point_data["point"]["timestamp"]
        file_path = self.storage_path / f"point_{timestamp}.json"
        
        with open(file_path, "w") as f:
            json.dump(point_data, f)
            
    async def _handle_pending_route(self, data: Dict):
        """Handles pending route proof from P2P network"""
        if not data.get("route_id") or not data.get("point"):
            return
            
        # Validate point
        point_data = data["point"]
        if not validate_gps_point(point_data["point"]):
            return
            
        # Verify proof chain
        if self.pending_points:
            if point_data["proof"].get("previous_hash") != self.pending_points[-1]["hash"]:
                return
                
        # Add to local state
        self.pending_points.append(point_data)
        
        # Update Merkle tree
        self.merkle_tree.add_leaf(json.dumps(point_data))
        
    def get_route_proof(self, start_time: float, end_time: float) -> Dict:
        """Gets cryptographic proof of route between timestamps"""
        if not self.contracts_unlocked:
            raise ValueError(
                "GPS não verificado. Execute verify_gps_device() primeiro."
            )
            
        points = self.gps_manager.get_route_proof(start_time, end_time)
        
        return {
            "points": points,
            "merkle_root": self.merkle_tree.get_merkle_root(),
            "route_id": self.current_route_id,
            "signature": sign_message(
                self.merkle_tree.get_merkle_root().encode(),
                self.wallet.private_key
            )
        } 