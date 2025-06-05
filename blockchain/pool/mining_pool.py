"""
Mining pool implementation with PPLNS reward distribution
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from queue import Queue
from ..core.block import Block
from ..core.transaction import Transaction, TransactionType
from ..core.wallet import Wallet
from ..consensus.pow_consensus import PoWConsensus

@dataclass
class PoolConfig:
    """Pool configuration"""
    min_payout: float = 1.0  # Minimum amount for payout
    fee_percent: float = 1.0  # Pool fee (1%)
    pplns_window: int = 10  # Number of blocks for PPLNS calculation
    share_difficulty: int = 4  # Difficulty for shares
    max_workers: int = 1000  # Maximum number of workers
    heartbeat_interval: int = 30  # Seconds between heartbeats

@dataclass
class WorkerStats:
    """Worker statistics"""
    shares_valid: int = 0
    shares_invalid: int = 0
    shares_stale: int = 0
    last_share: float = 0
    hashrate: float = 0
    balance: float = 0
    
class MiningPool:
    """
    Mining pool with:
    - PPLNS reward distribution
    - Share validation
    - Worker management
    - Automated payouts
    """
    
    def __init__(
        self,
        wallet: Wallet,
        consensus: PoWConsensus,
        config: Optional[PoolConfig] = None
    ):
        self.wallet = wallet
        self.consensus = consensus
        self.config = config or PoolConfig()
        
        # Worker management
        self.workers: Dict[str, WorkerStats] = {}
        self.active_workers: Set[str] = set()
        self.worker_lock = threading.RLock()
        
        # Share tracking
        self.shares: List[Dict] = []  # List of {worker, timestamp, difficulty}
        self.current_block: Optional[Block] = None
        self.work_queue: Queue = Queue()
        
        # Payout tracking
        self.balances: Dict[str, float] = {}
        self.pending_payouts: Dict[str, float] = {}
        
        # Start management threads
        self._start_threads()
        
        logging.info("Mining pool initialized")
        
    def _start_threads(self):
        """Start management threads"""
        # Work generation thread
        threading.Thread(
            target=self._work_generator,
            daemon=True
        ).start()
        
        # Payout processing thread
        threading.Thread(
            target=self._process_payouts,
            daemon=True
        ).start()
        
        # Worker monitoring thread
        threading.Thread(
            target=self._monitor_workers,
            daemon=True
        ).start()
        
    def register_worker(self, worker_id: str) -> bool:
        """Register new worker"""
        with self.worker_lock:
            if len(self.workers) >= self.config.max_workers:
                return False
                
            if worker_id not in self.workers:
                self.workers[worker_id] = WorkerStats()
                self.active_workers.add(worker_id)
                logging.info(f"Registered worker {worker_id}")
                
            return True
            
    def get_work(self, worker_id: str) -> Optional[Block]:
        """Get work for worker"""
        if worker_id not in self.active_workers:
            return None
            
        # Get or create current block
        if not self.current_block:
            self.current_block = self._create_block_template()
            
        return self.current_block
        
    def submit_share(self, worker_id: str, block: Block) -> bool:
        """Submit share from worker"""
        if worker_id not in self.active_workers:
            return False
            
        # Validate share
        if not self._validate_share(block, self.config.share_difficulty):
            self.workers[worker_id].shares_invalid += 1
            return False
            
        # Check if share solves block
        if self._validate_share(block, self.consensus.get_difficulty()):
            # Found block! Submit to network
            if self.consensus.add_block(block):
                self._handle_block_found(block, worker_id)
                
        # Record valid share
        with self.worker_lock:
            worker = self.workers[worker_id]
            worker.shares_valid += 1
            worker.last_share = time.time()
            
            # Add to PPLNS window
            self.shares.append({
                "worker": worker_id,
                "timestamp": time.time(),
                "difficulty": self.config.share_difficulty
            })
            
            # Trim old shares
            while len(self.shares) > self.config.pplns_window:
                self.shares.pop(0)
                
        return True
        
    def _handle_block_found(self, block: Block, finder: str):
        """Handle found block and distribute rewards"""
        # Calculate block reward
        block_reward = self.consensus.calculate_block_reward()
        
        # Calculate pool fee
        pool_fee = block_reward * (self.config.fee_percent / 100)
        reward_for_miners = block_reward - pool_fee
        
        # Calculate share ratios in PPLNS window
        total_shares = sum(share["difficulty"] for share in self.shares)
        
        if total_shares > 0:
            # Distribute rewards based on shares
            with self.worker_lock:
                for share in self.shares:
                    worker = share["worker"]
                    share_ratio = share["difficulty"] / total_shares
                    reward = reward_for_miners * share_ratio
                    
                    # Add to worker balance
                    if worker not in self.balances:
                        self.balances[worker] = 0
                    self.balances[worker] += reward
                    
                # Extra bonus for block finder
                finder_bonus = pool_fee * 0.1  # 10% of pool fee
                self.balances[finder] += finder_bonus
                
        # Reset for next block
        self.current_block = None
        self.shares.clear()
        
    def _process_payouts(self):
        """Process pending payouts"""
        while True:
            try:
                with self.worker_lock:
                    # Find workers due payment
                    for worker, balance in self.balances.items():
                        if balance >= self.config.min_payout:
                            # Create payout transaction
                            tx = Transaction(
                                from_address=self.wallet.address,
                                to_address=worker,
                                amount=balance,
                                transaction_type=TransactionType.POOL_PAYOUT
                            )
                            
                            # Submit to blockchain
                            if self.consensus.add_transaction(tx):
                                self.balances[worker] = 0
                                logging.info(f"Processed payout of {balance} to {worker}")
                                
            except Exception as e:
                logging.error(f"Error processing payouts: {e}")
                
            time.sleep(60)  # Check every minute
            
    def _monitor_workers(self):
        """Monitor worker activity"""
        while True:
            try:
                current_time = time.time()
                with self.worker_lock:
                    for worker_id in list(self.active_workers):
                        worker = self.workers[worker_id]
                        # Remove inactive workers
                        if current_time - worker.last_share > self.config.heartbeat_interval * 2:
                            self.active_workers.remove(worker_id)
                            logging.info(f"Worker {worker_id} became inactive")
                            
            except Exception as e:
                logging.error(f"Error monitoring workers: {e}")
                
            time.sleep(self.config.heartbeat_interval)
            
    def _create_block_template(self) -> Block:
        """Create new block template"""
        # Get pending transactions
        transactions = self.consensus.get_pending_transactions()
        
        # Add pool reward transaction
        reward_tx = Transaction(
            from_address="0" * 64,
            to_address=self.wallet.address,  # Pool address
            amount=self.consensus.calculate_block_reward(),
            transaction_type=TransactionType.MINING
        )
        transactions.insert(0, reward_tx)
        
        # Create block
        return Block(
            timestamp=int(time.time()),
            previous_hash=self.consensus.get_latest_block().hash,
            transactions=transactions,
            miner=self.wallet.address,
            difficulty=self.consensus.get_difficulty()
        )
        
    def _validate_share(self, block: Block, difficulty: int) -> bool:
        """Validate share meets difficulty"""
        share_hash = block.calculate_hash()
        return share_hash.startswith("0" * difficulty)
        
    def get_stats(self) -> Dict:
        """Get pool statistics"""
        with self.worker_lock:
            return {
                "active_workers": len(self.active_workers),
                "total_workers": len(self.workers),
                "current_round_shares": len(self.shares),
                "pool_hashrate": sum(w.hashrate for w in self.workers.values()),
                "pending_payouts": sum(self.balances.values()),
                "pool_fee": self.config.fee_percent
            }
            
    def get_worker_stats(self, worker_id: str) -> Optional[Dict]:
        """Get statistics for specific worker"""
        if worker_id not in self.workers:
            return None
            
        worker = self.workers[worker_id]
        return {
            "shares_valid": worker.shares_valid,
            "shares_invalid": worker.shares_invalid,
            "shares_stale": worker.shares_stale,
            "hashrate": worker.hashrate,
            "balance": self.balances.get(worker_id, 0),
            "active": worker_id in self.active_workers
        } 