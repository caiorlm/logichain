import time
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import ed25519
from enum import Enum

class TransactionStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    SUSPICIOUS = "SUSPICIOUS"

@dataclass
class Transaction:
    tx_id: str
    sender: str
    receiver: str
    amount: float
    nonce: int
    timestamp: float
    signature: bytes
    mode: str  # "ONLINE" or "OFFLINE"
    metadata: Dict

@dataclass
class BalanceState:
    confirmed_balance: float
    pending_balance: float
    locked_amount: float
    last_nonce: int
    last_update: float

class TransactionProtection:
    def __init__(self):
        self.balances: Dict[str, BalanceState] = {}
        self.pending_transactions: Dict[str, Transaction] = {}
        self.used_nonces: Set[str] = set()  # wallet:nonce
        self.max_pending_amount = 1000.0  # Maximum amount in pending state
        self.nonce_window = 1000  # Maximum nonce difference allowed
        self.max_offline_amount = 100.0  # Maximum amount for offline transactions
        
    def validate_transaction(
        self,
        tx: Transaction,
        sender_pubkey: bytes
    ) -> bool:
        """Validate transaction and check for fraud"""
        try:
            # Verify basic transaction data
            if not self._verify_transaction_data(tx):
                return False
                
            # Verify signature
            if not self._verify_signature(tx, sender_pubkey):
                return False
                
            # Check for replay
            if self._is_replay(tx):
                return False
                
            # Verify balance
            if not self._verify_balance(tx):
                return False
                
            # Verify nonce sequence
            if not self._verify_nonce(tx):
                return False
                
            # Additional offline checks
            if tx.mode == "OFFLINE":
                if not self._verify_offline_limits(tx):
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def add_pending_transaction(
        self,
        tx: Transaction,
        sender_pubkey: bytes
    ) -> bool:
        """Add transaction to pending pool"""
        # Validate first
        if not self.validate_transaction(tx, sender_pubkey):
            return False
            
        # Update balance state
        sender_state = self._get_balance_state(tx.sender)
        sender_state.pending_balance -= tx.amount
        sender_state.locked_amount += tx.amount
        
        # Store transaction
        self.pending_transactions[tx.tx_id] = tx
        
        # Mark nonce as used
        self._mark_nonce_used(tx)
        
        return True
        
    def confirm_transaction(self, tx_id: str):
        """Confirm a pending transaction"""
        tx = self.pending_transactions.get(tx_id)
        if not tx:
            return
            
        # Update sender balance
        sender_state = self._get_balance_state(tx.sender)
        sender_state.confirmed_balance -= tx.amount
        sender_state.locked_amount -= tx.amount
        
        # Update receiver balance
        receiver_state = self._get_balance_state(tx.receiver)
        receiver_state.confirmed_balance += tx.amount
        
        # Remove from pending
        del self.pending_transactions[tx_id]
        
    def reject_transaction(self, tx_id: str):
        """Reject and cleanup a pending transaction"""
        tx = self.pending_transactions.get(tx_id)
        if not tx:
            return
            
        # Restore locked amount
        sender_state = self._get_balance_state(tx.sender)
        sender_state.pending_balance += tx.amount
        sender_state.locked_amount -= tx.amount
        
        # Remove from pending
        del self.pending_transactions[tx_id]
        
        # Keep nonce marked as used to prevent replay
        
    def _verify_transaction_data(self, tx: Transaction) -> bool:
        """Verify basic transaction data"""
        current_time = time.time()
        
        # Check amount
        if tx.amount <= 0:
            return False
            
        # Check timestamp (within 1 hour)
        if abs(current_time - tx.timestamp) > 3600:
            return False
            
        # Check sender != receiver
        if tx.sender == tx.receiver:
            return False
            
        return True
        
    def _verify_signature(
        self,
        tx: Transaction,
        sender_pubkey: bytes
    ) -> bool:
        """Verify transaction signature"""
        try:
            # Create message
            message = (
                f"{tx.sender}:{tx.receiver}:{tx.amount}:"
                f"{tx.nonce}:{tx.timestamp}:{tx.mode}"
            ).encode()
            
            # Verify
            verifying_key = ed25519.VerifyingKey(sender_pubkey)
            verifying_key.verify(tx.signature, message)
            return True
            
        except Exception:
            return False
            
    def _is_replay(self, tx: Transaction) -> bool:
        """Check if transaction is a replay attempt"""
        nonce_key = f"{tx.sender}:{tx.nonce}"
        return nonce_key in self.used_nonces
        
    def _verify_balance(self, tx: Transaction) -> bool:
        """Verify sender has sufficient balance"""
        sender_state = self._get_balance_state(tx.sender)
        
        # Check confirmed balance
        if tx.amount > sender_state.confirmed_balance:
            return False
            
        # Check pending balance
        if tx.amount > sender_state.pending_balance:
            return False
            
        # Check total pending amount
        total_pending = sender_state.locked_amount + tx.amount
        if total_pending > self.max_pending_amount:
            return False
            
        return True
        
    def _verify_nonce(self, tx: Transaction) -> bool:
        """Verify transaction nonce is valid"""
        sender_state = self._get_balance_state(tx.sender)
        
        # Nonce must be greater than last used
        if tx.nonce <= sender_state.last_nonce:
            return False
            
        # Check nonce is within acceptable window
        if tx.nonce > sender_state.last_nonce + self.nonce_window:
            return False
            
        return True
        
    def _verify_offline_limits(self, tx: Transaction) -> bool:
        """Verify offline transaction limits"""
        # Check amount limit
        if tx.amount > self.max_offline_amount:
            return False
            
        # Check pending transactions count
        sender_pending = len([
            t for t in self.pending_transactions.values()
            if t.sender == tx.sender and t.mode == "OFFLINE"
        ])
        if sender_pending >= 10:  # Max 10 pending offline tx per sender
            return False
            
        return True
        
    def _get_balance_state(self, wallet: str) -> BalanceState:
        """Get or create balance state for wallet"""
        if wallet not in self.balances:
            self.balances[wallet] = BalanceState(
                confirmed_balance=0.0,
                pending_balance=0.0,
                locked_amount=0.0,
                last_nonce=0,
                last_update=time.time()
            )
        return self.balances[wallet]
        
    def _mark_nonce_used(self, tx: Transaction):
        """Mark transaction nonce as used"""
        nonce_key = f"{tx.sender}:{tx.nonce}"
        self.used_nonces.add(nonce_key)
        
        # Update last nonce
        sender_state = self._get_balance_state(tx.sender)
        sender_state.last_nonce = max(
            sender_state.last_nonce,
            tx.nonce
        ) 