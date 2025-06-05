"""
Transaction implementation
"""

from typing import Optional
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives.asymmetric import ed25519

@dataclass
class Transaction:
    tx_hash: str
    tx_type: str  # 'transfer' or 'mining_reward'
    from_address: str
    to_address: str
    amount: float
    timestamp: float
    signature: Optional[str] = None
    public_key: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)
        
    @staticmethod
    def verify_signature(transaction_data: str, signature: bytes, public_key: bytes) -> bool:
        """Verify transaction signature"""
        try:
            public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
            public_key_obj.verify(signature, transaction_data.encode())
            return True
        except Exception:
            return False 