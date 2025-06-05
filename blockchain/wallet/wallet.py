"""
Simple wallet implementation
"""

import os
import json
import hashlib
import secrets
import logging
from typing import Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class Wallet:
    """Simple wallet implementation"""
    address: str
    private_key: str
    public_key: str
    balance: float = 0.0
    
    @classmethod
    def create(cls) -> 'Wallet':
        """Create a new wallet"""
        # Generate private key
        private_key = secrets.token_hex(32)
        
        # Generate public key (simple hash of private key)
        public_key = hashlib.sha256(private_key.encode()).hexdigest()
        
        # Generate address (hash of public key)
        address = "LOGI" + hashlib.sha256(public_key.encode()).hexdigest()[:32]
        
        return cls(
            address=address,
            private_key=private_key,
            public_key=public_key
        )
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Wallet':
        """Create wallet from dictionary"""
        return cls(
            address=data['address'],
            private_key=data['private_key'],
            public_key=data['public_key'],
            balance=data.get('balance', 0.0)
        )
        
    def to_dict(self) -> Dict:
        """Convert wallet to dictionary"""
        return asdict(self)
        
    def sign(self, message: str) -> str:
        """Sign a message using private key"""
        # Simple signature implementation
        message_bytes = message.encode()
        signature_input = self.private_key.encode() + message_bytes
        return hashlib.sha256(signature_input).hexdigest()
        
    def verify_signature(self, message: str, signature: str) -> bool:
        """Verify a signature"""
        expected_signature = self.sign(message)
        return secrets.compare_digest(signature, expected_signature)
        
    def save(self, wallet_path: str):
        """Save wallet to file"""
        try:
            os.makedirs(os.path.dirname(wallet_path), exist_ok=True)
            with open(wallet_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save wallet: {e}")
            raise
            
    @classmethod
    def load(cls, wallet_path: str) -> Optional['Wallet']:
        """Load wallet from file"""
        try:
            with open(wallet_path, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load wallet: {e}")
            return None 