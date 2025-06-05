"""
LogiChain Transaction Pool
"""

from typing import Dict, List, Optional
import threading
from .transaction import Transaction, TransactionPriority

class TransactionPool:
    """Manages pending transactions"""
    
    def __init__(self, max_pool_size: int = 10000):
        self.transactions: Dict[str, Transaction] = {}
        self.max_pool_size = max_pool_size
        self.lock = threading.Lock()
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to pool"""
        if self.is_full():
            return False
            
        with self.lock:
            if transaction.hash in self.transactions:
                return False
                
            self.transactions[transaction.hash] = transaction
            return True
            
    def remove_transaction(self, tx_hash: str) -> None:
        """Remove transaction from pool"""
        with self.lock:
            if tx_hash in self.transactions:
                del self.transactions[tx_hash]
                
    def get_transactions(self, limit: Optional[int] = None) -> List[Transaction]:
        """
        Get transactions from pool, sorted by priority.
        If limit is specified, returns at most that many transactions.
        """
        with self.lock:
            # Sort by priority
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda tx: tx.priority.value,
                reverse=True
            )
            
            if limit:
                return sorted_txs[:limit]
            return sorted_txs
            
    def clear(self) -> None:
        """Clear all transactions from pool"""
        with self.lock:
            self.transactions.clear()
            
    def contains(self, tx_hash: str) -> bool:
        """Check if transaction is in pool"""
        return tx_hash in self.transactions
        
    def get_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """Get specific transaction from pool"""
        return self.transactions.get(tx_hash)
        
    def size(self) -> int:
        """Return current size of pool"""
        return len(self.transactions)
        
    def is_full(self) -> bool:
        """Check if pool is full"""
        return self.size() >= self.max_pool_size 