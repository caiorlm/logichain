"""
Reputation and rewards system for LogiChain
"""

from enum import Enum
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

class DriverLevel(Enum):
    """Driver levels in the system"""
    DRIVER_LEVEL_1 = "Driver Level 1"
    DRIVER_LEVEL_2 = "Driver Level 2"
    DRIVER_LEVEL_3 = "Driver Level 3"
    DRIVER_EXPERT = "Driver Expert"
    LOGISTIC_SENIOR = "Logistic Senior"

class ReputationSystem:
    """Reputation management system"""
    
    # Level requirements (reputation score ranges)
    LEVEL_REQUIREMENTS = {
        DriverLevel.DRIVER_LEVEL_1: (1.0, 1.99),    # Iniciante
        DriverLevel.DRIVER_LEVEL_2: (2.0, 2.99),    # Desenvolvendo
        DriverLevel.DRIVER_LEVEL_3: (3.0, 3.99),    # Experiente
        DriverLevel.DRIVER_EXPERT: (4.0, 4.49),     # Expert
        DriverLevel.LOGISTIC_SENIOR: (4.5, 5.0)     # Sênior
    }
    
    # Bonus percentages per level
    LEVEL_BONUSES = {
        DriverLevel.DRIVER_LEVEL_1: 0.00,    # 0% bonus
        DriverLevel.DRIVER_LEVEL_2: 0.05,    # 5% bonus
        DriverLevel.DRIVER_LEVEL_3: 0.10,    # 10% bonus
        DriverLevel.DRIVER_EXPERT: 0.15,     # 15% bonus
        DriverLevel.LOGISTIC_SENIOR: 0.20    # 20% bonus
    }

    # Reputation changes for events
    REPUTATION_CHANGES = {
        "delivery_success": 0.2,           # Successful delivery
        "delivery_quality_high": 0.3,      # Quality 4.5+
        "delivery_on_time": 0.1,          # Before deadline
        "delivery_express": 0.2,          # Express delivery
        "delivery_failure": -0.3,         # Failed delivery
        "delivery_late": -0.2,            # Late delivery
        "gps_fraud": -1.0,               # GPS fraud
        "root_detected": -1.0,           # Root detected
        "contract_cancelled": -0.4,      # Cancellation
        "quality_below_3": -0.2,         # Low quality
        "milestone_achieved": 0.3,        # Milestone reached
        "high_value_success": 0.4        # High value contract
    } 