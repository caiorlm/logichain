"""
LogiChain Sync Acknowledgment
Handles signed sync acknowledgments and verification
"""

import time
import json
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass
from ..crypto.keys import sign_message, verify_signature

@dataclass
class SyncAck:
    """Represents a signed sync acknowledgment"""
    timestamp: float
    node_id: str
    merged_state_hash: str
    old_state_hash: str
    new_state_hash: str
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "node_id": self.node_id,
            "merged_state_hash": self.merged_state_hash,
            "old_state_hash": self.old_state_hash,
            "new_state_hash": self.new_state_hash,
            "signature": self.signature
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'SyncAck':
        return cls(**data)

class SyncAckManager:
    """Manages sync acknowledgments"""
    
    def __init__(self, node_id: str, private_key: str):
        self.node_id = node_id
        self.private_key = private_key
        self.pending_acks: Dict[str, SyncAck] = {}
        
    def create_ack(
        self,
        merged_state_hash: str,
        old_state_hash: str,
        new_state_hash: str
    ) -> SyncAck:
        """Create signed acknowledgment"""
        # Create ACK
        ack = SyncAck(
            timestamp=time.time(),
            node_id=self.node_id,
            merged_state_hash=merged_state_hash,
            old_state_hash=old_state_hash,
            new_state_hash=new_state_hash
        )
        
        # Sign ACK
        content = json.dumps(
            {k: v for k, v in ack.to_dict().items() if k != "signature"},
            sort_keys=True
        )
        ack.signature = sign_message(content, self.private_key)
        
        # Store pending
        self.pending_acks[merged_state_hash] = ack
        return ack
        
    def verify_ack(
        self,
        ack: SyncAck,
        public_key: str,
        max_age: int = 300
    ) -> bool:
        """Verify acknowledgment signature and freshness"""
        try:
            # Check timestamp
            if time.time() - ack.timestamp > max_age:
                return False
                
            # Verify signature
            content = json.dumps(
                {k: v for k, v in ack.to_dict().items() if k != "signature"},
                sort_keys=True
            )
            if not verify_signature(content, ack.signature, public_key):
                return False
                
            return True
            
        except Exception:
            return False
            
    def complete_sync(
        self,
        merged_state_hash: str,
        peer_ack: SyncAck
    ) -> bool:
        """Complete sync with peer acknowledgment"""
        # Get our pending ACK
        our_ack = self.pending_acks.get(merged_state_hash)
        if not our_ack:
            return False
            
        # Verify hashes match
        if our_ack.merged_state_hash != peer_ack.merged_state_hash:
            return False
            
        # Verify old/new state consistency
        if (our_ack.old_state_hash != peer_ack.old_state_hash or
            our_ack.new_state_hash != peer_ack.new_state_hash):
            return False
            
        # Remove pending
        del self.pending_acks[merged_state_hash]
        return True
        
    def cleanup_expired(self, max_age: int = 300):
        """Remove expired pending ACKs"""
        current_time = time.time()
        expired = [
            state_hash
            for state_hash, ack in self.pending_acks.items()
            if current_time - ack.timestamp > max_age
        ]
        
        for state_hash in expired:
            del self.pending_acks[state_hash] 