"""
Hybrid mining system combining PoW and PoE with pool support
"""

import threading
import time
import logging
from typing import Optional, Dict, List
from queue import Queue
from dataclasses import dataclass
from ..consensus.hybrid_consensus import HybridConsensus
from ..core.block import Block
from ..core.transaction import Transaction, TransactionType
from ..wallet.wallet import Wallet
from ..pool.mining_pool import MiningPool

@dataclass
class MiningConfig:
    """Mining configuration"""
    threads: int = 4  # Number of mining threads
    max_gas: int = 15000000  # Max gas per block
    min_tx_fee: float = 0.0001  # Minimum transaction fee
    block_interval: int = 15  # Target seconds between blocks
    uncle_generations: int = 2  # Number of generations for uncle rewards
    uncle_reward_factor: float = 0.875  # Reward factor for uncle blocks
    pool_mode: bool = False  # Whether mining for a pool
    pool_address: Optional[str] = None  # Pool address if in pool mode
    worker_id: Optional[str] = None  # Worker ID for pool mining

class HybridMiner:
    """
    Hybrid mining system that combines:
    - Multi-threaded PoW mining
    - PoE validation
    - Pool mining support
    - Transaction selection and fee optimization
    """
    
    def __init__(
        self,
        wallet: Wallet,
        consensus: HybridConsensus,
        config: Optional[MiningConfig] = None,
        pool: Optional[MiningPool] = None
    ):
        self.wallet = wallet
        self.consensus = consensus
        self.config = config or MiningConfig()
        self.pool = pool
        
        # Mining state
        self.mining = False
        self.current_block: Optional[Block] = None
        self.mined_blocks: Queue = Queue()
        self.mining_threads: List[threading.Thread] = []
        
        # Performance metrics
        self.hash_rate = 0
        self.last_block_time = 0
        self.blocks_mined = 0
        self.shares_submitted = 0
        
        # Pool connection
        if self.config.pool_mode and not self.pool:
            self.pool = MiningPool(
                pool_address=self.config.pool_address,
                worker_id=self.config.worker_id
            )
        
        logging.info("Hybrid miner initialized")
        
    def start_mining(self):
        """Start mining operations"""
        if self.mining:
            return
            
        self.mining = True
        
        # Connect to pool if in pool mode
        if self.config.pool_mode:
            if not self.pool.connect():
                logging.error("Failed to connect to pool")
                self.mining = False
                return
                
        # Start mining threads
        for i in range(self.config.threads):
            thread = threading.Thread(
                target=self._mining_worker,
                args=(i,),
                daemon=True
            )
            thread.start()
            self.mining_threads.append(thread)
            
        logging.info(f"Started mining with {self.config.threads} threads")
        
    def stop_mining(self):
        """Stop mining operations"""
        self.mining = False
        
        # Disconnect from pool
        if self.pool:
            self.pool.disconnect()
            
        for thread in self.mining_threads:
            thread.join()
        self.mining_threads = []
        logging.info("Mining stopped")
        
    def _mining_worker(self, thread_id: int):
        """Mining worker thread"""
        while self.mining:
            try:
                # Get mining task
                if self.config.pool_mode:
                    mining_task = self.pool.get_work()
                    if not mining_task:
                        time.sleep(1)
                        continue
                else:
                    # Solo mining
                    mining_task = self._create_block_template()
                
                # Mine block
                if self._mine_block(thread_id, mining_task):
                    if self.config.pool_mode:
                        # Submit share to pool
                        if self.pool.submit_share(mining_task):
                            self.shares_submitted += 1
                    else:
                        # Solo mining - add block to chain
                        self.mined_blocks.put(mining_task)
                        self.blocks_mined += 1
                        
            except Exception as e:
                logging.error(f"Mining error in thread {thread_id}: {e}")
                time.sleep(1)
                
    def _create_block_template(self) -> Block:
        """Create block template for solo mining"""
        # Get parent block
        parent_block = self.consensus.get_latest_block()
        
        # Select transactions
        transactions = self._select_transactions()
        
        # Create mining reward
        reward = self.consensus.calculate_mining_reward()
        reward_tx = Transaction(
            from_address="0" * 40,
            to_address=self.wallet.address,
            amount=reward,
            transaction_type=TransactionType.MINING
        )
        transactions.insert(0, reward_tx)
        
        # Create block
        return Block(
            timestamp=int(time.time()),
            previous_hash=parent_block.hash,
            transactions=transactions,
            miner=self.wallet.address,
            difficulty=self.consensus.get_difficulty()
        )
        
    def _select_transactions(self) -> List[Transaction]:
        """Select and validate transactions for new block"""
        selected_txs = []
        gas_used = 0
        
        # Get transactions from mempool
        mempool_txs = self.consensus.get_pending_transactions()
        
        # Sort by fee per gas
        sorted_txs = sorted(
            mempool_txs,
            key=lambda tx: tx.gas_price,
            reverse=True
        )
        
        # Select transactions up to gas limit
        for tx in sorted_txs:
            if gas_used + tx.gas_limit <= self.config.max_gas:
                if self.consensus.validate_transaction(tx):
                    selected_txs.append(tx)
                    gas_used += tx.gas_limit
                    
        return selected_txs
        
    def _mine_block(self, thread_id: int, block: Block) -> bool:
        """
        Try to mine the current block
        Returns True if successfully mined
        """
        # Set mining metadata
        block.miner = self.wallet.address
        block.thread_id = thread_id
        
        # Try different nonces
        start_time = time.time()
        hashes_tried = 0
        
        while self.mining:
            block.nonce += 1
            block.timestamp = int(time.time())
            
            # Calculate hash
            block_hash = block.calculate_hash()
            hashes_tried += 1
            
            # Check if meets difficulty
            if block_hash.startswith('0' * self.consensus.pow_difficulty):
                # Update hash rate
                time_spent = time.time() - start_time
                self.hash_rate = hashes_tried / time_spent
                
                logging.info(f"Block mined by thread {thread_id}: {block_hash}")
                return True
                
            # Periodically check mining rights and update hash rate
            if hashes_tried % 10000 == 0:
                if not self._check_mining_rights():
                    return False
                    
                time_spent = time.time() - start_time
                self.hash_rate = hashes_tried / time_spent
                
        return False
        
    def _check_mining_rights(self) -> bool:
        """Check if we have rights to mine"""
        mining_rights = self.consensus.get_mining_rights()
        our_score = mining_rights.get(self.wallet.address, 0)
        
        # Need to be in top 20% of scores to mine
        scores = sorted(mining_rights.values(), reverse=True)
        cutoff_index = max(1, len(scores) // 5)
        cutoff_score = scores[cutoff_index - 1]
        
        return our_score >= cutoff_score
        
    def add_transaction(self, tx: Transaction) -> bool:
        """Add transaction to mining pool"""
        # Validate transaction
        if not tx.verify():
            logging.warning(f"Invalid transaction: {tx.hash}")
            return False
            
        # Check minimum fee
        if tx.gas_price < self.config.min_tx_fee:
            logging.warning(f"Transaction fee too low: {tx.gas_price}")
            return False
            
        # Add to pool
        self.consensus.add_transaction(tx)
        return True
        
    def get_mining_stats(self) -> Dict:
        """Get mining statistics"""
        stats = {
            "is_mining": self.mining,
            "threads": len(self.mining_threads),
            "hash_rate": self.hash_rate,
            "blocks_mined": self.blocks_mined,
            "last_block_time": self.last_block_time
        }
        
        if self.config.pool_mode:
            stats.update({
                "pool_connected": self.pool.is_connected(),
                "shares_submitted": self.shares_submitted,
                "pool_hashrate": self.pool.get_worker_hashrate(),
                "pool_balance": self.pool.get_worker_balance()
            })
            
        return stats 