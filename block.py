"""
Block structure with enhanced security features
"""

import hashlib
import json
import time
from typing import List, Dict, Optional
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from dataclasses import dataclass, asdict
from database_manager import DatabaseManager
from transaction import Transaction

@dataclass
class Transaction:
    """Transaction structure"""
    tx_hash: str
    tx_type: str
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

class Block:
    """Secure block implementation"""
    
    def __init__(self,
                 index: int,
                 timestamp: float,
                 transactions: List[Transaction],
                 previous_hash: str,
                 difficulty: int = 4,
                 nonce: int = 0,
                 miner_address: str = "",
                 mining_reward: float = 50.0):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = nonce
        self.miner_address = miner_address
        self.mining_reward = mining_reward
        self.merkle_root = self._calculate_merkle_root()
        self.hash = self._calculate_hash()
        self._db = DatabaseManager()
        
    def _calculate_hash(self) -> str:
        """Calculate double SHA-256 hash of block header"""
        block_header = {
            'index': self.index,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'previous_hash': self.previous_hash,
            'difficulty': self.difficulty,
            'nonce': self.nonce
        }
        header_string = json.dumps(block_header, sort_keys=True)
        
        # Double SHA-256 (Bitcoin style)
        first_hash = hashlib.sha256(header_string.encode()).digest()
        return hashlib.sha256(first_hash).hexdigest()
        
    def _calculate_merkle_root(self) -> str:
        """Calculate Merkle root of transactions"""
        if not self.transactions:
            return hashlib.sha256("".encode()).hexdigest()
            
        tx_hashes = [tx.tx_hash for tx in self.transactions]
        
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
                
            new_tx_hashes = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_tx_hashes.append(new_hash)
            tx_hashes = new_tx_hashes
            
        return tx_hashes[0]
        
    def mine_block(self, difficulty: int = None) -> bool:
        """Mine block with proof of work"""
        if difficulty is not None:
            self.difficulty = difficulty
            
        target = "0" * self.difficulty
        
        while self.hash[:self.difficulty] != target:
            self.nonce += 1
            self.hash = self._calculate_hash()
            
        return True
        
    def verify_proof_of_work(self) -> bool:
        """Verify block's proof of work"""
        return self.hash[:self.difficulty] == "0" * self.difficulty
        
    def verify_transactions(self) -> bool:
        """Verify all transactions in block"""
        # Verify Merkle root
        if self._calculate_merkle_root() != self.merkle_root:
            return False
            
        # Verify mining reward (should be exactly one)
        mining_rewards = [tx for tx in self.transactions if tx.tx_type == 'mining_reward']
        if len(mining_rewards) != 1:
            return False
            
        reward_tx = mining_rewards[0]
        if (reward_tx.to_address != self.miner_address or
            reward_tx.amount != self.mining_reward or
            reward_tx.from_address != "0" * 64):
            return False
            
        return True
        
    def save(self, atomic: bool = True) -> bool:
        """Save block to database"""
        return self._db.save_block(self, atomic)
        
    @classmethod
    def get_block(cls, block_hash: str) -> Optional['Block']:
        """Get block from database by hash"""
        db = DatabaseManager()
        return db.get_block(block_hash)
        
    @classmethod
    def get_latest_block(cls) -> Optional['Block']:
        """Get latest confirmed block from database"""
        db = DatabaseManager()
        return db.get_latest_block()
        
    def to_dict(self):
        """Convert block to dictionary"""
        return {
            'hash': self.hash,
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'difficulty': self.difficulty,
            'nonce': self.nonce,
            'miner_address': self.miner_address,
            'mining_reward': self.mining_reward
        }
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to block"""
        # Verify transaction signature if not mining reward
        if transaction.tx_type != 'mining_reward':
            if not transaction.signature or not transaction.public_key:
                return False
                
            # Verify signature
            tx_data = json.dumps(transaction.to_dict(), sort_keys=True)
            if not Transaction.verify_signature(
                tx_data,
                bytes.fromhex(transaction.signature),
                bytes.fromhex(transaction.public_key)
            ):
                return False
                
        self.transactions.append(transaction)
        self.merkle_root = self._calculate_merkle_root()
        self.hash = self._calculate_hash()
        return True
        
    def is_valid(self) -> bool:
        """Validate entire block"""
        # 1. Check block hash
        if self.hash != self._calculate_hash():
            return False
            
        # 2. Check Merkle root
        if self.merkle_root != self._calculate_merkle_root():
            return False
            
        # 3. Check PoW
        if not self.verify_proof_of_work():
            return False
            
        # 4. Check transactions
        if not self.verify_transactions():
            return False
            
        return True
        
    @staticmethod
    def create_genesis_block() -> 'Block':
        """Create genesis block"""
        timestamp = time.time()
        genesis_tx = Transaction(
            tx_hash="0" * 64,
            tx_type="genesis",
            from_address="0" * 64,
            to_address="0" * 64,
            amount=0,
            timestamp=timestamp
        )
        
        return Block(
            index=0,
            timestamp=timestamp,
            transactions=[genesis_tx],
            previous_hash="0" * 64,
            difficulty=4,
            nonce=0,
            miner_address="0" * 64,
            mining_reward=0
        )
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Block':
        """Create block from dictionary"""
        transactions = [
            Transaction(**tx_data)
            for tx_data in data['transactions']
        ]
        
        return cls(
            index=data['index'],
            timestamp=data['timestamp'],
            transactions=transactions,
            previous_hash=data['previous_hash'],
            difficulty=data['difficulty'],
            nonce=data['nonce'],
            miner_address=data.get('miner_address', ""),
            mining_reward=data.get('mining_reward', 50.0)
        ) 