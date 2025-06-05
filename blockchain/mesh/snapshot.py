"""
LogiChain State Snapshot
Handles immutable state snapshots with cryptographic integrity
"""

import time
import json
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from ..crypto.keys import sign_message, verify_signature

@dataclass
class SyncMetadata:
    """Metadata for each sync operation"""
    timestamp: float
    node_id: str
    signature: str

@dataclass
class SyncHop:
    """Represents a hop in transaction sync path"""
    node_id: str
    timestamp: float
    signature: str
    
    def validate(
        self,
        tx_hash: str,
        prev_timestamp: float,
        key_manager: KeyManager,
        max_time_drift: int = 300
    ) -> bool:
        """Validate hop integrity"""
        current_time = time.time()
        
        # Check timestamp bounds
        if self.timestamp < prev_timestamp:
            return False
        if self.timestamp > current_time + max_time_drift:
            return False
        if self.timestamp - prev_timestamp > max_time_drift:
            return False
            
        # Get and validate node key
        public_key = key_manager.get_node_key(self.node_id)
        if not public_key or not key_manager.is_trusted(self.node_id):
            return False
            
        # Verify signature
        content = f"{tx_hash}:{self.timestamp}:{self.node_id}"
        return verify_signature(content, self.signature, public_key)

@dataclass
class Transaction:
    """Transaction with complete sync history"""
    tx_hash: str
    sender_id: str
    original_timestamp: float
    origin_node: str
    sync_path: List[SyncHop]
    signature: str
    data: Dict
    
    def add_sync_hop(self, node_id: str, private_key: str):
        """Add sync hop with signature"""
        # Create hop record
        hop = SyncHop(
            node_id=node_id,
            timestamp=time.time(),
            signature=""
        )
        
        # Sign hop record
        content = f"{self.tx_hash}:{hop.timestamp}:{node_id}"
        hop.signature = sign_message(content, private_key)
        
        # Add to path
        self.sync_path.append(hop)
        
    def validate_sync_path(
        self,
        key_manager: KeyManager,
        max_time_drift: int = 300
    ) -> bool:
        """Validate complete sync path"""
        # Must have sync path starting with origin
        if not self.sync_path:
            return False
        if self.sync_path[0].node_id != self.origin_node:
            return False
            
        # Check for duplicates in path
        seen_nodes = {self.sync_path[0].node_id}
        prev_time = self.original_timestamp
        
        # Validate each hop
        for hop in self.sync_path:
            # Check for duplicate nodes
            if hop.node_id in seen_nodes and hop != self.sync_path[0]:
                return False
            seen_nodes.add(hop.node_id)
            
            # Validate hop integrity
            if not hop.validate(
                self.tx_hash,
                prev_time,
                key_manager,
                max_time_drift
            ):
                return False
            prev_time = hop.timestamp
            
        return True
        
    def validate_complete(
        self,
        key_manager: KeyManager,
        current_time: Optional[float] = None
    ) -> bool:
        """Complete transaction validation"""
        if current_time is None:
            current_time = time.time()
            
        # Check timestamps
        if self.original_timestamp > current_time:
            return False
            
        # Validate origin node
        origin_key = key_manager.get_node_key(self.origin_node)
        if not origin_key or not key_manager.is_trusted(self.origin_node):
            return False
            
        # Verify transaction signature
        content = f"{self.sender_id}:{self.original_timestamp}:{self.data}"
        if not verify_signature(content, self.signature, origin_key):
            return False
            
        # Validate sync path
        return self.validate_sync_path(key_manager)
        
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "tx_hash": self.tx_hash,
            "sender_id": self.sender_id,
            "original_timestamp": self.original_timestamp,
            "origin_node": self.origin_node,
            "sync_path": [
                {
                    "node_id": hop.node_id,
                    "timestamp": hop.timestamp,
                    "signature": hop.signature
                }
                for hop in self.sync_path
            ],
            "signature": self.signature,
            "data": self.data
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        """Create from dictionary"""
        sync_path = [
            SyncHop(**hop)
            for hop in data["sync_path"]
        ]
        
        return cls(
            tx_hash=data["tx_hash"],
            sender_id=data["sender_id"],
            original_timestamp=data["original_timestamp"],
            origin_node=data["origin_node"],
            sync_path=sync_path,
            signature=data["signature"],
            data=data["data"]
        )

class StateSnapshot:
    """Immutable state snapshot with cryptographic integrity"""
    
    def __init__(
        self,
        node_id: str,
        private_key: str,
        transactions: Optional[List[Transaction]] = None,
        previous_hash: Optional[str] = None,
        ancestry: Optional[List[str]] = None,
        version: int = 0
    ):
        self.node_id = node_id
        self.private_key = private_key
        self.timestamp = time.time()
        self.transactions = transactions or []
        self.previous_hash = previous_hash
        self.ancestry = ancestry or []
        self.version = version
        self.state_hash = None
        self.signature = None
        
        # Generate hash and sign if we have transactions
        if self.transactions:
            self.generate_hash()
            self.sign()
            
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction and update hash/signature"""
        if not self._validate_transaction(transaction):
            return False
            
        self.transactions.append(transaction)
        self.generate_hash()
        self.sign()
        return True
        
    def generate_hash(self) -> str:
        """Generate deterministic hash of snapshot content"""
        # Sort transactions by original timestamp
        sorted_txs = sorted(
            self.transactions,
            key=lambda x: x.original_timestamp
        )
        
        # Create content dictionary
        content = {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in sorted_txs],
            "previous_hash": self.previous_hash,
            "ancestry": self.ancestry,
            "version": self.version
        }
        
        # Generate hash
        content_str = json.dumps(content, sort_keys=True)
        self.state_hash = hashlib.sha256(content_str.encode()).hexdigest()
        return self.state_hash
        
    def sign(self):
        """Sign the state hash with node's private key"""
        if not self.state_hash:
            self.generate_hash()
        self.signature = sign_message(self.state_hash, self.private_key)
        
    def verify(self, public_key: str) -> bool:
        """Verify snapshot integrity and signature"""
        if not self.state_hash or not self.signature:
            return False
            
        # Verify hash matches content
        current_hash = self.generate_hash()
        if current_hash != self.state_hash:
            return False
            
        # Verify signature
        return verify_signature(self.state_hash, self.signature, public_key)
        
    def _validate_transaction(self, transaction: Transaction) -> bool:
        """Validate transaction before adding"""
        required_fields = [
            "tx_hash",
            "sender_id",
            "original_timestamp",
            "origin_node",
            "signature"
        ]
        
        # Check required fields
        tx_dict = transaction.to_dict()
        if not all(field in tx_dict for field in required_fields):
            return False
            
        # Validate timestamps
        if transaction.original_timestamp > time.time():
            return False
            
        # Check for duplicates
        if any(tx.tx_hash == transaction.tx_hash for tx in self.transactions):
            return False
            
        return True
        
    def to_dict(self) -> Dict:
        """Convert snapshot to dictionary"""
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "ancestry": self.ancestry,
            "version": self.version,
            "state_hash": self.state_hash,
            "signature": self.signature
        }
        
    @classmethod
    def from_dict(cls, data: Dict, node_id: str, private_key: str) -> 'StateSnapshot':
        """Create snapshot from dictionary"""
        transactions = [
            Transaction.from_dict(tx_data)
            for tx_data in data["transactions"]
        ]
        
        snapshot = cls(
            node_id=node_id,
            private_key=private_key,
            transactions=transactions,
            previous_hash=data.get("previous_hash"),
            ancestry=data.get("ancestry", []),
            version=data.get("version", 0)
        )
        
        snapshot.timestamp = data["timestamp"]
        snapshot.state_hash = data["state_hash"]
        snapshot.signature = data["signature"]
        
        return snapshot 