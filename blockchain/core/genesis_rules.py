"""
Genesis Block Rules and Fundamentals
Defines core rules that are enforced throughout the blockchain
"""

import json
from typing import Dict, List
from enum import Enum
from dataclasses import dataclass

class RuleType(Enum):
    CONSENSUS = "consensus"
    VALIDATION = "validation"
    SECURITY = "security"
    ECONOMIC = "economic"
    NETWORK = "network"
    INTEGRITY = "integrity"

@dataclass
class ConsensusRule:
    min_validators: int = 3
    validation_threshold: float = 0.67
    block_time: int = 30
    difficulty_adjustment: int = 2016
    max_block_size: int = 1024 * 1024  # 1MB

@dataclass
class ValidationRule:
    max_transaction_size: int = 100 * 1024  # 100KB
    max_signature_size: int = 72
    min_fee: float = 0.0001
    max_fee: float = 1.0
    max_ops_per_tx: int = 100

@dataclass
class SecurityRule:
    min_hash_power: float = 0.1
    max_reorg_depth: int = 100
    signature_algorithm: str = "secp256k1"
    hash_algorithm: str = "sha256d"
    key_size: int = 256

@dataclass
class EconomicRule:
    initial_supply: int = 21_000_000
    block_reward: float = 50.0
    halving_interval: int = 210_000
    min_stake: float = 100.0
    max_inflation: float = 0.02

@dataclass
class NetworkRule:
    max_peers: int = 125
    min_peers: int = 8
    timeout: int = 30
    max_message_size: int = 32 * 1024 * 1024  # 32MB
    port: int = 8333

@dataclass
class IntegrityRule:
    code_hash_algorithm: str = "sha512"
    execution_hash_algorithm: str = "sha256d"
    max_code_size: int = 1024 * 1024  # 1MB
    required_coverage: float = 0.95
    update_interval: int = 10000  # blocks

class GenesisRules:
    """Defines and enforces fundamental blockchain rules"""
    
    def __init__(self):
        self.consensus = ConsensusRule()
        self.validation = ValidationRule()
        self.security = SecurityRule()
        self.economic = EconomicRule()
        self.network = NetworkRule()
        self.integrity = IntegrityRule()
        
    def to_genesis_block(self) -> Dict:
        """Convert rules to genesis block format"""
        return {
            "version": 1,
            "timestamp": 0,  # Genesis timestamp
            "previous_hash": "0" * 64,
            "merkle_root": "0" * 64,
            "difficulty": 1,
            "nonce": 0,
            "rules": {
                "consensus": {
                    "type": RuleType.CONSENSUS.value,
                    "parameters": self._to_dict(self.consensus),
                    "modules": [
                        "consensus",
                        "validator",
                        "block_processor"
                    ]
                },
                "validation": {
                    "type": RuleType.VALIDATION.value,
                    "parameters": self._to_dict(self.validation),
                    "modules": [
                        "transaction",
                        "block",
                        "mempool"
                    ]
                },
                "security": {
                    "type": RuleType.SECURITY.value,
                    "parameters": self._to_dict(self.security),
                    "modules": [
                        "crypto",
                        "wallet",
                        "network"
                    ]
                },
                "economic": {
                    "type": RuleType.ECONOMIC.value,
                    "parameters": self._to_dict(self.economic),
                    "modules": [
                        "mining",
                        "staking",
                        "rewards"
                    ]
                },
                "network": {
                    "type": RuleType.NETWORK.value,
                    "parameters": self._to_dict(self.network),
                    "modules": [
                        "p2p",
                        "sync",
                        "discovery"
                    ]
                },
                "integrity": {
                    "type": RuleType.INTEGRITY.value,
                    "parameters": self._to_dict(self.integrity),
                    "modules": [
                        "code_integrity",
                        "genesis_integrator",
                        "security"
                    ]
                }
            }
        }
        
    def _to_dict(self, obj) -> Dict:
        """Convert dataclass to dictionary"""
        return {
            k: v for k, v in obj.__dict__.items()
            if not k.startswith('_')
        }
        
    @classmethod
    def from_genesis_block(cls, genesis_block: Dict) -> 'GenesisRules':
        """Create rules from genesis block"""
        rules = cls()
        
        for rule_type, rule_data in genesis_block["rules"].items():
            params = rule_data["parameters"]
            
            if rule_type == "consensus":
                rules.consensus = ConsensusRule(**params)
            elif rule_type == "validation":
                rules.validation = ValidationRule(**params)
            elif rule_type == "security":
                rules.security = SecurityRule(**params)
            elif rule_type == "economic":
                rules.economic = EconomicRule(**params)
            elif rule_type == "network":
                rules.network = NetworkRule(**params)
            elif rule_type == "integrity":
                rules.integrity = IntegrityRule(**params)
                
        return rules
        
    def validate_rules(self) -> bool:
        """Validate rule consistency"""
        try:
            # Validate consensus rules
            if (self.consensus.validation_threshold <= 0.5 or
                self.consensus.validation_threshold > 1.0):
                return False
                
            # Validate economic rules
            if (self.economic.block_reward <= 0 or
                self.economic.initial_supply <= 0):
                return False
                
            # Validate security rules
            if self.security.min_hash_power <= 0:
                return False
                
            # Validate network rules
            if self.network.min_peers > self.network.max_peers:
                return False
                
            # Validate integrity rules
            if self.integrity.required_coverage <= 0:
                return False
                
            return True
            
        except Exception:
            return False
            
    def export_rules(self, output_file: str):
        """Export rules to file"""
        genesis_block = self.to_genesis_block()
        
        with open(output_file, 'w') as f:
            json.dump(genesis_block, f, indent=2)
            
    @classmethod
    def import_rules(cls, input_file: str) -> 'GenesisRules':
        """Import rules from file"""
        with open(input_file) as f:
            genesis_block = json.load(f)
            
        return cls.from_genesis_block(genesis_block) 