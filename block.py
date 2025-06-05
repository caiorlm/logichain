"""
Block structure with enhanced security features and Bitcoin-style validation
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

class InvalidBlockError(Exception):
    """Raised when block validation fails"""
    pass

@dataclass
class BlockHeader:
    """Immutable block header structure"""
    version: int = 1
    previous_hash: str
    merkle_root: str
    timestamp: float
    difficulty: int
    nonce: int
    
    def serialize(self) -> bytes:
        """Serialize header for hashing"""
        header = {
            'version': self.version,
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'timestamp': self.timestamp,
            'difficulty': self.difficulty,
            'nonce': self.nonce
        }
        return json.dumps(header, sort_keys=True).encode()

class Block:
    """Secure block implementation with Bitcoin-style validation"""
    
    def __init__(self,
                 index: int,
                 timestamp: float,
                 transactions: List[Transaction],
                 previous_hash: str,
                 difficulty: int = 4,
                 nonce: int = 0,
                 miner_address: str = "",
                 mining_reward: float = 50.0):
        
        # Validate inputs
        if not isinstance(transactions, list):
            raise InvalidBlockError("Transactions must be a list")
        if not all(isinstance(tx, Transaction) for tx in transactions):
            raise InvalidBlockError("All transactions must be Transaction objects")
        if not isinstance(previous_hash, str) or len(previous_hash) != 64:
            raise InvalidBlockError("Invalid previous hash format")
            
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = nonce
        self.miner_address = miner_address
        self.mining_reward = mining_reward
        
        # Calculate merkle root before hash
        self.merkle_root = self._calculate_merkle_root()
        
        # Create block header
        self.header = BlockHeader(
            previous_hash=previous_hash,
            merkle_root=self.merkle_root,
            timestamp=timestamp,
            difficulty=difficulty,
            nonce=nonce
        )
        
        # Calculate block hash
        self.hash = self._calculate_hash()
        
    def _calculate_hash(self) -> str:
        """Calculate double SHA-256 hash of block header (Bitcoin-style)"""
        header_bytes = self.header.serialize()
        # Double SHA-256 (Bitcoin style)
        first_hash = hashlib.sha256(header_bytes).digest()
        return hashlib.sha256(first_hash).hexdigest()
        
    def _calculate_merkle_root(self) -> str:
        """Calculate Merkle root of transactions (Bitcoin-style)"""
        if not self.transactions:
            return hashlib.sha256(b"").hexdigest()
            
        def sha256d(data: bytes) -> bytes:
            """Double SHA-256"""
            return hashlib.sha256(hashlib.sha256(data).digest()).digest()
            
        # Get transaction hashes
        tx_hashes = [bytes.fromhex(tx.tx_hash) for tx in self.transactions]
        
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
                
            new_tx_hashes = []
            for i in range(0, len(tx_hashes), 2):
                # Concatenate and double-hash
                combined = tx_hashes[i] + tx_hashes[i + 1]
                new_hash = sha256d(combined)
                new_tx_hashes.append(new_hash)
            tx_hashes = new_tx_hashes
            
        return tx_hashes[0].hex()
        
    def mine_block(self, difficulty: int = None) -> bool:
        """Mine block with proof of work"""
        if difficulty is not None:
            self.difficulty = difficulty
            self.header.difficulty = difficulty
            
        target = "0" * self.difficulty
        max_nonce = 2**32  # Standard Bitcoin nonce range
        
        for nonce in range(max_nonce):
            self.nonce = nonce
            self.header.nonce = nonce
            self.hash = self._calculate_hash()
            
            if self.hash[:self.difficulty] == target:
                return True
                
        return False
        
    def verify_proof_of_work(self) -> bool:
        """Verify block's proof of work"""
        if self.hash != self._calculate_hash():
            return False
        return self.hash[:self.difficulty] == "0" * self.difficulty
        
    def verify_transactions(self) -> bool:
        """Verify all transactions in block"""
        # 1. Verify Merkle root matches transactions
        if self._calculate_merkle_root() != self.merkle_root:
            return False
            
        # 2. Verify exactly one mining reward
        mining_rewards = [tx for tx in self.transactions if tx.tx_type == 'mining_reward']
        if len(mining_rewards) != 1:
            return False
            
        reward_tx = mining_rewards[0]
        if (reward_tx.to_address != self.miner_address or
            reward_tx.amount != self.mining_reward or
            reward_tx.from_address != "0" * 64):
            return False
            
        # 3. Verify all transaction signatures
        for tx in self.transactions:
            if tx.tx_type != 'mining_reward':
                if not tx.verify_signature():
                    return False
                    
        return True
        
    def is_valid(self) -> bool:
        """Validate entire block"""
        try:
            # 1. Check block hash matches header
            if self.hash != self._calculate_hash():
                return False
                
            # 2. Check timestamp is reasonable
            current_time = time.time()
            two_hours = 7200  # 2 hours in seconds
            if self.timestamp > current_time + two_hours:
                return False  # Block too far in future
                
            # 3. Check Merkle root matches transactions
            if self.merkle_root != self._calculate_merkle_root():
                return False
                
            # 4. Check PoW
            if not self.verify_proof_of_work():
                return False
                
            # 5. Check transactions
            if not self.verify_transactions():
                return False
                
            return True
            
        except Exception:
            return False
            
    def to_dict(self) -> Dict:
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