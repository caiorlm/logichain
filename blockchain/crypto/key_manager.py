"""
LogiChain Key Manager
Manages node keys and trust relationships
"""

import json
import time
from typing import Dict, Optional, Set, List
from dataclasses import dataclass
from .keys import verify_signature

@dataclass
class NodeKey:
    """Node key information"""
    node_id: str
    public_key: str
    added_at: float
    last_seen: float
    trust_level: int = 0

class KeyManager:
    """Manages node keys and trust relationships"""
    
    def __init__(self):
        self.node_keys: Dict[str, str] = {}  # node_id -> public_key
        self.trusted_nodes: Dict[str, bool] = {}  # node_id -> is_trusted
        
    def add_node_key(
        self,
        node_id: str,
        public_key: str,
        trust: bool = False
    ):
        """Add node public key"""
        self.node_keys[node_id] = public_key
        self.trusted_nodes[node_id] = trust
        
    def get_node_key(self, node_id: str) -> Optional[str]:
        """Get node public key"""
        return self.node_keys.get(node_id)
        
    def is_trusted(self, node_id: str) -> bool:
        """Check if node is trusted"""
        return self.trusted_nodes.get(node_id, False)
        
    def verify_node_signature(
        self,
        node_id: str,
        message: str,
        signature: str
    ) -> bool:
        """Verify node signature"""
        public_key = self.get_node_key(node_id)
        if not public_key:
            return False
            
        return verify_signature(message, signature, public_key)
        
    def validate_sync_path(
        self,
        sync_path: List[Dict],
        tx_hash: str
    ) -> bool:
        """Validate sync path signatures"""
        if not sync_path:
            return False
            
        prev_time = 0
        for hop in sync_path:
            # Check required fields
            if not all(k in hop for k in ["node_id", "timestamp", "signature"]):
                return False
                
            # Validate timestamp order
            if hop["timestamp"] < prev_time:
                return False
            prev_time = hop["timestamp"]
            
            # Get node key
            node_id = hop["node_id"]
            public_key = self.get_node_key(node_id)
            if not public_key:
                return False
                
            # Verify signature
            content = f"{tx_hash}:{hop['timestamp']}:{node_id}"
            if not verify_signature(content, hop["signature"], public_key):
                return False
                
        return True
        
    def cleanup_old_keys(self, max_age: int = 86400):
        """Remove old untrusted keys"""
        current_time = time.time()
        to_remove = [
            node_id
            for node_id, key in self.node_keys.items()
            if (current_time - key.last_seen > max_age and
                node_id not in self.trusted_nodes)
        ]
        
        for node_id in to_remove:
            del self.node_keys[node_id]
            
    def export_trusted_keys(self) -> str:
        """Export trusted keys as JSON"""
        trusted = {
            node_id: self.node_keys[node_id].public_key
            for node_id in self.trusted_nodes
        }
        return json.dumps(trusted, indent=2)
        
    def import_trusted_keys(self, json_data: str):
        """Import trusted keys from JSON"""
        trusted = json.loads(json_data)
        for node_id, public_key in trusted.items():
            self.add_node_key(node_id, public_key, trust=True) 