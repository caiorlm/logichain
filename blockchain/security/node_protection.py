import time
import os
import hashlib
from typing import Dict, List, Optional, Tuple
import ed25519
from dataclasses import dataclass

@dataclass
class Challenge:
    challenge_id: str
    node_id: str
    timestamp: float
    nonce: bytes
    signature: bytes

@dataclass
class Response:
    challenge_id: str
    node_id: str
    timestamp: float
    proof: bytes
    signature: bytes

class NodeProtection:
    def __init__(self):
        self.challenge_timeout = 30  # seconds
        self.active_challenges: Dict[str, Challenge] = {}
        self.verified_nodes: Dict[str, float] = {}  # node_id -> last_verified
        self.verification_cache_time = 3600  # 1 hour
        
    def create_challenge(
        self,
        target_node_id: str,
        private_key: bytes
    ) -> Challenge:
        """Create a challenge for node verification"""
        # Generate random nonce
        nonce = os.urandom(32)
        
        # Create challenge ID
        challenge_id = hashlib.sha256(
            f"{target_node_id}:{time.time()}:{nonce.hex()}".encode()
        ).hexdigest()
        
        # Create challenge message
        message = self._get_challenge_message(
            challenge_id,
            target_node_id,
            time.time(),
            nonce
        )
        
        # Sign challenge
        signing_key = ed25519.SigningKey(private_key)
        signature = signing_key.sign(message)
        
        # Create challenge object
        challenge = Challenge(
            challenge_id=challenge_id,
            node_id=target_node_id,
            timestamp=time.time(),
            nonce=nonce,
            signature=signature
        )
        
        # Store active challenge
        self.active_challenges[challenge_id] = challenge
        
        return challenge
        
    def verify_response(
        self,
        response: Response,
        public_key: bytes
    ) -> bool:
        """Verify node response to challenge"""
        try:
            # Get original challenge
            challenge = self.active_challenges.get(response.challenge_id)
            if not challenge:
                return False
                
            # Check timeout
            if time.time() - challenge.timestamp > self.challenge_timeout:
                return False
                
            # Verify node ID matches
            if response.node_id != challenge.node_id:
                return False
                
            # Verify response signature
            message = self._get_response_message(
                response.challenge_id,
                response.node_id,
                response.timestamp,
                response.proof
            )
            
            verifying_key = ed25519.VerifyingKey(public_key)
            try:
                verifying_key.verify(response.signature, message)
            except:
                return False
                
            # Verify proof matches challenge
            if not self._verify_proof(challenge.nonce, response.proof):
                return False
                
            # Mark node as verified
            self.verified_nodes[response.node_id] = time.time()
            
            # Cleanup challenge
            del self.active_challenges[response.challenge_id]
            
            return True
            
        except Exception:
            return False
            
    def create_response(
        self,
        challenge: Challenge,
        node_id: str,
        private_key: bytes
    ) -> Response:
        """Create response to a challenge"""
        # Generate proof from challenge nonce
        proof = self._generate_proof(challenge.nonce)
        
        # Create response message
        message = self._get_response_message(
            challenge.challenge_id,
            node_id,
            time.time(),
            proof
        )
        
        # Sign response
        signing_key = ed25519.SigningKey(private_key)
        signature = signing_key.sign(message)
        
        return Response(
            challenge_id=challenge.challenge_id,
            node_id=node_id,
            timestamp=time.time(),
            proof=proof,
            signature=signature
        )
        
    def is_node_verified(self, node_id: str) -> bool:
        """Check if node was recently verified"""
        last_verified = self.verified_nodes.get(node_id, 0)
        return time.time() - last_verified <= self.verification_cache_time
        
    def _get_challenge_message(
        self,
        challenge_id: str,
        node_id: str,
        timestamp: float,
        nonce: bytes
    ) -> bytes:
        """Get message to sign for challenge"""
        return f"{challenge_id}:{node_id}:{timestamp}:{nonce.hex()}".encode()
        
    def _get_response_message(
        self,
        challenge_id: str,
        node_id: str,
        timestamp: float,
        proof: bytes
    ) -> bytes:
        """Get message to sign for response"""
        return f"{challenge_id}:{node_id}:{timestamp}:{proof.hex()}".encode()
        
    def _generate_proof(self, nonce: bytes) -> bytes:
        """Generate proof from challenge nonce"""
        # Simple proof: double hash of nonce
        return hashlib.sha256(
            hashlib.sha256(nonce).digest()
        ).digest()
        
    def _verify_proof(self, nonce: bytes, proof: bytes) -> bool:
        """Verify proof matches challenge nonce"""
        expected_proof = self._generate_proof(nonce)
        return proof == expected_proof
        
    def cleanup_expired(self):
        """Clean up expired challenges and verifications"""
        current_time = time.time()
        
        # Clean expired challenges
        expired_challenges = [
            cid for cid, c in self.active_challenges.items()
            if current_time - c.timestamp > self.challenge_timeout
        ]
        for cid in expired_challenges:
            del self.active_challenges[cid]
            
        # Clean expired verifications
        expired_nodes = [
            nid for nid, t in self.verified_nodes.items()
            if current_time - t > self.verification_cache_time
        ]
        for nid in expired_nodes:
            del self.verified_nodes[nid] 