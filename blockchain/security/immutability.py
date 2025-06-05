"""
Immutability protection for LogiChain
"""

import hashlib
import inspect
from typing import Dict, Any, Optional
from .crypto import KeyManager

class ImmutabilityGuard:
    """Guards blockchain immutability through cryptographic proofs"""
    
    def __init__(self):
        self.key_manager = KeyManager()
        self.frozen_methods = {}
        
    def freeze_method(self, obj: Any, method_name: str) -> None:
        """Freezes a method to prevent modifications"""
        if not hasattr(obj, method_name):
            raise AttributeError(f"Object has no method named {method_name}")
            
        method = getattr(obj, method_name)
        method_hash = self._calculate_method_hash(method)
        self.frozen_methods[f"{id(obj)}:{method_name}"] = method_hash
        
    def _calculate_method_hash(self, method) -> str:
        """Calculate hash of method source code"""
        source = inspect.getsource(method)
        return hashlib.sha256(source.encode()).hexdigest()
        
    def verify_method_integrity(self, obj: Any, method_name: str) -> bool:
        """Verify if a frozen method has been modified"""
        if not hasattr(obj, method_name):
            return False
            
        method = getattr(obj, method_name)
        current_hash = self._calculate_method_hash(method)
        original_hash = self.frozen_methods.get(f"{id(obj)}:{method_name}")
        
        return original_hash is not None and current_hash == original_hash
        
    def calculate_block_hash(self, block_data: Dict[str, Any]) -> str:
        """Calculate cryptographic hash of block data"""
        block_bytes = str(block_data).encode('utf-8')
        return hashlib.sha256(block_bytes).hexdigest()
        
    def verify_block_hash(self, block_hash: str, block_data: Dict[str, Any]) -> bool:
        """Verify block hash matches data"""
        calculated_hash = self.calculate_block_hash(block_data)
        return block_hash == calculated_hash
        
    def sign_block(self, block_hash: str) -> str:
        """Sign block hash with node's private key"""
        signature = self.key_manager.sign_message(block_hash.encode('utf-8'))
        return signature.hex()
        
    def verify_block_signature(self, block_hash: str, signature: str, public_key: bytes) -> bool:
        """Verify block signature with node's public key"""
        try:
            signature_bytes = bytes.fromhex(signature)
            return self.key_manager.verify_signature(
                block_hash.encode('utf-8'),
                signature_bytes,
                public_key
            )
        except (ValueError, TypeError):
            return False
            
    def create_merkle_root(self, transaction_hashes: list) -> str:
        """Create Merkle root from transaction hashes"""
        if not transaction_hashes:
            return hashlib.sha256(b'').hexdigest()
            
        def _hash_pair(hash1: str, hash2: str) -> str:
            combined = hash1 + hash2
            return hashlib.sha256(combined.encode('utf-8')).hexdigest()
            
        current_level = transaction_hashes
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                hash1 = current_level[i]
                hash2 = current_level[i + 1] if i + 1 < len(current_level) else hash1
                next_level.append(_hash_pair(hash1, hash2))
            current_level = next_level
            
        return current_level[0]
        
    def verify_merkle_proof(self, tx_hash: str, proof: list, merkle_root: str) -> bool:
        """Verify Merkle proof for transaction"""
        current_hash = tx_hash
        
        for sibling_hash in proof:
            if isinstance(sibling_hash, dict):
                position = sibling_hash.get('position', 'right')
                hash_value = sibling_hash.get('hash', '')
            else:
                position = 'right'
                hash_value = sibling_hash
                
            if position == 'right':
                current_hash = hashlib.sha256(
                    (current_hash + hash_value).encode('utf-8')
                ).hexdigest()
            else:
                current_hash = hashlib.sha256(
                    (hash_value + current_hash).encode('utf-8')
                ).hexdigest()
                
        return current_hash == merkle_root 