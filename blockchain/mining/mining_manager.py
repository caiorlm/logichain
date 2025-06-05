"""
Mining manager with P2P network integration and mempool synchronization
"""

import time
import logging
import threading
import queue
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from ..core.block import Block
from ..core.transaction import Transaction
from ..network.mempool_manager import MempoolManager
from ..consensus.pow_consensus import PoWConsensus

logger = logging.getLogger(__name__)

class MiningManager:
    """Manages mining operations with network integration"""
    
    def __init__(
        self,
        mempool: MempoolManager,
        consensus: PoWConsensus,
        miner_address: str,
        num_threads: int = None
    ):
        self.mempool = mempool
        self.consensus = consensus
        self.miner_address = miner_address
        self.num_threads = num_threads or max(1, threading.cpu_count() - 1)
        
        # Mining state
        self.current_block: Optional[Block] = None
        self.mining_blocks: Dict[str, Block] = {}
        self.stop_flags: Dict[str, bool] = {}
        self.mining_thread: Optional[threading.Thread] = None
        self.is_mining = False
        
        # Work queues
        self.work_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
    def start_mining(self):
        """Start mining operations"""
        if self.is_mining:
            return
            
        self.is_mining = True
        self.mining_thread = threading.Thread(target=self._mining_loop)
        self.mining_thread.daemon = True
        self.mining_thread.start()
        
        logger.info("Mining operations started")
        
    def stop_mining(self):
        """Stop mining operations"""
        self.is_mining = False
        
        # Stop all mining tasks
        for block_hash in self.stop_flags:
            self.stop_flags[block_hash] = True
            
        if self.mining_thread:
            self.mining_thread.join()
            
        logger.info("Mining operations stopped")
        
    def _mining_loop(self):
        """Main mining loop"""
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            while self.is_mining:
                try:
                    # Create new block template
                    block = self._create_block_template()
                    if not block:
                        time.sleep(1)
                        continue
                        
                    # Start mining tasks
                    block_hash = block.hash
                    self.mining_blocks[block_hash] = block
                    self.stop_flags[block_hash] = False
                    
                    # Divide nonce range among threads
                    nonce_ranges = self._divide_nonce_ranges(self.num_threads)
                    futures = []
                    
                    for start, end in nonce_ranges:
                        futures.append(
                            executor.submit(
                                self._mine_block_range,
                                block,
                                start,
                                end,
                                block_hash
                            )
                        )
                        
                    # Wait for result or new block
                    while not self.stop_flags[block_hash]:
                        try:
                            result = self.result_queue.get(timeout=1)
                            if result["block_hash"] == block_hash:
                                if result["success"]:
                                    # Block found!
                                    mined_block = result["block"]
                                    self._handle_mined_block(mined_block)
                                break
                        except queue.Empty:
                            # Check if we should create new block
                            if self._should_create_new_block(block):
                                break
                                
                    # Stop mining this block
                    self.stop_flags[block_hash] = True
                    del self.mining_blocks[block_hash]
                    
                except Exception as e:
                    logger.error(f"Error in mining loop: {e}")
                    time.sleep(1)
                    
    def _create_block_template(self) -> Optional[Block]:
        """Create new block template with transactions from mempool"""
        try:
            # Get latest block
            prev_block = self.consensus.get_latest_block()
            if not prev_block:
                return None
                
            # Get transactions from mempool
            transactions = self.mempool.get_transactions()
            
            # Create mining reward
            reward = self.consensus.calculate_mining_reward(prev_block.index + 1)
            reward_tx = Transaction.create_mining_reward(
                self.miner_address,
                reward
            )
            transactions.insert(0, reward_tx)
            
            # Create block
            block = Block(
                index=prev_block.index + 1,
                timestamp=time.time(),
                transactions=transactions,
                previous_hash=prev_block.hash,
                difficulty=self.consensus.get_next_difficulty(),
                miner_address=self.miner_address
            )
            
            return block
            
        except Exception as e:
            logger.error(f"Error creating block template: {e}")
            return None
            
    def _mine_block_range(
        self,
        block: Block,
        start_nonce: int,
        end_nonce: int,
        block_hash: str
    ):
        """Mine block with nonce range"""
        try:
            current_nonce = start_nonce
            
            while (
                current_nonce <= end_nonce and
                not self.stop_flags[block_hash]
            ):
                # Try nonce
                block.nonce = current_nonce
                block.header.nonce = current_nonce
                new_hash = block._calculate_hash()
                
                # Check if valid
                if new_hash.startswith("0" * block.difficulty):
                    block.hash = new_hash
                    self.result_queue.put({
                        "success": True,
                        "block": block,
                        "block_hash": block_hash
                    })
                    return
                    
                current_nonce += 1
                
            self.result_queue.put({
                "success": False,
                "block_hash": block_hash
            })
            
        except Exception as e:
            logger.error(f"Error mining block range: {e}")
            self.result_queue.put({
                "success": False,
                "block_hash": block_hash
            })
            
    def _handle_mined_block(self, block: Block):
        """Handle successfully mined block"""
        try:
            # Validate block
            if not block.is_valid():
                logger.warning(f"Mined invalid block {block.hash}")
                return
                
            # Add to blockchain
            if self.consensus.add_block(block):
                logger.info(f"Successfully mined block {block.hash}")
                
                # Update mempool
                self.mempool.handle_new_block(block)
                
                # Broadcast to network
                self.consensus.broadcast_block(block)
            else:
                logger.warning(f"Failed to add mined block {block.hash}")
                
        except Exception as e:
            logger.error(f"Error handling mined block: {e}")
            
    def _should_create_new_block(self, current_block: Block) -> bool:
        """Check if we should create new block template"""
        # Check if new transactions in mempool
        current_tx_count = len(current_block.transactions)
        mempool_tx_count = len(self.mempool.get_transactions())
        
        if mempool_tx_count > current_tx_count:
            return True
            
        # Check if block too old
        if time.time() - current_block.timestamp > 60:
            return True
            
        return False
        
    def _divide_nonce_ranges(self, num_threads: int) -> List[tuple]:
        """Divide nonce range among threads"""
        max_nonce = 2**32
        chunk_size = max_nonce // num_threads
        ranges = []
        
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < num_threads - 1 else max_nonce
            ranges.append((start, end))
            
        return ranges 