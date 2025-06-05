"""
LogiChain Wallet State Manager
Handles secure balance tracking and transaction locking
"""

import time
import threading
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from ..mesh.snapshot import Transaction

@dataclass
class BalanceLock:
    """Represents a balance lock for pending transactions"""
    amount: float
    timestamp: float
    tx_hash: str
    expires_at: float

class WalletState:
    """Manages wallet state and balance tracking"""
    
    def __init__(self, address: str):
        self.address = address
        self.confirmed_transactions: Dict[str, Transaction] = {}
        self.pending_transactions: Dict[str, Transaction] = {}
        self.balance_locks: Dict[str, BalanceLock] = {}
        self._lock = threading.Lock()
        
    def get_confirmed_balance(self) -> float:
        """Get balance from confirmed transactions only"""
        balance = 0.0
        
        for tx in self.confirmed_transactions.values():
            if tx.sender_id == self.address:
                balance -= float(tx.data["amount"])
            if tx.data.get("recipient") == self.address:
                balance += float(tx.data["amount"])
                
        return balance
        
    def get_available_balance(self) -> float:
        """Get balance considering locks and pending transactions"""
        confirmed = self.get_confirmed_balance()
        
        # Subtract locked amounts
        with self._lock:
            current_time = time.time()
            locked_amount = sum(
                lock.amount
                for lock in self.balance_locks.values()
                if lock.expires_at > current_time
            )
            
        return confirmed - locked_amount
        
    def can_spend(self, amount: float) -> bool:
        """Check if wallet can spend amount"""
        return self.get_available_balance() >= amount
        
    def lock_balance(
        self,
        amount: float,
        tx_hash: str,
        lock_duration: int = 300
    ) -> bool:
        """Lock balance for pending transaction"""
        with self._lock:
            if not self.can_spend(amount):
                return False
                
            # Create lock
            lock = BalanceLock(
                amount=amount,
                timestamp=time.time(),
                tx_hash=tx_hash,
                expires_at=time.time() + lock_duration
            )
            
            self.balance_locks[tx_hash] = lock
            return True
            
    def release_lock(self, tx_hash: str):
        """Release balance lock"""
        with self._lock:
            if tx_hash in self.balance_locks:
                del self.balance_locks[tx_hash]
                
    def add_pending_transaction(self, transaction: Transaction) -> bool:
        """Add pending transaction"""
        with self._lock:
            # Validate amount
            amount = float(transaction.data["amount"])
            
            if transaction.sender_id == self.address:
                # Check and lock balance for outgoing tx
                if not self.lock_balance(amount, transaction.tx_hash):
                    return False
                    
            # Add to pending
            self.pending_transactions[transaction.tx_hash] = transaction
            return True
            
    def confirm_transaction(self, transaction: Transaction):
        """Confirm transaction and release lock"""
        with self._lock:
            # Move from pending to confirmed
            if transaction.tx_hash in self.pending_transactions:
                del self.pending_transactions[transaction.tx_hash]
            
            self.confirmed_transactions[transaction.tx_hash] = transaction
            
            # Release lock if exists
            self.release_lock(transaction.tx_hash)
            
    def cleanup_expired_locks(self):
        """Remove expired balance locks"""
        with self._lock:
            current_time = time.time()
            expired = [
                tx_hash
                for tx_hash, lock in self.balance_locks.items()
                if lock.expires_at <= current_time
            ]
            
            for tx_hash in expired:
                del self.balance_locks[tx_hash]
                
    def get_transaction_status(self, tx_hash: str) -> Optional[str]:
        """Get transaction status"""
        if tx_hash in self.confirmed_transactions:
            return "confirmed"
        if tx_hash in self.pending_transactions:
            return "pending"
        if tx_hash in self.balance_locks:
            return "locked"
        return None 