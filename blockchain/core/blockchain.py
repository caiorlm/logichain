"""
Blockchain core implementation
"""

import logging
import os
from typing import List, Optional
from datetime import datetime
from .block import Block
from .transaction import Transaction
from ..storage.blockchain_db import BlockchainDB

logger = logging.getLogger(__name__)

class Blockchain:
    """Blockchain implementation"""
    
    def __init__(self, db_path: str = "data/blockchain/chain.db", node_id: str = "main-node"):
        """Initialize blockchain"""
        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Convert file path to SQLite URL
        if not db_path.startswith("sqlite:///"):
            db_path = f"sqlite:///{os.path.abspath(db_path)}"
            
        logger.info(f"Using database at: {db_path}")
        self.db = BlockchainDB(db_path)
        self.blocks = []
        self.pending_transactions = []
        self.node_id = node_id
        
        # Load existing blocks
        self.blocks = self.db.load_blocks() or []
        
        logger.info(f"Blockchain initialized with {len(self.blocks)} blocks")
        
    def add_block(self, block: Block) -> bool:
        """Add a new block to the chain"""
        if self.validate_block(block):
            # Save block to database first
            if self.db.save_block(block):
                self.blocks.append(block)
                logger.info(f"Block {block.hash} added to chain")
                return True
            else:
                logger.error(f"Failed to save block {block.hash} to database")
                return False
        logger.warning(f"Block {block.hash} validation failed")
        return False
        
    def validate_block(self, block: Block) -> bool:
        """Validate a block"""
        # Check block hash
        if block.hash != block.calculate_hash():
            logger.warning(f"Block {block.hash} has invalid hash")
            return False
            
        # Check previous hash
        if not self.blocks:
            # Genesis block
            if block.prev_hash != "0" * 64:
                logger.warning("Invalid genesis block previous hash")
                return False
        else:
            if block.prev_hash != self.blocks[-1].hash:
                logger.warning(f"Block {block.hash} has invalid previous hash")
                return False
                
        # Check transactions
        for tx in block.transactions:
            if not self.validate_transaction(tx):
                logger.warning(f"Block {block.hash} has invalid transaction {tx.hash}")
                return False
                
        return True
        
    def get_latest_block(self) -> Optional[Block]:
        """Get the latest block in the chain"""
        if not self.blocks:
            return None
        return self.blocks[-1]
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a new transaction to pending transactions"""
        if self.validate_transaction(transaction):
            self.pending_transactions.append(transaction)
            return True
        return False
        
    def validate_transaction(self, transaction: Transaction) -> bool:
        """Validate a transaction"""
        # Mining rewards are always valid
        if transaction.from_address == "0" * 64:
            return True
            
        # Check if sender has enough balance
        sender_balance = self.get_balance(transaction.from_address)
        if sender_balance < transaction.amount:
            logger.warning(f"Insufficient balance for transaction {transaction.hash}")
            return False
            
        return True
        
    def get_balance(self, address: str) -> float:
        """Get balance for an address"""
        balance = 0.0
        
        # Load all blocks from database to ensure we have the latest state
        self.blocks = self.db.load_blocks() or []
        
        for block in self.blocks:
            for tx in block.transactions:
                if tx.to_address == address:
                    balance += tx.amount
                elif tx.from_address == address:
                    balance -= tx.amount
                    
        return balance
        
    def mine_block(self, transactions: List[Transaction]) -> Optional[Block]:
        """Mine a new block"""
        if not transactions:
            return None
            
        # Create block
        prev_block = self.get_latest_block()
        prev_hash = prev_block.hash if prev_block else "0" * 64
        
        block = Block(
            prev_hash=prev_hash,
            timestamp=datetime.utcnow(),
            nonce=0,
            difficulty=4,  # Fixed difficulty for now
            transactions=transactions
        )
        
        # Mine block
        mining_time = block.mine_block()
        logger.info(f"Block mined in {mining_time:.2f}s")
        
        # Add block to chain
        if self.add_block(block):
            return block
            
        return None 