"""
Mempool manager with robust transaction validation and synchronization
"""

import time
import logging
import sqlite3
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from ..core.transaction import Transaction
from ..core.block import Block
from ..consensus.pow_consensus import PoWConsensus

logger = logging.getLogger(__name__)

@dataclass
class MempoolTransaction:
    """Extended transaction info for mempool"""
    transaction: Transaction
    received_time: float
    last_seen: float
    fee_per_byte: float
    size: int
    in_blocks: Set[str]  # block hashes that included this tx

class MempoolManager:
    """Manages transaction mempool with robust validation"""
    
    def __init__(self, db_path: str = "data/mempool.db"):
        self.db_path = db_path
        self.mempool: Dict[str, MempoolTransaction] = {}
        self.orphan_txs: Dict[str, Transaction] = {}
        self.processing_blocks: Set[str] = set()
        self.consensus = PoWConsensus()
        self._init_database()
        
    def _init_database(self):
        """Initialize mempool database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mempool (
                    tx_hash TEXT PRIMARY KEY,
                    raw_tx BLOB NOT NULL,
                    received_time REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    fee_per_byte REAL NOT NULL,
                    size INTEGER NOT NULL
                )
            """)
            
    def add_transaction(self, transaction: Transaction, validate: bool = True) -> bool:
        """Add transaction to mempool with validation"""
        try:
            tx_hash = transaction.hash
            
            # Skip if already in mempool
            if tx_hash in self.mempool:
                self.mempool[tx_hash].last_seen = time.time()
                return True
                
            # Skip if already in blockchain
            if self.consensus.is_tx_in_chain(tx_hash):
                return False
                
            if validate:
                # Basic validation
                if not transaction.verify_signature():
                    logger.warning(f"Invalid signature for tx {tx_hash}")
                    return False
                    
                # Check nonce
                if not self.consensus.verify_tx_nonce(transaction):
                    logger.warning(f"Invalid nonce for tx {tx_hash}")
                    return False
                    
                # Check balance
                if not self.consensus.verify_tx_balance(transaction):
                    logger.warning(f"Insufficient balance for tx {tx_hash}")
                    return False
                    
                # Check for double-spend in mempool
                if self._is_double_spend(transaction):
                    logger.warning(f"Double-spend detected for tx {tx_hash}")
                    return False
                    
            # Calculate fee and size
            tx_size = len(transaction.serialize())
            fee_per_byte = transaction.fee / tx_size if tx_size > 0 else 0
            
            # Add to mempool
            self.mempool[tx_hash] = MempoolTransaction(
                transaction=transaction,
                received_time=time.time(),
                last_seen=time.time(),
                fee_per_byte=fee_per_byte,
                size=tx_size,
                in_blocks=set()
            )
            
            # Save to database
            self._save_to_db(tx_hash)
            
            logger.info(f"Added transaction {tx_hash} to mempool")
            return True
            
        except Exception as e:
            logger.error(f"Error adding transaction to mempool: {e}")
            return False
            
    def remove_transaction(self, tx_hash: str):
        """Remove transaction from mempool"""
        if tx_hash in self.mempool:
            del self.mempool[tx_hash]
            
            # Remove from database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM mempool WHERE tx_hash = ?", (tx_hash,))
                
    def get_transactions(self, max_size: int = 1000000) -> List[Transaction]:
        """Get transactions for new block, prioritized by fee"""
        transactions = []
        size = 0
        
        # Sort by fee per byte
        sorted_txs = sorted(
            self.mempool.values(),
            key=lambda x: x.fee_per_byte,
            reverse=True
        )
        
        for mempool_tx in sorted_txs:
            if size + mempool_tx.size > max_size:
                continue
                
            transactions.append(mempool_tx.transaction)
            size += mempool_tx.size
            
        return transactions
        
    def handle_new_block(self, block: Block):
        """Update mempool when new block is added"""
        block_hash = block.hash
        
        # Skip if already processing
        if block_hash in self.processing_blocks:
            return
            
        try:
            self.processing_blocks.add(block_hash)
            
            # Remove confirmed transactions
            for tx in block.transactions:
                if tx.hash in self.mempool:
                    # Mark as included in this block
                    self.mempool[tx.hash].in_blocks.add(block_hash)
                    
                    # Remove if in enough blocks
                    if len(self.mempool[tx.hash].in_blocks) >= 6:
                        self.remove_transaction(tx.hash)
                        
            # Revalidate remaining transactions
            for tx_hash in list(self.mempool.keys()):
                if not self.consensus.verify_tx_balance(self.mempool[tx_hash].transaction):
                    self.remove_transaction(tx_hash)
                    
        finally:
            self.processing_blocks.discard(block_hash)
            
    def handle_chain_reorg(self, old_chain: List[Block], new_chain: List[Block]):
        """Handle blockchain reorganization"""
        # Re-add transactions from old chain
        for block in old_chain:
            for tx in block.transactions:
                if not any(tx in b.transactions for b in new_chain):
                    self.add_transaction(tx, validate=True)
                    
        # Remove transactions in new chain
        for block in new_chain:
            for tx in block.transactions:
                if tx.hash in self.mempool:
                    self.remove_transaction(tx.hash)
                    
    def cleanup(self, max_age: int = 3600):
        """Remove old transactions"""
        current_time = time.time()
        
        for tx_hash in list(self.mempool.keys()):
            mempool_tx = self.mempool[tx_hash]
            
            # Remove if too old
            if current_time - mempool_tx.received_time > max_age:
                self.remove_transaction(tx_hash)
                continue
                
            # Remove if not seen recently
            if current_time - mempool_tx.last_seen > 1800:  # 30 minutes
                self.remove_transaction(tx_hash)
                
    def _is_double_spend(self, transaction: Transaction) -> bool:
        """Check if transaction double-spends any mempool transaction"""
        for tx in self.mempool.values():
            if (tx.transaction.from_address == transaction.from_address and
                tx.transaction.nonce == transaction.nonce):
                return True
        return False
        
    def _save_to_db(self, tx_hash: str):
        """Save transaction to database"""
        mempool_tx = self.mempool[tx_hash]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mempool (
                    tx_hash, raw_tx, received_time,
                    last_seen, fee_per_byte, size
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tx_hash,
                mempool_tx.transaction.serialize(),
                mempool_tx.received_time,
                mempool_tx.last_seen,
                mempool_tx.fee_per_byte,
                mempool_tx.size
            ))
            
    def load_from_db(self):
        """Load mempool from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM mempool WHERE last_seen > ?",
                (time.time() - 3600,)  # Only load transactions from last hour
            )
            
            for row in cursor:
                tx_hash = row[0]
                transaction = Transaction.deserialize(row[1])
                
                self.mempool[tx_hash] = MempoolTransaction(
                    transaction=transaction,
                    received_time=row[2],
                    last_seen=row[3],
                    fee_per_byte=row[4],
                    size=row[5],
                    in_blocks=set()
                ) 