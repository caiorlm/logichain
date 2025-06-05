"""
LogiChain Transaction System
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import time
import hashlib
import json
from enum import Enum
import logging
from datetime import datetime
import random

class TransactionType(Enum):
    TRANSFER = "transfer"
    CONTRACT = "contract"
    DELIVERY = "delivery"
    MINING = "mining"
    REPUTATION = "reputation"

class TransactionPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Transaction:
    def __init__(self, from_address: str, to_address: str, amount: float, timestamp: Optional[float] = None, fee: float = 0.001):
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.timestamp = timestamp or time.time()
        self.fee = fee
        self.hash = self.calculate_hash()
        
    def calculate_hash(self) -> str:
        """Calculate transaction hash"""
        tx_string = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{self.fee}"
        return hashlib.sha256(tx_string.encode()).hexdigest()
        
    def to_dict(self) -> dict:
        """Convert transaction to dictionary"""
        return {
            'hash': self.hash,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'amount': self.amount,
            'timestamp': self.timestamp,
            'fee': self.fee
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        """Create transaction from dictionary"""
        tx = cls(
            from_address=data['from_address'],
            to_address=data['to_address'],
            amount=data['amount'],
            timestamp=data['timestamp'],
            fee=data.get('fee', 0.001)
        )
        tx.hash = data['hash']
        return tx
        
    @classmethod
    def from_db_row(cls, row: tuple) -> 'Transaction':
        """Create transaction from database row"""
        tx = cls(
            from_address=row[2],  # from_address
            to_address=row[3],  # to_address
            amount=row[4],  # amount
            timestamp=row[6],  # timestamp
            fee=row[5]  # fee
        )
        tx.hash = row[0]  # tx_hash
        return tx

class TransactionPool:
    """Pool de transações pendentes"""
    
    def __init__(self, max_size: int = 5000):
        self.transactions = {}  # hash -> Transaction
        self.max_size = max_size
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Adiciona transação ao pool"""
        if len(self.transactions) >= self.max_size:
            return False
            
        tx_hash = transaction.hash
        if tx_hash in self.transactions:
            return False
            
        self.transactions[tx_hash] = transaction
        return True
        
    def remove_transaction(self, tx_hash: str):
        """Remove transação do pool"""
        if tx_hash in self.transactions:
            del self.transactions[tx_hash]
            
    def get_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """Retorna transação por hash"""
        return self.transactions.get(tx_hash)
        
    def get_all_transactions(self) -> Dict[str, Transaction]:
        """Retorna todas transações"""
        return self.transactions.copy()
        
    def clear(self):
        """Limpa pool"""
        self.transactions.clear()
        
    def get_stats(self) -> Dict:
        """Retorna estatísticas do pool"""
        return {
            'total_transactions': len(self.transactions),
            'max_size': self.max_size,
            'memory_usage': len(json.dumps(self.transactions))
        } 