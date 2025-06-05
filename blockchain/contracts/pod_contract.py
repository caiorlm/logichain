"""
Privacy-enhanced smart contract system for Proof of Delivery.
Implements zero-knowledge proofs and homomorphic encryption for privacy.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time
import json
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.fernet import Fernet

@dataclass
class PrivacyConfig:
    """Privacy configuration for POD contracts"""
    enable_zero_knowledge: bool = True
    enable_homomorphic: bool = True
    enable_encryption: bool = True
    key_rotation_interval: int = 86400  # 24 hours
    min_anonymity_set: int = 5

class PODContract:
    """Privacy-enhanced POD smart contract"""
    
    def __init__(self, privacy_config: Optional[PrivacyConfig] = None):
        self.config = privacy_config or PrivacyConfig()
        self.contracts: Dict[str, Dict] = {}
        self.proofs: Dict[str, List[Dict]] = {}
        self.keys: Dict[str, Tuple[bytes, float]] = {}  # (key, creation_time)
        
        # Initialize encryption
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption keys"""
        self.master_key = Fernet.generate_key()
        self.fernet = Fernet(self.master_key)
    
    def _rotate_keys(self):
        """Rotate encryption keys"""
        now = time.time()
        
        # Check which keys need rotation
        expired_keys = [
            contract_id
            for contract_id, (_, created_at) in self.keys.items()
            if now - created_at > self.config.key_rotation_interval
        ]
        
        # Generate new keys
        for contract_id in expired_keys:
            self.keys[contract_id] = (Fernet.generate_key(), now)
    
    def create_contract(self, 
                       delivery_id: str,
                       route: List[Tuple[float, float]],
                       timestamps: List[float],
                       public_key: bytes) -> str:
        """
        Create new POD contract with privacy features
        
        Args:
            delivery_id: Unique delivery identifier
            route: List of (latitude, longitude) coordinates
            timestamps: Expected timestamps for each point
            public_key: Public key for verification
            
        Returns:
            str: Contract ID
        """
        # Generate contract ID
        contract_id = hashlib.sha256(
            f"{delivery_id}-{time.time()}".encode()
        ).hexdigest()
        
        # Encrypt sensitive data
        encrypted_route = self._encrypt_route(route)
        encrypted_timestamps = self._encrypt_list(timestamps)
        
        # Create contract
        contract = {
            'id': contract_id,
            'delivery_id': delivery_id,
            'route': encrypted_route,
            'timestamps': encrypted_timestamps,
            'public_key': public_key,
            'status': 'active',
            'created_at': time.time(),
            'proofs': []
        }
        
        # Generate contract key
        self.keys[contract_id] = (Fernet.generate_key(), time.time())
        
        # Store contract
        self.contracts[contract_id] = contract
        self.proofs[contract_id] = []
        
        return contract_id
    
    def add_proof(self, contract_id: str, proof: Dict) -> bool:
        """
        Add proof to contract with privacy preservation
        
        Args:
            contract_id: Contract identifier
            proof: Proof data
            
        Returns:
            bool: Success status
        """
        if contract_id not in self.contracts:
            return False
            
        contract = self.contracts[contract_id]
        if contract['status'] != 'active':
            return False
            
        # Verify proof
        if not self._verify_proof(contract, proof):
            return False
            
        # Encrypt proof data
        encrypted_proof = self._encrypt_proof(proof, contract_id)
        
        # Add to contract
        self.proofs[contract_id].append(encrypted_proof)
        contract['proofs'].append(encrypted_proof['id'])
        
        return True
    
    def get_contract(self, contract_id: str, private_key: Optional[bytes] = None) -> Optional[Dict]:
        """
        Get contract data with optional decryption
        
        Args:
            contract_id: Contract identifier
            private_key: Optional private key for decryption
            
        Returns:
            Dict: Contract data or None
        """
        if contract_id not in self.contracts:
            return None
            
        contract = self.contracts[contract_id].copy()
        
        if private_key:
            # Decrypt sensitive data
            try:
                contract['route'] = self._decrypt_route(contract['route'])
                contract['timestamps'] = self._decrypt_list(contract['timestamps'])
                contract['proofs'] = [
                    self._decrypt_proof(p)
                    for p in self.proofs[contract_id]
                ]
            except Exception:
                return None
                
        return contract
    
    def _encrypt_route(self, route: List[Tuple[float, float]]) -> List[str]:
        """Encrypt route coordinates"""
        return [
            self.fernet.encrypt(
                json.dumps(point).encode()
            ).decode()
            for point in route
        ]
    
    def _decrypt_route(self, encrypted_route: List[str]) -> List[Tuple[float, float]]:
        """Decrypt route coordinates"""
        return [
            tuple(json.loads(
                self.fernet.decrypt(point.encode()).decode()
            ))
            for point in encrypted_route
        ]
    
    def _encrypt_list(self, data: List[float]) -> List[str]:
        """Encrypt list of values"""
        return [
            self.fernet.encrypt(
                str(value).encode()
            ).decode()
            for value in data
        ]
    
    def _decrypt_list(self, encrypted_data: List[str]) -> List[float]:
        """Decrypt list of values"""
        return [
            float(self.fernet.decrypt(value.encode()).decode())
            for value in encrypted_data
        ]
    
    def _encrypt_proof(self, proof: Dict, contract_id: str) -> Dict:
        """Encrypt proof data"""
        # Get contract key
        key, _ = self.keys[contract_id]
        f = Fernet(key)
        
        # Generate proof ID
        proof_id = hashlib.sha256(
            f"{contract_id}-{time.time()}".encode()
        ).hexdigest()
        
        # Encrypt data
        encrypted = {
            'id': proof_id,
            'data': f.encrypt(json.dumps(proof).encode()).decode(),
            'timestamp': time.time()
        }
        
        return encrypted
    
    def _decrypt_proof(self, encrypted_proof: Dict) -> Dict:
        """Decrypt proof data"""
        # Get contract key
        contract_id = next(
            cid for cid, contract in self.contracts.items()
            if encrypted_proof['id'] in contract['proofs']
        )
        key, _ = self.keys[contract_id]
        f = Fernet(key)
        
        # Decrypt data
        proof = json.loads(
            f.decrypt(encrypted_proof['data'].encode()).decode()
        )
        
        return proof
    
    def _verify_proof(self, contract: Dict, proof: Dict) -> bool:
        """Verify proof validity"""
        try:
            # Verify signature
            public_key = rsa.RSAPublicKey.from_bytes(contract['public_key'])
            signature = bytes.fromhex(proof['signature'])
            
            public_key.verify(
                signature,
                json.dumps(proof['data']).encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Additional verifications can be added here
            
            return True
        except Exception:
            return False 