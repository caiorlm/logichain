"""
LogiChain Reward Engine
Implements Bitcoin-style block rewards with halving
"""

from typing import Dict, Optional
from decimal import Decimal
import time
from ..core.blockchain import Blockchain
from ..storage.database import BlockchainDB
from ..config import TOKENOMICS, get_block_reward

class RewardEngine:
    """Manages the block reward system"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        db: BlockchainDB,
        config: Optional[Dict] = None
    ):
        self.blockchain = blockchain
        self.db = db
        self.config = config or TOKENOMICS
        self.total_rewards_distributed = 0
        
    def calculate_block_reward(self, block_height: int) -> float:
        """Calculate block reward with halving"""
        return get_block_reward(block_height)
        
    def distribute_block_reward(
        self,
        miner_address: str,
        block_height: int,
        fees: float = 0.0
    ) -> Dict[str, float]:
        """Distribute block reward and fees to miner"""
        # Calculate base block reward
        block_reward = self.calculate_block_reward(block_height)
        
        # Add transaction fees (100% to miner)
        total_reward = block_reward + fees
        
        # Send reward to miner
        if total_reward > 0:
            self.blockchain.transfer(
                from_address="0",
                to_address=miner_address,
                amount=total_reward
            )
            
        # Update stats
        self.total_rewards_distributed += total_reward
        
        return {
            "block_reward": block_reward,
            "fees": fees,
            "total_reward": total_reward,
            "recipient": miner_address
        }
        
    def get_stats(self) -> Dict:
        """Get reward engine statistics"""
        current_height = self.blockchain.height
        next_halving = (
            (current_height // self.config["HALVING_INTERVAL"] + 1) * 
            self.config["HALVING_INTERVAL"]
        )
        
        return {
            "total_rewards_distributed": self.total_rewards_distributed,
            "current_block_reward": self.calculate_block_reward(current_height),
            "next_halving_block": next_halving,
            "blocks_until_halving": next_halving - current_height,
            "max_supply": self.config["MAX_SUPPLY"],
            "current_supply": self.blockchain.get_total_supply()
        } 