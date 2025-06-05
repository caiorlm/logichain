"""
LogiChain Trusted Node Quorum
Handles cryptographic voting and consensus among trusted nodes
"""

import time
import json
import hashlib
import asyncio
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from ..crypto.keys import sign_message, verify_signature

class QuorumState(Enum):
    PENDING = "pending"
    VOTING = "voting"
    APPROVED = "approved"
    REJECTED = "rejected"

@dataclass
class QuorumVote:
    """Cryptographic vote from trusted node"""
    node_id: str
    timestamp: float
    vote_type: str
    content_hash: str
    signature: str
    
    def verify(self, public_key: str) -> bool:
        """Verify vote signature"""
        content = f"{self.node_id}:{self.timestamp}:{self.vote_type}:{self.content_hash}"
        return verify_signature(content, self.signature, public_key)

class TrustedNodeQuorum:
    """Manages trusted node voting and consensus"""
    
    def __init__(
        self,
        node_id: str,
        private_key: str,
        trusted_nodes: Dict[str, str],
        min_votes: int = 3,
        vote_timeout: int = 300
    ):
        self.node_id = node_id
        self.private_key = private_key
        self.trusted_nodes = trusted_nodes
        self.min_votes = min_votes
        self.vote_timeout = vote_timeout
        
        # Voting state
        self.pending_votes: Dict[str, Dict[str, QuorumVote]] = {}
        self.vote_results: Dict[str, QuorumState] = {}
        self.vote_timestamps: Dict[str, float] = {}
        
    async def propose_vote(
        self,
        content: Dict,
        vote_type: str
    ) -> Tuple[str, bool]:
        """Propose new vote to quorum"""
        try:
            # Create content hash
            content_str = json.dumps(content, sort_keys=True)
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()
            
            # Create vote
            timestamp = time.time()
            vote = QuorumVote(
                node_id=self.node_id,
                timestamp=timestamp,
                vote_type=vote_type,
                content_hash=content_hash,
                signature=sign_message(
                    f"{self.node_id}:{timestamp}:{vote_type}:{content_hash}",
                    self.private_key
                )
            )
            
            # Initialize voting
            self.pending_votes[content_hash] = {self.node_id: vote}
            self.vote_results[content_hash] = QuorumState.VOTING
            self.vote_timestamps[content_hash] = timestamp
            
            return content_hash, True
            
        except Exception:
            return "", False
            
    def add_vote(
        self,
        content_hash: str,
        vote: QuorumVote
    ) -> bool:
        """Add vote from trusted node"""
        try:
            # Verify node is trusted
            if vote.node_id not in self.trusted_nodes:
                return False
                
            # Verify vote signature
            if not vote.verify(self.trusted_nodes[vote.node_id]):
                return False
                
            # Check vote is still active
            if content_hash not in self.vote_results:
                return False
                
            if self.vote_results[content_hash] != QuorumState.VOTING:
                return False
                
            # Check vote timeout
            current_time = time.time()
            vote_time = self.vote_timestamps[content_hash]
            if current_time - vote_time > self.vote_timeout:
                self.vote_results[content_hash] = QuorumState.REJECTED
                return False
                
            # Add vote
            if content_hash not in self.pending_votes:
                self.pending_votes[content_hash] = {}
            self.pending_votes[content_hash][vote.node_id] = vote
            
            # Check if quorum reached
            if len(self.pending_votes[content_hash]) >= self.min_votes:
                self.vote_results[content_hash] = QuorumState.APPROVED
                
            return True
            
        except Exception:
            return False
            
    def get_vote_state(self, content_hash: str) -> QuorumState:
        """Get current vote state"""
        return self.vote_results.get(content_hash, QuorumState.REJECTED)
        
    def validate_quorum(
        self,
        content_hash: str,
        required_state: QuorumState = QuorumState.APPROVED
    ) -> bool:
        """Validate quorum state"""
        try:
            # Check vote exists
            if content_hash not in self.vote_results:
                return False
                
            # Check state matches
            if self.vote_results[content_hash] != required_state:
                return False
                
            # Verify all votes
            votes = self.pending_votes[content_hash]
            valid_votes = 0
            
            for node_id, vote in votes.items():
                if node_id not in self.trusted_nodes:
                    continue
                    
                if vote.verify(self.trusted_nodes[node_id]):
                    valid_votes += 1
                    
            return valid_votes >= self.min_votes
            
        except Exception:
            return False
            
    def cleanup_old_votes(self):
        """Remove expired votes"""
        current_time = time.time()
        
        # Find expired votes
        expired = [
            content_hash
            for content_hash, timestamp in self.vote_timestamps.items()
            if current_time - timestamp > self.vote_timeout
        ]
        
        # Remove expired
        for content_hash in expired:
            if self.vote_results[content_hash] == QuorumState.VOTING:
                self.vote_results[content_hash] = QuorumState.REJECTED
                
            del self.pending_votes[content_hash]
            del self.vote_timestamps[content_hash]
            
    async def wait_for_quorum(
        self,
        content_hash: str,
        timeout: Optional[float] = None
    ) -> bool:
        """Wait for quorum to be reached"""
        try:
            start_time = time.time()
            while True:
                # Check timeout
                if timeout and time.time() - start_time > timeout:
                    return False
                    
                # Check vote state
                state = self.get_vote_state(content_hash)
                if state == QuorumState.APPROVED:
                    return True
                if state == QuorumState.REJECTED:
                    return False
                    
                # Wait and retry
                await asyncio.sleep(1)
                
        except Exception:
            return False 