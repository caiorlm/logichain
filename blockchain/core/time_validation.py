"""
LogiChain Time Validation System
Handles multi-layer timestamp validation and proof of time
"""

import time
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from ..crypto.keys import sign_message, verify_signature

# Constants
MAX_TIME_DRIFT = 3600  # 1 hour
MAX_SNAPSHOT_AGE = 7200  # 2 hours
MIN_TRUSTED_NODES = 3
BLOCK_TIME_WINDOW = 300  # 5 minutes

@dataclass
class TimeProof:
    """Cryptographic proof of time"""
    timestamp: float
    node_id: str
    previous_block_hash: str
    previous_timestamp: float
    signature: str
    quorum_signatures: List[str]
    
    def verify(self, public_keys: Dict[str, str]) -> bool:
        """Verify time proof integrity"""
        try:
            # Verify base signature
            content = f"{self.timestamp}:{self.previous_block_hash}:{self.previous_timestamp}"
            if not verify_signature(content, self.signature, public_keys[self.node_id]):
                return False
                
            # Verify quorum signatures
            if len(self.quorum_signatures) < MIN_TRUSTED_NODES:
                return False
                
            # Verify each quorum signature
            for sig in self.quorum_signatures:
                node_id = sig.split(":")[0]
                signature = sig.split(":")[1]
                if not verify_signature(content, signature, public_keys[node_id]):
                    return False
                    
            return True
            
        except Exception:
            return False

class TimeValidationSystem:
    """Manages time validation across the network"""
    
    def __init__(
        self,
        node_id: str,
        private_key: str,
        trusted_nodes: Dict[str, str],
        genesis_time: float
    ):
        self.node_id = node_id
        self.private_key = private_key
        self.trusted_nodes = trusted_nodes
        self.genesis_time = genesis_time
        self.time_proofs: Dict[str, TimeProof] = {}
        self.state_sequence: Dict[str, float] = {}
        self.quorum_votes: Dict[str, Set[str]] = {}
        
    def validate_timestamp(
        self,
        timestamp: float,
        block_hash: str,
        previous_hash: str
    ) -> Tuple[bool, str]:
        """Multi-layer timestamp validation"""
        try:
            current_time = time.time()
            
            # Layer 1: Basic drift check
            if abs(timestamp - current_time) > MAX_TIME_DRIFT:
                return False, "Timestamp drift too large"
                
            # Layer 2: Genesis time check
            if timestamp < self.genesis_time:
                return False, "Pre-genesis timestamp"
                
            # Layer 3: Previous block check
            if previous_hash in self.state_sequence:
                prev_time = self.state_sequence[previous_hash]
                if timestamp <= prev_time:
                    return False, "Invalid timestamp sequence"
                if timestamp - prev_time > BLOCK_TIME_WINDOW:
                    return False, "Block time window exceeded"
                    
            # Layer 4: Quorum validation
            if not self._validate_quorum(timestamp, block_hash):
                return False, "Insufficient quorum validation"
                
            return True, "Valid timestamp"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
            
    def create_time_proof(
        self,
        timestamp: float,
        block_hash: str,
        previous_hash: str
    ) -> Optional[TimeProof]:
        """Create cryptographic proof of time"""
        try:
            # Get previous timestamp
            prev_time = self.state_sequence.get(previous_hash, self.genesis_time)
            
            # Create base signature
            content = f"{timestamp}:{previous_hash}:{prev_time}"
            signature = sign_message(content, self.private_key)
            
            # Create proof
            proof = TimeProof(
                timestamp=timestamp,
                node_id=self.node_id,
                previous_block_hash=previous_hash,
                previous_timestamp=prev_time,
                signature=signature,
                quorum_signatures=[]
            )
            
            # Store proof
            self.time_proofs[block_hash] = proof
            return proof
            
        except Exception:
            return None
            
    def validate_state_sequence(
        self,
        block_hash: str,
        timestamp: float,
        previous_hash: str
    ) -> bool:
        """Validate state sequence continuity"""
        try:
            # Must have previous state (except genesis)
            if previous_hash != "genesis" and previous_hash not in self.state_sequence:
                return False
                
            # Check sequence
            if previous_hash in self.state_sequence:
                prev_time = self.state_sequence[previous_hash]
                
                # Validate chronological order
                if timestamp <= prev_time:
                    return False
                    
                # Validate time window
                if timestamp - prev_time > BLOCK_TIME_WINDOW:
                    return False
                    
            # Add to sequence
            self.state_sequence[block_hash] = timestamp
            return True
            
        except Exception:
            return False
            
    def _validate_quorum(self, timestamp: float, block_hash: str) -> bool:
        """Validate timestamp with trusted node quorum"""
        try:
            # Get quorum votes
            votes = self.quorum_votes.get(block_hash, set())
            
            # Check minimum votes
            if len(votes) < MIN_TRUSTED_NODES:
                return False
                
            # Verify each vote
            valid_votes = 0
            for vote in votes:
                node_id, signature = vote.split(":")
                
                # Skip untrusted nodes
                if node_id not in self.trusted_nodes:
                    continue
                    
                # Verify signature
                content = f"{timestamp}:{block_hash}"
                if verify_signature(content, signature, self.trusted_nodes[node_id]):
                    valid_votes += 1
                    
            return valid_votes >= MIN_TRUSTED_NODES
            
        except Exception:
            return False
            
    def add_quorum_vote(
        self,
        node_id: str,
        block_hash: str,
        timestamp: float,
        signature: str
    ) -> bool:
        """Add trusted node vote"""
        try:
            # Verify node is trusted
            if node_id not in self.trusted_nodes:
                return False
                
            # Verify signature
            content = f"{timestamp}:{block_hash}"
            if not verify_signature(content, signature, self.trusted_nodes[node_id]):
                return False
                
            # Add vote
            if block_hash not in self.quorum_votes:
                self.quorum_votes[block_hash] = set()
            self.quorum_votes[block_hash].add(f"{node_id}:{signature}")
            
            return True
            
        except Exception:
            return False
            
    def cleanup_old_proofs(self):
        """Remove old time proofs"""
        current_time = time.time()
        
        # Remove old proofs
        old_proofs = [
            block_hash
            for block_hash, proof in self.time_proofs.items()
            if current_time - proof.timestamp > MAX_SNAPSHOT_AGE
        ]
        
        for block_hash in old_proofs:
            del self.time_proofs[block_hash]
            
        # Remove old votes
        old_votes = [
            block_hash
            for block_hash in self.quorum_votes
            if block_hash not in self.time_proofs
        ]
        
        for block_hash in old_votes:
            del self.quorum_votes[block_hash] 