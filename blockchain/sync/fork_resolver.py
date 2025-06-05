import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ChainMode(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"

@dataclass
class ChainInfo:
    blocks: List[Dict]
    total_difficulty: int
    quorum_votes: int
    mode: ChainMode
    last_block_time: float

@dataclass
class ForkResolution:
    winning_chain: ChainInfo
    reason: str
    is_suspicious: bool
    metrics: Dict

class ForkResolver:
    def __init__(self):
        self.suspicious_threshold = 0.7
        self.min_quorum_votes = 3
        self.max_time_difference = 3600  # 1 hour
        self.audit_queue: List[Tuple[ChainInfo, ChainInfo]] = []
        
    def resolve_fork(
        self,
        online_chain: ChainInfo,
        offline_chain: ChainInfo
    ) -> ForkResolution:
        """Resolve fork between online and offline chains"""
        try:
            # Calculate metrics for both chains
            online_metrics = self._calculate_chain_metrics(online_chain)
            offline_metrics = self._calculate_chain_metrics(offline_chain)
            
            # Compare chain heights
            if len(online_chain.blocks) != len(offline_chain.blocks):
                # Different heights - choose longer chain
                winner = online_chain if len(online_chain.blocks) > len(offline_chain.blocks) else offline_chain
                return ForkResolution(
                    winning_chain=winner,
                    reason="Height difference",
                    is_suspicious=False,
                    metrics={
                        "online": online_metrics,
                        "offline": offline_metrics
                    }
                )
                
            # Same height - compare difficulty
            if online_chain.total_difficulty != offline_chain.total_difficulty:
                winner = online_chain if online_chain.total_difficulty > offline_chain.total_difficulty else offline_chain
                return ForkResolution(
                    winning_chain=winner,
                    reason="Difficulty difference",
                    is_suspicious=False,
                    metrics={
                        "online": online_metrics,
                        "offline": offline_metrics
                    }
                )
                
            # Same difficulty - check quorum votes
            if online_chain.quorum_votes >= self.min_quorum_votes:
                return ForkResolution(
                    winning_chain=online_chain,
                    reason="Online quorum validation",
                    is_suspicious=False,
                    metrics={
                        "online": online_metrics,
                        "offline": offline_metrics
                    }
                )
                
            # Check for suspicious patterns
            is_suspicious = self._is_fork_suspicious(
                online_chain,
                offline_chain,
                online_metrics,
                offline_metrics
            )
            
            if is_suspicious:
                self._queue_for_audit(online_chain, offline_chain)
                
            # Default to online chain with warning
            return ForkResolution(
                winning_chain=online_chain,
                reason="Default to online chain",
                is_suspicious=is_suspicious,
                metrics={
                    "online": online_metrics,
                    "offline": offline_metrics
                }
            )
            
        except Exception as e:
            # On error, default to online chain
            return ForkResolution(
                winning_chain=online_chain,
                reason=f"Error in resolution: {str(e)}",
                is_suspicious=True,
                metrics={
                    "online": {},
                    "offline": {}
                }
            )
            
    def _calculate_chain_metrics(self, chain: ChainInfo) -> Dict:
        """Calculate metrics for chain analysis"""
        current_time = time.time()
        
        return {
            "length": len(chain.blocks),
            "difficulty": chain.total_difficulty,
            "quorum_votes": chain.quorum_votes,
            "avg_block_time": self._calculate_avg_block_time(chain.blocks),
            "time_since_last": current_time - chain.last_block_time,
            "mode": chain.mode.value
        }
        
    def _calculate_avg_block_time(self, blocks: List[Dict]) -> float:
        """Calculate average time between blocks"""
        if len(blocks) < 2:
            return 0
            
        times = [b.get('timestamp', 0) for b in blocks]
        differences = [t2 - t1 for t1, t2 in zip(times[:-1], times[1:])]
        
        return sum(differences) / len(differences)
        
    def _is_fork_suspicious(
        self,
        online_chain: ChainInfo,
        offline_chain: ChainInfo,
        online_metrics: Dict,
        offline_metrics: Dict
    ) -> bool:
        """Check for suspicious patterns in fork"""
        # Check time difference between chains
        time_diff = abs(
            online_chain.last_block_time -
            offline_chain.last_block_time
        )
        if time_diff > self.max_time_difference:
            return True
            
        # Check for unusual difficulty changes
        if self._has_unusual_difficulty(online_chain.blocks):
            return True
            
        if self._has_unusual_difficulty(offline_chain.blocks):
            return True
            
        # Check for missing quorum votes
        if online_chain.quorum_votes < self.min_quorum_votes:
            return True
            
        return False
        
    def _has_unusual_difficulty(self, blocks: List[Dict]) -> bool:
        """Check for unusual difficulty adjustments"""
        if len(blocks) < 3:
            return False
            
        difficulties = [b.get('difficulty', 0) for b in blocks]
        changes = [d2/d1 if d1 > 0 else 1 for d1, d2 in zip(difficulties[:-1], difficulties[1:])]
        
        return any(c > 2 or c < 0.5 for c in changes)
        
    def _queue_for_audit(
        self,
        online_chain: ChainInfo,
        offline_chain: ChainInfo
    ):
        """Add suspicious fork to audit queue"""
        self.audit_queue.append((online_chain, offline_chain))
        
    def get_audit_queue(self) -> List[Tuple[ChainInfo, ChainInfo]]:
        """Get list of suspicious forks for audit"""
        return self.audit_queue.copy()
        
    def clear_audit_queue(self):
        """Clear the audit queue"""
        self.audit_queue.clear() 