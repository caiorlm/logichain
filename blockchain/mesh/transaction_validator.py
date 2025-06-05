"""
LogiChain Transaction Validator
Handles comprehensive transaction validation
"""

import time
import hashlib
import logging
from typing import Dict, Optional, Set
from .snapshot import Transaction
from ..crypto.keys import verify_signature

logger = logging.getLogger(__name__)

class TransactionValidator:
    """Handles comprehensive transaction validation"""
    
    def __init__(self):
        self.processed_txs: Set[str] = set()
        self.max_timestamp_drift = 300  # 5 minutes
        
    def validate_transaction(
        self,
        transaction: Transaction,
        public_key: Optional[str] = None
    ) -> bool:
        """
        Validate transaction integrity and authenticity
        Returns True if transaction is valid
        """
        try:
            # Check required fields
            if not self._validate_required_fields(transaction):
                logger.error(f"Missing required fields: {transaction.tx_hash}")
                return False
                
            # Validate timestamps
            if not self._validate_timestamps(transaction):
                logger.error(f"Invalid timestamps: {transaction.tx_hash}")
                return False
                
            # Check for duplicates
            if not self._check_duplicate(transaction):
                logger.error(f"Duplicate transaction: {transaction.tx_hash}")
                return False
                
            # Validate hash
            if not self._validate_hash(transaction):
                logger.error(f"Invalid hash: {transaction.tx_hash}")
                return False
                
            # Validate signature if public key provided
            if public_key and not self._validate_signature(transaction, public_key):
                logger.error(f"Invalid signature: {transaction.tx_hash}")
                return False
                
            # Add to processed set
            self.processed_txs.add(transaction.tx_hash)
            return True
            
        except Exception as e:
            logger.error(f"Error validating transaction: {str(e)}")
            return False
            
    def _validate_required_fields(self, transaction: Transaction) -> bool:
        """Validate presence of required fields"""
        required_fields = [
            "tx_hash",
            "sender_id",
            "original_timestamp",
            "origin_node",
            "signature",
            "sync_path",
            "data"
        ]
        
        tx_dict = transaction.to_dict()
        return all(field in tx_dict for field in required_fields)
        
    def _validate_timestamps(self, transaction: Transaction) -> bool:
        """Validate transaction timestamps"""
        current_time = time.time()
        
        # Check original timestamp
        if transaction.original_timestamp > current_time + self.max_timestamp_drift:
            return False
            
        # Check sync timestamp if exists
        if transaction.sync_timestamp:
            if transaction.sync_timestamp < transaction.original_timestamp:
                return False
            if transaction.sync_timestamp > current_time + self.max_timestamp_drift:
                return False
                
        return True
        
    def _check_duplicate(self, transaction: Transaction) -> bool:
        """Check if transaction is duplicate"""
        return transaction.tx_hash not in self.processed_txs
        
    def _validate_hash(self, transaction: Transaction) -> bool:
        """Validate transaction hash matches content"""
        # Create content for hashing
        content = {
            "sender_id": transaction.sender_id,
            "original_timestamp": transaction.original_timestamp,
            "origin_node": transaction.origin_node,
            "data": transaction.data
        }
        
        # Generate hash
        content_str = str(sorted(content.items()))
        calculated_hash = hashlib.sha256(content_str.encode()).hexdigest()
        
        return calculated_hash == transaction.tx_hash
        
    def _validate_signature(self, transaction: Transaction, public_key: str) -> bool:
        """Validate transaction signature"""
        return verify_signature(
            transaction.tx_hash,
            transaction.signature,
            public_key
        )
        
    def clear_processed(self):
        """Clear set of processed transactions"""
        self.processed_txs.clear()
        
    def set_timestamp_drift(self, max_drift: int):
        """Set maximum allowed timestamp drift in seconds"""
        self.max_timestamp_drift = max_drift 