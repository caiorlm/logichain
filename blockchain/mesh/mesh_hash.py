"""
Mesh network hashing and validation system
"""

import hashlib
import time
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
import json

@dataclass
class MeshNode:
    node_id: str
    public_key: str
    last_seen: float
    reputation: float

class MeshHash:
    """Handles hashing and validation in mesh network"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.known_nodes: Dict[str, MeshNode] = {}
        self.local_transactions = []
        self.validation_cache = {}
        
    def calculate_mesh_transaction_hash(
        self,
        transaction: Dict,
        validators: List[str]
    ) -> str:
        """
        Calculate mesh transaction hash with validator signatures
        """
        # Base transaction hash
        tx_string = json.dumps(transaction, sort_keys=True)
        tx_hash = hashlib.sha256(tx_string.encode()).hexdigest()
        
        # Add validator signatures
        validator_string = "-".join(sorted(validators))
        mesh_hash = hashlib.sha256(
            f"{tx_hash}-{validator_string}".encode()
        ).hexdigest()
        
        return mesh_hash
        
    def create_mesh_block(
        self,
        transactions: List[Dict],
        validators: List[str],
        previous_hash: str
    ) -> Dict:
        """
        Create a mesh block with lightweight PoW
        """
        # Calculate transaction merkle root
        tx_hashes = [
            self.calculate_mesh_transaction_hash(tx, validators)
            for tx in transactions
        ]
        merkle_root = self._calculate_merkle_root(tx_hashes)
        
        # Create block header
        timestamp = int(time.time())
        block_header = {
            "version": 1,
            "previous_hash": previous_hash,
            "merkle_root": merkle_root,
            "timestamp": timestamp,
            "validator_count": len(validators),
            "mode": "mesh"
        }
        
        # Calculate lightweight PoW
        nonce = self._find_mesh_pow(block_header)
        block_header["nonce"] = nonce
        
        return {
            "header": block_header,
            "transactions": transactions,
            "validators": validators,
            "mesh_hash": self._calculate_mesh_block_hash(block_header)
        }
        
    def validate_mesh_block(
        self,
        block: Dict,
        required_validators: int = 3
    ) -> Tuple[bool, str]:
        """
        Validate a mesh block
        """
        # Check minimum validators
        if len(block["validators"]) < required_validators:
            return False, "Insufficient validators"
            
        # Verify block hash
        calculated_hash = self._calculate_mesh_block_hash(block["header"])
        if calculated_hash != block["mesh_hash"]:
            return False, "Invalid block hash"
            
        # Verify merkle root
        tx_hashes = [
            self.calculate_mesh_transaction_hash(tx, block["validators"])
            for tx in block["transactions"]
        ]
        calculated_merkle = self._calculate_merkle_root(tx_hashes)
        if calculated_merkle != block["header"]["merkle_root"]:
            return False, "Invalid merkle root"
            
        # Verify lightweight PoW
        if not self._verify_mesh_pow(block["header"]):
            return False, "Invalid mesh PoW"
            
        return True, "Valid mesh block"
        
    def _calculate_merkle_root(self, hashes: List[str]) -> str:
        """Calculate merkle root from list of hashes"""
        if not hashes:
            return hashlib.sha256("empty_mesh".encode()).hexdigest()
            
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
                
            next_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i+1]
                next_hash = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(next_hash)
            hashes = next_level
            
        return hashes[0]
        
    def _calculate_mesh_block_hash(self, header: Dict) -> str:
        """Calculate mesh block hash"""
        header_string = json.dumps(header, sort_keys=True)
        timestamp_salt = str(int(time.time() / 300)).encode()  # 5-minute window
        return hashlib.sha256(
            header_string.encode() + timestamp_salt
        ).hexdigest()
        
    def _find_mesh_pow(self, header: Dict, difficulty: int = 2) -> int:
        """Find nonce for lightweight mesh PoW"""
        nonce = 0
        while True:
            header["nonce"] = nonce
            block_hash = self._calculate_mesh_block_hash(header)
            if block_hash.startswith("0" * difficulty):
                return nonce
            nonce += 1
            
    def _verify_mesh_pow(
        self,
        header: Dict,
        difficulty: int = 2
    ) -> bool:
        """Verify lightweight mesh PoW"""
        block_hash = self._calculate_mesh_block_hash(header)
        return block_hash.startswith("0" * difficulty)
        
    def add_node(self, node: MeshNode):
        """Add or update a known mesh node"""
        self.known_nodes[node.node_id] = node
        
    def update_node_reputation(
        self,
        node_id: str,
        validation_success: bool
    ):
        """Update node reputation based on validation success"""
        if node_id in self.known_nodes:
            node = self.known_nodes[node_id]
            if validation_success:
                node.reputation = min(1.0, node.reputation + 0.1)
            else:
                node.reputation = max(0.0, node.reputation - 0.2)
            node.last_seen = time.time() 