"""
Proof of Delivery (POD) reward calculator
Handles concatenated routes and driver levels
"""

from typing import Dict, List
from datetime import datetime
from ..core.contract import Contract, ContractStatus
from ..wallet.reputation import DriverLevel, ReputationSystem

class PODRewardCalculator:
    """Calculates rewards for Proof of Delivery"""
    
    def __init__(self, base_reward: float = 25.0):
        self.base_reward = base_reward
        self.reputation_system = ReputationSystem()
        
    def calculate_contract_reward(
        self,
        contract: Contract,
        driver_level: DriverLevel,
        quality_score: float,
        on_time: bool
    ) -> Dict:
        """
        Calculate reward for a single contract or concatenated contracts
        """
        # Base calculation
        base_reward = self._calculate_base_reward(contract)
        
        # Apply driver level multiplier
        level_multiplier = self.reputation_system.LEVEL_BONUSES[driver_level]
        level_bonus = base_reward * level_multiplier
        
        # Quality bonus (up to 20%)
        quality_multiplier = min(quality_score / 5.0, 1.0) * 0.2
        quality_bonus = base_reward * quality_multiplier
        
        # On-time bonus (10%)
        time_bonus = base_reward * 0.1 if on_time else 0
        
        # Concatenation bonus (5% per linked contract)
        concat_bonus = base_reward * (len(contract.linked_contracts) * 0.05)
        
        # Calculate total
        total_reward = base_reward + level_bonus + quality_bonus + time_bonus + concat_bonus
        
        return {
            "base_reward": base_reward,
            "level_bonus": level_bonus,
            "quality_bonus": quality_bonus,
            "time_bonus": time_bonus,
            "concatenation_bonus": concat_bonus,
            "total_reward": total_reward,
            "breakdown": {
                "driver_level": driver_level.value,
                "level_multiplier": level_multiplier,
                "quality_score": quality_score,
                "quality_multiplier": quality_multiplier,
                "on_time": on_time,
                "linked_contracts": len(contract.linked_contracts)
            }
        }
        
    def _calculate_base_reward(self, contract: Contract) -> float:
        """
        Calculate base reward considering distance and complexity
        """
        # Distance factor (1 LGC per 10km)
        distance_reward = (contract.estimated_distance / 10.0) * self.base_reward
        
        # Complexity factor (number of checkpoints)
        complexity_factor = len(contract.route_points) / 2  # 2 points is base
        complexity_reward = self.base_reward * (complexity_factor - 1) * 0.1
        
        return max(self.base_reward, distance_reward + complexity_reward)
        
    def estimate_route_reward(
        self,
        contracts: List[Contract],
        driver_level: DriverLevel
    ) -> Dict:
        """
        Estimate potential rewards for a route before execution
        """
        total_distance = sum(c.estimated_distance for c in contracts)
        total_checkpoints = sum(len(c.route_points) for c in contracts)
        
        # Base estimation
        base_estimate = self._calculate_base_reward(contracts[0]) * len(contracts)
        
        # Level bonus
        level_multiplier = self.reputation_system.LEVEL_BONUSES[driver_level]
        level_bonus = base_estimate * level_multiplier
        
        # Concatenation potential
        concat_bonus = base_estimate * ((len(contracts) - 1) * 0.05)
        
        # Minimum guaranteed (without quality/time bonus)
        minimum_reward = base_estimate + level_bonus + concat_bonus
        
        # Maximum potential (with perfect quality and time)
        maximum_reward = minimum_reward * 1.3  # +30% for perfect execution
        
        return {
            "route_summary": {
                "total_distance": total_distance,
                "total_checkpoints": total_checkpoints,
                "num_contracts": len(contracts)
            },
            "reward_estimate": {
                "minimum_reward": minimum_reward,
                "maximum_reward": maximum_reward,
                "base_estimate": base_estimate,
                "level_bonus": level_bonus,
                "concat_bonus": concat_bonus,
                "driver_level": driver_level.value
            }
        } 