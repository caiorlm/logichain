"""
LogiChain Dual Mining System
Handles both online (full) and offline (limited) mining operations
"""

import time
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

class MiningMode(Enum):
    ONLINE = "online"   # Full mining with high computational power
    OFFLINE = "offline" # Limited mining via LoRa/offline mesh

@dataclass
class MiningConfig:
    """Mining configuration for different modes"""
    difficulty: int
    max_transactions: int
    block_size: int
    timeout: int
    max_power: int  # Maximum computational power to use

@dataclass
class MiningResult:
    """Result of mining operation"""
    success: bool
    block_hash: Optional[str]
    transactions: List[Dict]
    timestamp: float
    power_used: int
    mode: MiningMode

class DualMining:
    """Manages dual-mode mining operations"""
    
    def __init__(
        self,
        node_id: str,
        online_config: Optional[MiningConfig] = None,
        offline_config: Optional[MiningConfig] = None
    ):
        self.node_id = node_id
        
        # Default online config (full power)
        self.online_config = online_config or MiningConfig(
            difficulty=4,          # Higher difficulty
            max_transactions=1000, # More transactions per block
            block_size=1048576,   # 1MB blocks
            timeout=60,           # 1 minute timeout
            max_power=100         # Full power usage
        )
        
        # Default offline config (limited power)
        self.offline_config = offline_config or MiningConfig(
            difficulty=2,         # Lower difficulty for LoRa
            max_transactions=10,  # Limited transactions
            block_size=1024,     # 1KB blocks for LoRa
            timeout=300,         # 5 minutes timeout
            max_power=20         # Limited power usage
        )
        
    async def mine_block(
        self,
        transactions: List[Dict],
        mode: MiningMode,
        previous_hash: str
    ) -> MiningResult:
        """Mine a new block in specified mode"""
        try:
            # Get config for mode
            config = (
                self.online_config if mode == MiningMode.ONLINE 
                else self.offline_config
            )
            
            # Limit transactions based on mode
            transactions = transactions[:config.max_transactions]
            
            # Prepare block data
            block_data = {
                "node_id": self.node_id,
                "previous_hash": previous_hash,
                "timestamp": time.time(),
                "transactions": transactions,
                "mode": mode.value
            }
            
            # Mine with limited power
            with ThreadPoolExecutor(max_workers=config.max_power) as executor:
                nonce = 0
                start_time = time.time()
                
                while True:
                    # Check timeout
                    if time.time() - start_time > config.timeout:
                        return MiningResult(
                            success=False,
                            block_hash=None,
                            transactions=[],
                            timestamp=time.time(),
                            power_used=config.max_power,
                            mode=mode
                        )
                        
                    # Try mining
                    block_data["nonce"] = nonce
                    block_hash = hashlib.sha256(
                        json.dumps(block_data, sort_keys=True).encode()
                    ).hexdigest()
                    
                    # Check if meets difficulty
                    if block_hash.startswith("0" * config.difficulty):
                        return MiningResult(
                            success=True,
                            block_hash=block_hash,
                            transactions=transactions,
                            timestamp=time.time(),
                            power_used=config.max_power,
                            mode=mode
                        )
                        
                    nonce += 1
                    
        except Exception:
            return MiningResult(
                success=False,
                block_hash=None,
                transactions=[],
                timestamp=time.time(),
                power_used=0,
                mode=mode
            )
            
    def validate_block(
        self,
        block_data: Dict,
        mode: MiningMode
    ) -> bool:
        """Validate block based on mode"""
        try:
            # Get config for mode
            config = (
                self.online_config if mode == MiningMode.ONLINE 
                else self.offline_config
            )
            
            # Check block size
            block_size = len(json.dumps(block_data).encode())
            if block_size > config.block_size:
                return False
                
            # Check transaction count
            if len(block_data["transactions"]) > config.max_transactions:
                return False
                
            # Validate hash difficulty
            block_hash = hashlib.sha256(
                json.dumps(block_data, sort_keys=True).encode()
            ).hexdigest()
            
            if not block_hash.startswith("0" * config.difficulty):
                return False
                
            return True
            
        except Exception:
            return False
            
    def adjust_difficulty(
        self,
        mode: MiningMode,
        avg_mining_time: float
    ) -> None:
        """Adjust mining difficulty based on mode and conditions"""
        try:
            config = (
                self.online_config if mode == MiningMode.ONLINE 
                else self.offline_config
            )
            
            # Adjust difficulty based on average mining time
            if mode == MiningMode.ONLINE:
                # Online mode - aim for 1 minute blocks
                if avg_mining_time < 50:  # Too fast
                    config.difficulty += 1
                elif avg_mining_time > 70:  # Too slow
                    config.difficulty = max(1, config.difficulty - 1)
            else:
                # Offline mode - aim for 5 minute blocks
                if avg_mining_time < 240:  # Too fast
                    config.difficulty += 1
                elif avg_mining_time > 360:  # Too slow
                    config.difficulty = max(1, config.difficulty - 1)
                    
        except Exception:
            pass
            
    def estimate_power_usage(
        self,
        transaction_count: int,
        mode: MiningMode
    ) -> int:
        """Estimate power usage for mining"""
        config = (
            self.online_config if mode == MiningMode.ONLINE 
            else self.offline_config
        )
        
        # Basic power estimation
        base_power = 5 if mode == MiningMode.ONLINE else 1
        tx_power = transaction_count * (0.1 if mode == MiningMode.ONLINE else 0.01)
        
        total_power = min(
            int(base_power + tx_power),
            config.max_power
        )
        
        return total_power 