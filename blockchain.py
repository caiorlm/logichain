"""
Blockchain implementation with Bitcoin-style security
"""

import time
import logging
from typing import List, Optional, Dict
from .block import Block, InvalidBlockError
from .transaction import Transaction

logger = logging.getLogger(__name__)

class BlockchainError(Exception):
    """Base exception for blockchain errors"""
    pass

class BlockValidationError(BlockchainError):
    """Raised when block validation fails"""
    pass

class TransactionValidationError(BlockchainError):
    """Raised when transaction validation fails"""
    pass

class Blockchain:
    """Secure blockchain implementation"""
    
    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty
        self.blocks: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.mempool: Dict[str, Transaction] = {}
        self.orphan_blocks: Dict[str, Block] = {}
        self.init_chain()
        
    def init_chain(self):
        """Initialize blockchain with genesis block"""
        if not self.blocks:
            genesis = Block.create_genesis_block()
            self.add_block(genesis)
            
    def add_block(self, block: Block, validate: bool = True) -> bool:
        """Add a new block to the chain with full validation"""
        try:
            if validate:
                # 1. Basic block validation
                if not block.is_valid():
                    raise BlockValidationError("Block failed basic validation")
                    
                # 2. Check block index
                if block.index != len(self.blocks):
                    raise BlockValidationError(f"Invalid block index {block.index}")
                    
                # 3. Verify previous hash
                if self.blocks:
                    if block.previous_hash != self.blocks[-1].hash:
                        # Store as orphan if we don't have the previous block
                        self.orphan_blocks[block.hash] = block
                        return False
                elif block.previous_hash != "0" * 64:  # Genesis block
                    raise BlockValidationError("Invalid genesis block")
                    
                # 4. Verify timestamp
                if block.index > 0:
                    prev_block = self.blocks[-1]
                    if block.timestamp <= prev_block.timestamp:
                        raise BlockValidationError("Block timestamp too old")
                    if block.timestamp > time.time() + 7200:  # 2 hours in future
                        raise BlockValidationError("Block timestamp too far in future")
                        
                # 5. Verify proof of work
                if not block.verify_proof_of_work():
                    raise BlockValidationError("Invalid proof of work")
                    
                # 6. Verify all transactions
                if not self.verify_block_transactions(block):
                    raise BlockValidationError("Invalid block transactions")
                    
                # 7. Verify mining reward
                if not self.verify_mining_reward(block):
                    raise BlockValidationError("Invalid mining reward")
                    
            # Add block to chain
            self.blocks.append(block)
            
            # Remove confirmed transactions from mempool
            for tx in block.transactions:
                self.mempool.pop(tx.tx_hash, None)
                
            # Process orphan blocks that may now be valid
            self._process_orphans()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add block {block.hash}: {str(e)}")
            return False
            
    def verify_block_transactions(self, block: Block) -> bool:
        """Verify all transactions in a block"""
        # Track balances during block validation
        temp_balances = {}
        
        for tx in block.transactions:
            if tx.tx_type == 'mining_reward':
                continue
                
            # Get sender's current balance
            sender = tx.from_address
            balance = temp_balances.get(sender, self.get_balance(sender))
            
            # Verify sender has sufficient balance
            if balance < tx.amount:
                return False
                
            # Update temporary balances
            temp_balances[sender] = balance - tx.amount
            temp_balances[tx.to_address] = temp_balances.get(tx.to_address, 0) + tx.amount
            
        return True
        
    def verify_mining_reward(self, block: Block) -> bool:
        """Verify mining reward transaction"""
        rewards = [tx for tx in block.transactions if tx.tx_type == 'mining_reward']
        
        if len(rewards) != 1:
            return False
            
        reward = rewards[0]
        if (reward.from_address != "0" * 64 or
            reward.to_address != block.miner_address or
            reward.amount != self.calculate_mining_reward(block.index)):
            return False
            
        return True
        
    def calculate_mining_reward(self, block_index: int) -> float:
        """Calculate mining reward with halving"""
        halvings = block_index // 210000  # Bitcoin-style halving every 210,000 blocks
        return 50.0 / (2 ** halvings)
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to mempool with validation"""
        try:
            # 1. Basic transaction validation
            if not transaction.is_valid():
                raise TransactionValidationError("Invalid transaction format")
                
            # 2. Check if already in mempool
            if transaction.tx_hash in self.mempool:
                raise TransactionValidationError("Transaction already in mempool")
                
            # 3. Check if already in blockchain
            if self.find_transaction(transaction.tx_hash):
                raise TransactionValidationError("Transaction already in blockchain")
                
            # 4. Verify sender has sufficient balance
            if transaction.from_address != "0" * 64:  # Not a mining reward
                balance = self.get_balance(transaction.from_address)
                mempool_total = sum(
                    tx.amount for tx in self.mempool.values()
                    if tx.from_address == transaction.from_address
                )
                if balance - mempool_total < transaction.amount:
                    raise TransactionValidationError("Insufficient balance")
                    
            # Add to mempool
            self.mempool[transaction.tx_hash] = transaction
            return True
            
        except Exception as e:
            logger.error(f"Failed to add transaction: {str(e)}")
            return False
            
    def get_balance(self, address: str) -> float:
        """Calculate address balance from confirmed transactions"""
        balance = 0.0
        
        for block in self.blocks:
            for tx in block.transactions:
                if tx.to_address == address:
                    balance += tx.amount
                if tx.from_address == address:
                    balance -= tx.amount
                    
        return balance
        
    def find_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """Find transaction in blockchain by hash"""
        for block in self.blocks:
            for tx in block.transactions:
                if tx.tx_hash == tx_hash:
                    return tx
        return None
        
    def _process_orphans(self):
        """Process orphan blocks that may now be valid"""
        processed = set()
        added = True
        
        while added:
            added = False
            for block_hash, block in self.orphan_blocks.items():
                if block.previous_hash == self.blocks[-1].hash:
                    if self.add_block(block):
                        processed.add(block_hash)
                        added = True
                        
        # Remove processed orphans
        for block_hash in processed:
            self.orphan_blocks.pop(block_hash)
            
    def verify_chain(self) -> bool:
        """Verify entire blockchain"""
        for i in range(1, len(self.blocks)):
            current = self.blocks[i]
            previous = self.blocks[i-1]
            
            # Verify block links
            if current.previous_hash != previous.hash:
                return False
                
            # Verify block validity
            if not current.is_valid():
                return False
                
            # Verify transactions
            if not self.verify_block_transactions(current):
                return False
                
        return True
        
    def get_latest_block(self) -> Optional[Block]:
        """Get the latest block in the chain"""
        if not self.blocks:
            return None
        return self.blocks[-1] 