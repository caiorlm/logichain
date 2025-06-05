"""
Configuração da rede principal LogiChain
Bitcoin-style tokenomics implementation
"""

from decimal import Decimal
import os
from typing import Dict, Any

# Configurações da rede
NETWORK_ID = 1  # ID da rede principal
NETWORK_NAME = "LogiChain Mainnet"
NETWORK_VERSION = "1.0.0"
CHAIN_ID = 1337  # Chain ID único da LogiChain

# Configurações de bloco
BLOCK_TIME = 600  # 10 minutos (like Bitcoin)
MAX_BLOCK_SIZE = 1048576  # 1MB
MAX_TRANSACTIONS_PER_BLOCK = 2500
DIFFICULTY_ADJUSTMENT_INTERVAL = 2016  # ~2 semanas
TARGET_TIMESPAN = 1209600  # 2 semanas

# Configurações de mineração
INITIAL_DIFFICULTY = 18
INITIAL_REWARD = Decimal('50')
HALVING_INTERVAL = 210000
MAX_SUPPLY = Decimal('21000000')

# Configurações de transação
MIN_TRANSACTION_FEE = Decimal('0.0001')
MIN_RELAY_FEE = Decimal('0.00001')
DUST_THRESHOLD = Decimal('0.00000546')

# Configurações de rede P2P
P2P_PORT = 8334
API_PORT = 8333
MAX_PEERS = 125
MIN_PEERS = 8
PEER_DISCOVERY_INTERVAL = 300  # 5 minutos
PEER_PING_INTERVAL = 1800  # 30 minutos
BAN_SCORE_THRESHOLD = 100
MAX_PROTOCOL_VERSION = 70015
MIN_PROTOCOL_VERSION = 70015

# Configurações de segurança
SSL_REQUIRED = True
MIN_RELAY_TX_FEE = Decimal('0.00001')
MAX_STANDARD_TX_SIZE = 100000
MAX_MEMPOOL_SIZE = 300  # MB
MAX_ORPHAN_TRANSACTIONS = 100
CHECKPOINTS = {
    0: "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"  # Genesis block
}

# Nós bootstrap
BOOTSTRAP_NODES = [
    "node1.logichain.net:8334",
    "node2.logichain.net:8334",
    "node3.logichain.net:8334",
    "node4.logichain.net:8334",
    "node5.logichain.net:8334"
]

# Diretórios e arquivos
BASE_DIR = os.path.expanduser("~/.logichain/mainnet")
DB_PATH = os.path.join(BASE_DIR, "db/chain.db")
WALLET_PATH = os.path.join(BASE_DIR, "wallets")
LOG_PATH = os.path.join(BASE_DIR, "logs")
PEERS_FILE = os.path.join(BASE_DIR, "peers.json")
BANLIST_FILE = os.path.join(BASE_DIR, "banlist.json")

# Criar diretórios necessários
for path in [BASE_DIR, os.path.dirname(DB_PATH), WALLET_PATH, LOG_PATH]:
    os.makedirs(path, exist_ok=True)

class MainnetConfig:
    """Mainnet configuration parameters"""
    
    def __init__(self):
        # Network parameters
        self.network_id = 1
        self.network_name = "LogiChain Mainnet"
        self.chain_id = 1337
        self.block_time = 600  # 10 minutes (like Bitcoin)
        self.max_block_size = 2 * 1024 * 1024  # 2MB
        
        # Tokenomics parameters (fixed, Bitcoin-style)
        self.tokenomics = {
            "max_supply": 21_000_000,
            "initial_block_reward": 50.0,
            "halving_interval": 210_000,
            "min_transaction_fee": 0.00001,  # Minimum relay fee
        }
        
        # Genesis parameters
        self.genesis_timestamp = 1677721600  # March 2, 2023
        self.genesis_difficulty = 1_000_000
        
        # Staking parameters (for governance only)
        self.staking_params = {
            "min_pool_stake": 100_000.0,
            "min_node_stake": 50_000.0,
            "min_driver_stake": 1_000.0,
            "unstake_delay": 1209600,  # 14 days
            "no_rewards": True  # Staking does not generate rewards
        }
        
        # Governance parameters (BIP-style)
        self.governance_params = {
            "min_proposal_stake": 10_000.0,  # Minimum stake to propose
            "voting_period": 604800,  # 7 days
            "quorum": 0.4,  # 40% participation required
            "majority": 0.5,  # Simple majority (50% + 1)
            "allowed_proposal_types": [
                "protocol_upgrade",
                "parameter_change",
                "feature_activation"
            ],
            "restricted_changes": [
                "max_supply",
                "initial_block_reward",
                "halving_interval",
                "tokenomics"
            ]
        }
        
        # Consensus parameters
        self.consensus_params = {
            "pod_threshold": 0.8,
            "min_validators": 3,
            "max_validators": 100,
            "validator_timeout": 60,
            "block_confirmation_depth": 6
        }
        
    def calculate_block_reward(self, block_height: int) -> float:
        """Calculate block reward with Bitcoin-style halving"""
        halvings = block_height // self.tokenomics["halving_interval"]
        reward = self.tokenomics["initial_block_reward"] / (2 ** halvings)
        return max(reward, 0)
        
    def validate_proposal(self, proposal_type: str, changes: Dict) -> bool:
        """Validate governance proposal"""
        # Check if proposal type is allowed
        if proposal_type not in self.governance_params["allowed_proposal_types"]:
            return False
            
        # Check if changes affect restricted parameters
        for key in changes.keys():
            if key in self.governance_params["restricted_changes"]:
                return False
                
        return True
        
    def get_current_supply(self, current_height: int) -> float:
        """Calculate current supply based on block height"""
        total_supply = 0
        remaining_blocks = current_height
        reward = self.tokenomics["initial_block_reward"]
        halving_interval = self.tokenomics["halving_interval"]
        
        while remaining_blocks > 0 and reward > 0:
            blocks_in_era = min(remaining_blocks, halving_interval)
            total_supply += blocks_in_era * reward
            remaining_blocks -= blocks_in_era
            reward /= 2
            
        return min(total_supply, self.tokenomics["max_supply"])

    def get_economic_params(self) -> Dict[str, Any]:
        """Get economic parameters (exposed via API)"""
        return self.economic_params
        
    def update_economic_params(self, new_params: Dict[str, Any]) -> bool:
        """Update economic parameters through governance"""
        try:
            # Update reward parameters
            if "reward" in new_params:
                self.economic_params["reward"].update(new_params["reward"])
                
            # Update treasury parameters    
            if "treasury" in new_params:
                self.economic_params["treasury"].update(new_params["treasury"])
                
            # Update fee parameters
            if "fees" in new_params:
                self.economic_params["fees"].update(new_params["fees"])
                
            return True
        except Exception:
            return False
            
    def validate_economic_params(self, params: Dict[str, Any]) -> bool:
        """Validate economic parameter updates"""
        try:
            # Validate reward parameters
            if "reward" in params:
                reward = params["reward"]
                assert 0 <= reward.get("burn_rate", 0) <= 1
                assert 0 <= reward.get("treasury_rate", 0) <= 1
                assert 0 <= reward.get("staking_rate", 0) <= 1
                assert 0 <= reward.get("governance_rate", 0) <= 1
                total_rate = (reward.get("burn_rate", 0) + 
                            reward.get("treasury_rate", 0) +
                            reward.get("staking_rate", 0) +
                            reward.get("governance_rate", 0))
                assert abs(total_rate - 1.0) < 0.0001  # Sum should be 1
                
            # Validate treasury parameters
            if "treasury" in params:
                treasury = params["treasury"]
                assert treasury.get("distribution_interval", 0) > 0
                assert 0 <= treasury.get("staking_allocation", 0) <= 1
                assert 0 <= treasury.get("governance_allocation", 0) <= 1
                assert 0 <= treasury.get("development_allocation", 0) <= 1
                assert 0 <= treasury.get("emergency_allocation", 0) <= 1
                total_allocation = (treasury.get("staking_allocation", 0) +
                                treasury.get("governance_allocation", 0) +
                                treasury.get("development_allocation", 0) +
                                treasury.get("emergency_allocation", 0))
                assert abs(total_allocation - 1.0) < 0.0001  # Sum should be 1
                
            # Validate fee parameters
            if "fees" in params:
                fees = params["fees"]
                assert fees.get("base_fee", 0) > 0
                assert 0 <= fees.get("burn_rate", 0) <= 1
                assert 0 <= fees.get("treasury_rate", 0) <= 1
                assert abs(fees.get("burn_rate", 0) + 
                         fees.get("treasury_rate", 0) - 1.0) < 0.0001
                
            return True
        except Exception:
            return False 