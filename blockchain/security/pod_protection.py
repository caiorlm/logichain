import time
import hashlib
import math
from typing import Dict, List, Optional
from dataclasses import dataclass
import mmh3  # MurmurHash3 for Bloom filter

@dataclass
class POD:
    contract_hash: str
    nonce: str
    timestamp: float
    location: Dict[str, float]
    driver_signature: bytes
    client_signature: bytes
    metadata: Dict

class BloomFilter:
    def __init__(self, size: int, num_hash_functions: int):
        self.size = size
        self.num_hash_functions = num_hash_functions
        self.bit_array = [False] * size
        
    def add(self, item: str):
        for seed in range(self.num_hash_functions):
            index = mmh3.hash(item, seed) % self.size
            self.bit_array[index] = True
            
    def check(self, item: str) -> bool:
        for seed in range(self.num_hash_functions):
            index = mmh3.hash(item, seed) % self.size
            if not self.bit_array[index]:
                return False
        return True

class PODProtection:
    def __init__(self):
        # Initialize Bloom filter with size for ~1M PODs with 0.01% false positive
        self.bloom = BloomFilter(size=10000000, num_hash_functions=7)
        self.used_nonces = set()  # Backup exact storage
        self.max_pod_age = 86400  # 24 hours
        
    def create_pod(
        self,
        contract_hash: str,
        location: Dict[str, float],
        driver_key: bytes,
        client_key: bytes,
        metadata: Dict = None
    ) -> POD:
        """Create a new POD with dual signatures"""
        # Generate unique nonce
        timestamp = time.time()
        nonce = self._generate_nonce(contract_hash, timestamp)
        
        # Create POD data
        pod_data = {
            "contract_hash": contract_hash,
            "nonce": nonce,
            "timestamp": timestamp,
            "location": location,
            "metadata": metadata or {}
        }
        
        # Get signatures
        message = self._get_pod_message(pod_data)
        driver_signature = self._sign_message(message, driver_key)
        client_signature = self._sign_message(message, client_key)
        
        return POD(
            contract_hash=contract_hash,
            nonce=nonce,
            timestamp=timestamp,
            location=location,
            driver_signature=driver_signature,
            client_signature=client_signature,
            metadata=metadata or {}
        )
        
    def verify_pod(
        self,
        pod: POD,
        driver_pubkey: bytes,
        client_pubkey: bytes
    ) -> bool:
        """Verify POD validity and uniqueness"""
        try:
            # Check timestamp
            if not self._verify_timestamp(pod.timestamp):
                return False
                
            # Check if POD was already used
            if self._is_pod_used(pod):
                return False
                
            # Verify signatures
            message = self._get_pod_message({
                "contract_hash": pod.contract_hash,
                "nonce": pod.nonce,
                "timestamp": pod.timestamp,
                "location": pod.location,
                "metadata": pod.metadata
            })
            
            if not self._verify_signature(
                message,
                pod.driver_signature,
                driver_pubkey
            ):
                return False
                
            if not self._verify_signature(
                message,
                pod.client_signature,
                client_pubkey
            ):
                return False
                
            # Mark POD as used
            self._mark_pod_used(pod)
            
            return True
            
        except Exception:
            return False
            
    def _generate_nonce(self, contract_hash: str, timestamp: float) -> str:
        """Generate unique nonce for POD"""
        data = f"{contract_hash}:{timestamp}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()
        
    def _verify_timestamp(self, timestamp: float) -> bool:
        """Check if timestamp is within acceptable range"""
        current_time = time.time()
        return abs(current_time - timestamp) <= self.max_pod_age
        
    def _is_pod_used(self, pod: POD) -> bool:
        """Check if POD was already used using Bloom filter"""
        pod_id = f"{pod.contract_hash}:{pod.nonce}"
        
        # Check Bloom filter first (fast negative)
        if not self.bloom.check(pod_id):
            return False
            
        # If Bloom filter positive, check exact set
        return pod_id in self.used_nonces
        
    def _mark_pod_used(self, pod: POD):
        """Mark POD as used in both Bloom filter and exact set"""
        pod_id = f"{pod.contract_hash}:{pod.nonce}"
        self.bloom.add(pod_id)
        self.used_nonces.add(pod_id)
        
    def _get_pod_message(self, pod_data: Dict) -> bytes:
        """Get message to sign/verify"""
        message = (
            f"{pod_data['contract_hash']}:"
            f"{pod_data['nonce']}:"
            f"{pod_data['timestamp']}:"
            f"{pod_data['location']}"
        )
        return message.encode()
        
    def _sign_message(self, message: bytes, private_key: bytes) -> bytes:
        """Sign message with private key"""
        import ed25519
        signing_key = ed25519.SigningKey(private_key)
        return signing_key.sign(message)
        
    def _verify_signature(
        self,
        message: bytes,
        signature: bytes,
        public_key: bytes
    ) -> bool:
        """Verify signature with public key"""
        try:
            import ed25519
            verifying_key = ed25519.VerifyingKey(public_key)
            verifying_key.verify(signature, message)
            return True
        except:
            return False 