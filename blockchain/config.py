"""
LogiChain configuration and tokenomics
"""

from typing import Dict, Any
from decimal import Decimal

# Tokenomics configuration
TOKENOMICS = {
    "INITIAL_REWARD": 50.0,           # Initial block reward (POW)
    "DELIVERY_REWARD": 25.0,          # Initial delivery reward (POD)
    "HALVING_INTERVAL": 210000,       # Blocks between halvings
    "MAX_SUPPLY": 21000000,          # Maximum supply
    "INITIAL_DIFFICULTY": 4,         # Initial mining difficulty
    "TARGET_BLOCK_TIME": 150,        # Target seconds between blocks
    
    # Distribution
    "GENESIS_RESERVE": 1000000,      # Initial reserve for system
    "ECOSYSTEM_FUND": 2000000,       # Ecosystem development fund
    
    # Contract fees
    "CONTRACT_FEE": 0.10,            # 10% fee on contract value
    "FEE_DISTRIBUTION": {
        "POW_MINERS": 0.50,          # 50% to POW miners
        "POD_EXECUTOR": 0.50         # 50% to POD executor
    }
}

# Network parameters
NETWORK = {
    "NETWORK_ID": 1,
    "CHAIN_ID": 1337,
    "BLOCK_TIME": 600,  # 10 minutes like Bitcoin
    "MAX_BLOCK_SIZE": 2 * 1024 * 1024,  # 2MB
    "DIFFICULTY_ADJUSTMENT_INTERVAL": 2016  # ~2 weeks like Bitcoin
}

# Mesh network parameters
MESH = {
    "ENABLED": True,
    "OFFLINE_SYNC_INTERVAL": 300,  # 5 minutes
    "MAX_OFFLINE_BLOCKS": 1000,
    "BRIDGE_NODE_MIN_STAKE": 50000,
    "MAX_PEERS": 10,
    "HANDSHAKE_TIMEOUT": 30,
    "SYNC_BATCH_SIZE": 100,
    "STATE_CLEANUP_INTERVAL": 3600,  # 1 hour
    "MAX_PENDING_STATES": 1000,
    "MESH_PROTOCOL_VERSION": "1.0.0"
}

# LoRa parameters
LORA = {
    "ENABLED": True,
    "FREQUENCY": 915000000,  # 915MHz
    "BANDWIDTH": 125000,  # 125kHz
    "SPREADING_FACTOR": 7,
    "CODING_RATE": 5,
    "POWER_LEVEL": 20,  # dBm
    "SYNC_WORD": 0x12,
    "MAX_PAYLOAD_SIZE": 255,
    "RETRY_COUNT": 3,
    "RETRY_INTERVAL": 5,
    "LISTEN_INTERVAL": 2
}

# Governance parameters
GOVERNANCE = {
    "MIN_STAKE_TO_PROPOSE": 10_000,
    "QUORUM": 0.4,  # 40% participation required
    "MAJORITY": 0.6,  # 60% majority required
    "VOTING_PERIOD": 604800,  # 7 days
    "ALLOWED_PROPOSAL_TYPES": [
        "protocol_upgrade",
        "parameter_change",
        "feature_activation"
    ],
    "IMMUTABLE_PARAMS": [
        "MAX_SUPPLY",
        "INITIAL_REWARD",
        "HALVING_INTERVAL",
        "BURN_ENABLED",
        "TREASURY_ENABLED",
        "FEE_POLICY"
    ]
}

# Staking parameters (for governance only)
STAKING = {
    "MIN_POOL_STAKE": 100_000,
    "MIN_NODE_STAKE": 50_000,
    "MIN_DRIVER_STAKE": 1_000,
    "UNSTAKE_DELAY": 1209600,  # 14 days
    "REWARDS_ENABLED": False,  # No staking rewards
    "VOTING_POWER": {
        "STAKE_WEIGHT": 0.4,  # 40% from stake amount
        "REPUTATION_WEIGHT": 0.4,  # 40% from reputation
        "ACTIVITY_WEIGHT": 0.2  # 20% from activity
    }
}

# Reputation levels and requirements
REPUTATION = {
    "DRIVER_LEVEL_1": {
        "min_score": 1.0,
        "min_deliveries": 0,
        "reward_multiplier": 1.0     # Base reward
    },
    "DRIVER_LEVEL_2": {
        "min_score": 2.0,
        "min_deliveries": 50,
        "reward_multiplier": 1.05    # 5% bonus
    },
    "DRIVER_LEVEL_3": {
        "min_score": 3.0,
        "min_deliveries": 200,
        "reward_multiplier": 1.10    # 10% bonus
    },
    "DRIVER_EXPERT": {
        "min_score": 4.0,
        "min_deliveries": 500,
        "reward_multiplier": 1.15    # 15% bonus
    },
    "LOGISTIC_SENIOR": {
        "min_score": 4.5,
        "min_deliveries": 1000,
        "reward_multiplier": 1.20    # 20% bonus
    }
}

def get_block_reward(block_height: int) -> float:
    """Calculate block reward with Bitcoin-style halving"""
    halvings = block_height // TOKENOMICS["HALVING_INTERVAL"]
    reward = TOKENOMICS["INITIAL_REWARD"] / (2 ** halvings)
    return max(reward, 0)

def get_current_supply(current_height: int) -> float:
    """Calculate current supply based on block height"""
    total_supply = 0
    remaining_blocks = current_height
    reward = TOKENOMICS["INITIAL_REWARD"]
    halving_interval = TOKENOMICS["HALVING_INTERVAL"]
    
    while remaining_blocks > 0 and reward > 0:
        blocks_in_era = min(remaining_blocks, halving_interval)
        total_supply += blocks_in_era * reward
        remaining_blocks -= blocks_in_era
        reward /= 2
        
    return min(total_supply, TOKENOMICS["MAX_SUPPLY"])

def validate_governance_param(param: str) -> bool:
    """Check if parameter can be modified via governance"""
    return param not in GOVERNANCE["IMMUTABLE_PARAMS"]

def calculate_voting_power(
    stake_amount: float,
    reputation_score: float,
    activity_score: float
) -> float:
    """Calculate voting power based on stake, reputation and activity"""
    weights = STAKING["VOTING_POWER"]
    return (
        stake_amount * weights["STAKE_WEIGHT"] +
        reputation_score * weights["REPUTATION_WEIGHT"] +
        activity_score * weights["ACTIVITY_WEIGHT"]
    ) 