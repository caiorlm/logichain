"""
Tokenomics configuration for LogiChain
"""

from typing import Dict, Any
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class TokenomicsConfig:
    """Tokenomics configuration"""
    max_supply: int = 21_000_000
    initial_block_reward: int = 50
    halving_interval: int = 210_000
    distribution: Dict[str, float] = None
    min_tx_fee: float = 0.001
    default_tx_fee: float = 0.01
    max_tx_fee: float = 1.0

    def __post_init__(self):
        if self.distribution is None:
            self.distribution = {
                'executor': 0.80,
                'validators': 0.15,
                'maintenance': 0.05
            }

class TokenomicsManager:
    """Manager for tokenomics operations"""
    
    def __init__(self, config: TokenomicsConfig = None):
        self.config = config or TokenomicsConfig()
        self._total_supply = 0
        self._circulating_supply = 0
        
    def calculate_block_reward(self, block_height: int) -> float:
        """Calculate block reward based on height"""
        halvings = block_height // self.config.halving_interval
        return self.config.initial_block_reward / (2 ** halvings)
        
    def get_distribution(self, reward: float) -> Dict[str, float]:
        """Calculate reward distribution"""
        return {
            role: reward * percentage
            for role, percentage in self.config.distribution.items()
        }
        
    def validate_transaction_fee(self, fee: float) -> bool:
        """Validate if transaction fee is within acceptable range"""
        return self.config.min_tx_fee <= fee <= self.config.max_tx_fee
        
    def update_supply(self, amount: float) -> None:
        """Update total supply"""
        new_supply = self._total_supply + amount
        if new_supply > self.config.max_supply:
            raise ValueError("Would exceed maximum supply")
        self._total_supply = new_supply
        
    def get_tokenomics_info(self) -> Dict[str, Any]:
        """Get current tokenomics information"""
        return {
            'max_supply': self.config.max_supply,
            'total_supply': self._total_supply,
            'circulating_supply': self._circulating_supply,
            'block_reward': self.config.initial_block_reward,
            'halving_interval': self.config.halving_interval,
            'distribution': self.config.distribution,
            'min_tx_fee': self.config.min_tx_fee,
            'default_tx_fee': self.config.default_tx_fee,
            'max_tx_fee': self.config.max_tx_fee
        }
        
    def validate_transaction(self, amount: float, fee: float) -> bool:
        """Validate transaction amount and fee"""
        if amount <= 0:
            return False
        if not self.validate_transaction_fee(fee):
            return False
        return True 