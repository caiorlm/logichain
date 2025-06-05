"""
LogiChain Staking System
Implements governance-only staking without rewards
"""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import time
from ..core.blockchain import Blockchain
from ..storage.database import BlockchainDB
from ..config import STAKING, calculate_voting_power

class StakeType(Enum):
    """Types of stakes"""
    POOL = "pool"  # Logistics company pool
    NODE = "node"  # Validator node
    DRIVER = "driver"  # Delivery driver

@dataclass
class StakeInfo:
    """Stake information"""
    address: str
    stake_type: StakeType
    amount: float
    start_time: float
    lock_period: int
    status: str = "active"

class StakingSystem:
    """Manages staking for governance"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        db: BlockchainDB,
        config: Optional[Dict] = None
    ):
        self.blockchain = blockchain
        self.db = db
        self.config = config or STAKING
        
        self.stakes: Dict[str, StakeInfo] = {}
        self.total_staked: Dict[StakeType, float] = {
            t: 0.0 for t in StakeType
        }
        self.pending_unstakes: Dict[str, float] = {}
        
        # Performance tracking for reputation
        self.performance: Dict[str, Dict] = {}
        
    def create_stake(
        self,
        address: str,
        stake_type: StakeType,
        amount: float
    ) -> bool:
        """Create new stake"""
        # Verify minimum stake
        min_stake = {
            StakeType.POOL: self.config["MIN_POOL_STAKE"],
            StakeType.NODE: self.config["MIN_NODE_STAKE"],
            StakeType.DRIVER: self.config["MIN_DRIVER_STAKE"]
        }[stake_type]
        
        if amount < min_stake:
            raise ValueError(f"Insufficient stake. Required: {min_stake}")
            
        # Create stake
        stake = StakeInfo(
            address=address,
            stake_type=stake_type,
            amount=amount,
            start_time=time.time(),
            lock_period=self.config["UNSTAKE_DELAY"]
        )
        
        # Lock tokens
        self.blockchain.lock_tokens(address, amount)
        
        # Update state
        self.stakes[address] = stake
        self.total_staked[stake_type] += amount
        
        # Initialize performance tracking
        self.performance[address] = {
            "successful_validations": 0,
            "failed_validations": 0,
            "uptime": 100.0,
            "last_active": time.time()
        }
        
        return True
        
    def increase_stake(self, address: str, amount: float) -> bool:
        """Increase existing stake"""
        if address not in self.stakes:
            raise ValueError("No existing stake found")
            
        stake = self.stakes[address]
        if stake.status != "active":
            raise ValueError("Stake is not active")
            
        # Lock additional tokens
        self.blockchain.lock_tokens(address, amount)
        
        # Update amounts
        stake.amount += amount
        self.total_staked[stake.stake_type] += amount
        
        return True
        
    def request_unstake(self, address: str) -> float:
        """Request to unstake"""
        if address not in self.stakes:
            raise ValueError("No stake found")
            
        stake = self.stakes[address]
        if stake.status != "active":
            raise ValueError("Stake is not active")
            
        # Calculate unlock time
        unlock_time = time.time() + stake.lock_period
        
        # Record pending unstake
        self.pending_unstakes[address] = unlock_time
        stake.status = "unstaking"
        
        return unlock_time
        
    def process_unstake(self, address: str) -> float:
        """Process unstake after lock period"""
        if address not in self.pending_unstakes:
            raise ValueError("No pending unstake found")
            
        unlock_time = self.pending_unstakes[address]
        if time.time() < unlock_time:
            raise ValueError("Lock period not completed")
            
        stake = self.stakes[address]
        amount = stake.amount
        
        # Unlock tokens
        self.blockchain.unlock_tokens(address, amount)
        
        # Update state
        del self.pending_unstakes[address]
        del self.stakes[address]
        self.total_staked[stake.stake_type] -= amount
        
        return amount
        
    def update_performance(
        self,
        address: str,
        metric: str,
        value: Union[int, float]
    ):
        """Update performance metrics for reputation"""
        if address not in self.performance:
            return
            
        self.performance[address][metric] = value
        
        # Update uptime if node was inactive
        if metric == "last_active":
            inactive_time = time.time() - value
            max_inactive = 24 * 3600  # 24 hours
            if inactive_time > max_inactive:
                self.performance[address]["uptime"] *= (
                    1 - (inactive_time - max_inactive) / max_inactive
                )
        
    def get_stake_info(self, address: str) -> Optional[Dict]:
        """Get stake information"""
        if address not in self.stakes:
            return None
            
        stake = self.stakes[address]
        return {
            "address": stake.address,
            "type": stake.stake_type.value,
            "amount": stake.amount,
            "start_time": stake.start_time,
            "status": stake.status,
            "performance": self.performance[address]
        }
        
    def get_total_staked(self) -> Dict[str, float]:
        """Get total staked amounts by type"""
        return {
            stake_type.value: amount
            for stake_type, amount in self.total_staked.items()
        }
        
    def get_voting_power(self, address: str) -> float:
        """Calculate voting power based on stake and reputation"""
        if address not in self.stakes:
            return 0.0
            
        stake = self.stakes[address]
        perf = self.performance[address]
        
        # Calculate reputation score (0-1)
        total_validations = (
            perf["successful_validations"] + 
            perf["failed_validations"]
        )
        reputation = (
            perf["successful_validations"] / total_validations
            if total_validations > 0
            else 0.5  # Default reputation
        )
        
        # Calculate activity score (0-1)
        activity = min(1.0, perf["uptime"] / 100.0)
        
        # Calculate total voting power
        return calculate_voting_power(
            stake_amount=stake.amount,
            reputation_score=reputation,
            activity_score=activity
        ) 