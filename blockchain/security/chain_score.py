import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import hashlib
import ed25519

@dataclass
class SignedClock:
    timestamp: float
    node_id: str
    signature: bytes
    mesh_validators: List[str]

@dataclass
class ChainScore:
    total_score: float
    latency_penalty: float
    mesh_score: float
    quorum_score: float

class ChainScoreValidator:
    def __init__(self):
        self.max_acceptable_latency = 3600  # 1 hour
        self.min_mesh_validators = 2
        self.latency_penalty_factor = 0.1
        self.mesh_weight = 0.4
        self.quorum_weight = 0.6
        
    def validate_signed_clock(
        self,
        clock: SignedClock,
        public_key: bytes
    ) -> bool:
        """Validate a signed timestamp"""
        try:
            # Check timestamp freshness
            current_time = time.time()
            if abs(current_time - clock.timestamp) > self.max_acceptable_latency:
                return False
                
            # Check mesh validators
            if len(clock.mesh_validators) < self.min_mesh_validators:
                return False
                
            # Verify signature
            message = f"{clock.timestamp}:{clock.node_id}".encode()
            verifying_key = ed25519.VerifyingKey(public_key)
            verifying_key.verify(clock.signature, message)
            
            return True
            
        except Exception:
            return False
            
    def calculate_chain_score(
        self,
        blocks: List[Dict],
        current_time: float
    ) -> ChainScore:
        """Calculate score for a chain considering latency and mesh proofs"""
        total_latency = 0
        total_mesh_validators = 0
        total_quorum_votes = 0
        
        for block in blocks:
            # Calculate latency penalty
            block_time = block.get('timestamp', 0)
            latency = current_time - block_time
            latency_penalty = max(0, latency * self.latency_penalty_factor)
            total_latency += latency_penalty
            
            # Count mesh validators
            mesh_proof = block.get('mesh_proof', {})
            validators = mesh_proof.get('validators', [])
            total_mesh_validators += len(validators)
            
            # Count quorum votes
            quorum = block.get('quorum', {})
            votes = quorum.get('votes', [])
            total_quorum_votes += len(votes)
            
        # Calculate scores
        mesh_score = min(1.0, total_mesh_validators / (len(blocks) * self.min_mesh_validators))
        quorum_score = min(1.0, total_quorum_votes / (len(blocks) * 3))  # Assume min 3 votes needed
        
        # Calculate total score
        base_score = 1.0
        latency_penalty = min(1.0, total_latency / len(blocks))
        weighted_score = (
            (mesh_score * self.mesh_weight) +
            (quorum_score * self.quorum_weight)
        )
        
        total_score = base_score * (1 - latency_penalty) * weighted_score
        
        return ChainScore(
            total_score=total_score,
            latency_penalty=latency_penalty,
            mesh_score=mesh_score,
            quorum_score=quorum_score
        )
        
    def is_chain_suspicious(self, score: ChainScore) -> bool:
        """Check if chain score indicates suspicious behavior"""
        return (
            score.total_score < 0.6 or
            score.latency_penalty > 0.3 or
            score.mesh_score < 0.5 or
            score.quorum_score < 0.5
        )
        
class MeshProofManager:
    def __init__(self):
        self.required_validators = 2
        self.max_hop_distance = 3
        
    def create_mesh_proof(
        self,
        node_id: str,
        validators: List[str],
        hop_count: int,
        timestamp: float,
        signatures: List[bytes]
    ) -> Dict:
        """Create a mesh proof with required validators"""
        if len(validators) < self.required_validators:
            raise ValueError("Insufficient validators")
            
        if hop_count > self.max_hop_distance:
            raise ValueError("Hop distance too large")
            
        proof_data = {
            "node_id": node_id,
            "validators": validators,
            "hop_count": hop_count,
            "timestamp": timestamp,
            "signatures": [sig.hex() for sig in signatures],
            "proof_hash": self._calculate_proof_hash(
                node_id, validators, timestamp
            )
        }
        
        return proof_data
        
    def verify_mesh_proof(self, proof: Dict) -> bool:
        """Verify a mesh proof is valid"""
        try:
            # Check required fields
            required_fields = [
                "node_id", "validators", "hop_count",
                "timestamp", "signatures", "proof_hash"
            ]
            if not all(field in proof for field in required_fields):
                return False
                
            # Verify validator count
            if len(proof["validators"]) < self.required_validators:
                return False
                
            # Verify hop count
            if proof["hop_count"] > self.max_hop_distance:
                return False
                
            # Verify timestamp
            if abs(time.time() - proof["timestamp"]) > 3600:
                return False
                
            # Verify proof hash
            calculated_hash = self._calculate_proof_hash(
                proof["node_id"],
                proof["validators"],
                proof["timestamp"]
            )
            if calculated_hash != proof["proof_hash"]:
                return False
                
            return True
            
        except Exception:
            return False
            
    def _calculate_proof_hash(
        self,
        node_id: str,
        validators: List[str],
        timestamp: float
    ) -> str:
        """Calculate hash of proof data"""
        data = f"{node_id}:{','.join(validators)}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest() 