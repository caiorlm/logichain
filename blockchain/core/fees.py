"""
LogiChain Fee System
"""

from typing import Dict
from dataclasses import dataclass
from enum import Enum
import time
from .transaction import TransactionPriority

@dataclass
class NetworkStats:
    """Network statistics for fee calculation"""
    transactions_per_block: int
    average_block_time: float
    mempool_size: int

class FeeCalculator:
    """Calculates transaction fees based on network conditions"""
    
    BASE_FEE = 0.0001  # Base fee in LGC
    
    # Priority multipliers
    PRIORITY_MULTIPLIERS = {
        TransactionPriority.LOW: 1.0,
        TransactionPriority.MEDIUM: 1.5,
        TransactionPriority.HIGH: 2.0,
        TransactionPriority.URGENT: 3.0
    }
    
    # Network congestion thresholds
    CONGESTION_THRESHOLDS = {
        "low": 1000,      # transactions in mempool
        "medium": 5000,
        "high": 10000
    }
    
    def __init__(self):
        self.last_network_update = 0
        self.network_stats = NetworkStats(
            transactions_per_block=0,
            average_block_time=0,
            mempool_size=0
        )
    
    def calculate_fee(
        self,
        transaction_size: int,
        priority: TransactionPriority = TransactionPriority.MEDIUM
    ) -> float:
        """
        Calculate transaction fee based on:
        - Base fee
        - Transaction size
        - Network congestion
        - Priority level
        """
        # Base calculation
        base = self.BASE_FEE
        
        # Size component (0.00001 LGC per byte over 1KB)
        size_fee = max(0, (transaction_size - 1024) * 0.00001)
        
        # Congestion component
        congestion_multiplier = self._get_congestion_multiplier()
        
        # Priority multiplier
        priority_multiplier = self.PRIORITY_MULTIPLIERS[priority]
        
        # Calculate total fee
        total_fee = (base + size_fee) * congestion_multiplier * priority_multiplier
        
        # Round to 8 decimal places
        return round(total_fee, 8)
    
    def _get_congestion_multiplier(self) -> float:
        """Calculate network congestion multiplier"""
        if self.network_stats.mempool_size >= self.CONGESTION_THRESHOLDS["high"]:
            return 2.0
        elif self.network_stats.mempool_size >= self.CONGESTION_THRESHOLDS["medium"]:
            return 1.5
        elif self.network_stats.mempool_size >= self.CONGESTION_THRESHOLDS["low"]:
            return 1.2
        return 1.0
    
    def update_network_stats(self, stats: NetworkStats) -> None:
        """Update network statistics"""
        self.network_stats = stats
        self.last_network_update = 0  # Reset update timer
    
    def estimate_fee(
        self,
        transaction_size: int,
        priority: TransactionPriority = TransactionPriority.MEDIUM
    ) -> Dict:
        """
        Estimate fee and provide breakdown
        """
        fee = self.calculate_fee(transaction_size, priority)
        
        return {
            "total_fee": fee,
            "breakdown": {
                "base_fee": self.BASE_FEE,
                "size_component": max(0, (transaction_size - 1024) * 0.00001),
                "congestion_multiplier": self._get_congestion_multiplier(),
                "priority_multiplier": self.PRIORITY_MULTIPLIERS[priority],
                "network_stats": {
                    "mempool_size": self.network_stats.mempool_size,
                    "tx_per_block": self.network_stats.transactions_per_block,
                    "avg_block_time": self.network_stats.average_block_time
                }
            }
        } 