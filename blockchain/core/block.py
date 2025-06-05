"""
Implementação da estrutura de blocos da blockchain
"""

import hashlib
import json
import time
from typing import List, Dict, Optional
from datetime import datetime
from .transaction import Transaction

class Block:
    """Representa um bloco na blockchain"""
    
    def __init__(self, 
                 index: int,
                 timestamp: float,
                 transactions: List[Dict],
                 previous_hash: str,
                 difficulty: int = 4,
                 nonce: int = 0,
                 miner_address: Optional[str] = None,
                 mining_reward: float = 0.0):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = nonce
        self.miner_address = miner_address
        self.mining_reward = mining_reward
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calcula o hash do bloco usando SHA256"""
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'difficulty': self.difficulty,
            'nonce': self.nonce,
            'miner_address': self.miner_address,
            'mining_reward': self.mining_reward
        }, sort_keys=True)
        
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, difficulty: int) -> None:
        """Minera o bloco encontrando um nonce que satisfaz a dificuldade"""
        target = '0' * difficulty
        
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
    
    def is_valid(self) -> bool:
        """Verifica se o bloco é válido"""
        # Verifica se o hash está correto
        if self.hash != self.calculate_hash():
            return False
            
        # Verifica se a dificuldade foi atingida
        target = '0' * self.difficulty
        if self.hash[:self.difficulty] != target:
            return False
            
        return True
    
    def to_dict(self) -> Dict:
        """Converte o bloco para dicionário"""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'difficulty': self.difficulty,
            'nonce': self.nonce,
            'miner_address': self.miner_address,
            'mining_reward': self.mining_reward,
            'hash': self.hash
        }
    
    @classmethod
    def from_dict(cls, block_dict: Dict) -> 'Block':
        """Cria um bloco a partir de um dicionário"""
        block = cls(
            index=block_dict['index'],
            timestamp=block_dict['timestamp'],
            transactions=block_dict['transactions'],
            previous_hash=block_dict['previous_hash'],
            difficulty=block_dict.get('difficulty', 4),
            nonce=block_dict.get('nonce', 0),
            miner_address=block_dict.get('miner_address'),
            mining_reward=block_dict.get('mining_reward', 0.0)
        )
        block.hash = block_dict.get('hash', block.calculate_hash())
        return block
        
    @classmethod
    def from_db_row(cls, row: tuple) -> 'Block':
        """Create block from database row"""
        block = cls(
            index=row[0],  # index
            timestamp=row[1],  # timestamp
            transactions=[],  # transactions will be loaded separately
            previous_hash=row[2],  # previous_hash
            difficulty=row[3],  # difficulty
            nonce=row[4],  # nonce
            miner_address=row[5],  # miner_address
            mining_reward=row[6]  # mining_reward
        )
        block.hash = row[7]  # hash
        return block 