"""
Test blockchain persistence system
"""

import os
import time
import logging
import unittest
from typing import List

from block import Block
from transaction import Transaction
from database_manager import DatabaseManager
from mining_manager import MiningManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestBlockchainPersistence(unittest.TestCase):
    """Test blockchain persistence"""
    
    def setUp(self):
        """Set up test environment"""
        # Use test database
        self.test_db = "data/blockchain/test_chain.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        self.db = DatabaseManager(self.test_db)
        self.miner = MiningManager(
            miner_address="test_miner_address",
            difficulty=2  # Lower difficulty for faster tests
        )
        
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
    def test_block_persistence(self):
        """Test block persistence"""
        # Create and mine genesis block
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[],
            previous_hash="0" * 64,
            difficulty=2,
            miner_address="test_miner_address"
        )
        genesis_block.mine_block()
        
        # Save genesis block
        self.assertTrue(
            self.db.save_block(genesis_block),
            "Failed to save genesis block"
        )
        
        # Retrieve genesis block
        retrieved_block = Block.get_block(genesis_block.hash)
        self.assertIsNotNone(
            retrieved_block,
            "Failed to retrieve genesis block"
        )
        
        # Verify block data
        self.assertEqual(
            genesis_block.hash,
            retrieved_block.hash,
            "Block hash mismatch"
        )
        self.assertEqual(
            genesis_block.index,
            retrieved_block.index,
            "Block index mismatch"
        )
        
    def test_transaction_persistence(self):
        """Test transaction persistence"""
        # Create test transaction
        transaction = Transaction(
            tx_hash="test_tx_hash",
            tx_type="transfer",
            from_address="sender_address",
            to_address="receiver_address",
            amount=10.0,
            timestamp=time.time()
        )
        
        # Save to mempool
        self.assertTrue(
            self.db.save_transaction_to_mempool(transaction),
            "Failed to save transaction to mempool"
        )
        
        # Retrieve from mempool
        pending_txs = self.db.get_pending_transactions(limit=1)
        self.assertEqual(
            len(pending_txs),
            1,
            "Failed to retrieve transaction from mempool"
        )
        
        retrieved_tx = pending_txs[0]
        self.assertEqual(
            transaction.tx_hash,
            retrieved_tx.tx_hash,
            "Transaction hash mismatch"
        )
        
    def test_mining_persistence(self):
        """Test mining with persistence"""
        # Create test transaction
        transaction = Transaction(
            tx_hash="test_mining_tx",
            tx_type="transfer",
            from_address="sender_address",
            to_address="receiver_address",
            amount=10.0,
            timestamp=time.time()
        )
        
        # Save to mempool
        self.assertTrue(
            self.db.save_transaction_to_mempool(transaction),
            "Failed to save transaction to mempool"
        )
        
        # Mine block
        mined_block = self.miner.mine_block()
        self.assertIsNotNone(
            mined_block,
            "Failed to mine block"
        )
        
        # Verify block was saved
        retrieved_block = Block.get_block(mined_block.hash)
        self.assertIsNotNone(
            retrieved_block,
            "Failed to retrieve mined block"
        )
        
        # Verify transaction was included
        tx_hashes = [tx.tx_hash for tx in retrieved_block.transactions]
        self.assertIn(
            transaction.tx_hash,
            tx_hashes,
            "Transaction not included in block"
        )
        
        # Verify transaction was removed from mempool
        pending_txs = self.db.get_pending_transactions()
        pending_hashes = [tx.tx_hash for tx in pending_txs]
        self.assertNotIn(
            transaction.tx_hash,
            pending_hashes,
            "Transaction not removed from mempool"
        )
        
    def test_chain_integrity(self):
        """Test blockchain integrity"""
        blocks: List[Block] = []
        
        # Mine several blocks
        for i in range(3):
            # Create test transaction
            transaction = Transaction(
                tx_hash=f"test_tx_{i}",
                tx_type="transfer",
                from_address="sender_address",
                to_address="receiver_address",
                amount=10.0,
                timestamp=time.time()
            )
            
            # Save to mempool
            self.db.save_transaction_to_mempool(transaction)
            
            # Mine block
            block = self.miner.mine_block()
            self.assertIsNotNone(block)
            blocks.append(block)
            
        # Verify chain
        is_valid, errors = self.db.verify_chain_integrity()
        self.assertTrue(
            is_valid,
            f"Chain integrity check failed: {errors}"
        )
        
        # Verify block order
        for i in range(1, len(blocks)):
            self.assertEqual(
                blocks[i].previous_hash,
                blocks[i-1].hash,
                f"Invalid block linkage at index {i}"
            )
            
if __name__ == '__main__':
    unittest.main() 