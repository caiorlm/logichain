"""
LogiChain Reputation System
Manages node reputation with decay for inactivity
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
from ..storage.database import BlockchainDB

@dataclass
class ReputationConfig:
    """Configuration for reputation system"""
    # Decay percentage per interval (10%)
    DECAY_RATE: float = 0.10
    
    # Blocks between decay checks (10k blocks)
    DECAY_INTERVAL: int = 10_000
    
    # Minimum reputation score
    MIN_REPUTATION: float = 0.0
    
    # Maximum reputation score
    MAX_REPUTATION: float = 1.0
    
    # Initial reputation for new nodes
    INITIAL_REPUTATION: float = 0.5
    
    # Reputation gain for successful validation
    VALIDATION_REWARD: float = 0.01
    
    # Reputation gain for successful PoD
    POD_REWARD: float = 0.02
    
    # Reputation loss for failed validation
    VALIDATION_PENALTY: float = 0.05
    
    # Reputation loss for failed PoD
    POD_PENALTY: float = 0.1

@dataclass
class NodeActivity:
    """Tracks node activity for decay calculation"""
    last_active_block: int
    last_decay_block: int
    reputation: float

class ReputationManager:
    """Manages node reputation scores with decay"""
    
    def __init__(
        self,
        db: BlockchainDB,
        config: Optional[ReputationConfig] = None
    ):
        self.db = db
        self.config = config or ReputationConfig()
        self._load_activities()
        
    def _load_activities(self):
        """Load node activities from database"""
        self.activities: Dict[str, NodeActivity] = {}
        
        # Get current scores and activities
        scores = self.db.get_reputation_scores()
        activities = self.db.get_node_activities()
        
        # Initialize activities
        for node_id, score in scores.items():
            activity = activities.get(node_id, {})
            self.activities[node_id] = NodeActivity(
                last_active_block=activity.get(
                    "last_active_block",
                    0
                ),
                last_decay_block=activity.get(
                    "last_decay_block",
                    0
                ),
                reputation=score
            )
            
    def get_reputation(self, node_id: str) -> float:
        """Get current reputation score for node"""
        if node_id not in self.activities:
            # Initialize new node
            self.activities[node_id] = NodeActivity(
                last_active_block=0,
                last_decay_block=0,
                reputation=self.config.INITIAL_REPUTATION
            )
            self._save_node(node_id)
            
        return self.activities[node_id].reputation
        
    def record_activity(
        self,
        node_id: str,
        block_height: int,
        success: bool = True,
        activity_type: str = "validation"
    ):
        """Record node activity and update reputation"""
        # Get or create activity record
        activity = self.activities.get(
            node_id,
            NodeActivity(
                last_active_block=0,
                last_decay_block=0,
                reputation=self.config.INITIAL_REPUTATION
            )
        )
        
        # Update activity timestamp
        activity.last_active_block = block_height
        
        # Apply reputation change
        if success:
            if activity_type == "validation":
                self._increase_reputation(
                    activity,
                    self.config.VALIDATION_REWARD
                )
            elif activity_type == "pod":
                self._increase_reputation(
                    activity,
                    self.config.POD_REWARD
                )
        else:
            if activity_type == "validation":
                self._decrease_reputation(
                    activity,
                    self.config.VALIDATION_PENALTY
                )
            elif activity_type == "pod":
                self._decrease_reputation(
                    activity,
                    self.config.POD_PENALTY
                )
                
        # Save updated activity
        self.activities[node_id] = activity
        self._save_node(node_id)
        
    def process_decay(self, current_block: int):
        """Process reputation decay for inactive nodes"""
        for node_id, activity in self.activities.items():
            # Check if decay interval passed
            blocks_since_decay = (
                current_block - activity.last_decay_block
            )
            
            if blocks_since_decay >= self.config.DECAY_INTERVAL:
                # Calculate decay periods
                decay_periods = blocks_since_decay // (
                    self.config.DECAY_INTERVAL
                )
                
                # Apply decay for each period
                for _ in range(decay_periods):
                    self._apply_decay(activity)
                    
                # Update decay block
                activity.last_decay_block = current_block - (
                    blocks_since_decay % self.config.DECAY_INTERVAL
                )
                
                # Save updated activity
                self._save_node(node_id)
                
    def _increase_reputation(
        self,
        activity: NodeActivity,
        amount: float
    ):
        """Increase node reputation"""
        activity.reputation = min(
            activity.reputation + amount,
            self.config.MAX_REPUTATION
        )
        
    def _decrease_reputation(
        self,
        activity: NodeActivity,
        amount: float
    ):
        """Decrease node reputation"""
        activity.reputation = max(
            activity.reputation - amount,
            self.config.MIN_REPUTATION
        )
        
    def _apply_decay(self, activity: NodeActivity):
        """Apply reputation decay"""
        decay_amount = activity.reputation * self.config.DECAY_RATE
        self._decrease_reputation(activity, decay_amount)
        
    def _save_node(self, node_id: str):
        """Save node activity and reputation to database"""
        activity = self.activities[node_id]
        
        # Save reputation score
        self.db.set_reputation_score(
            node_id,
            activity.reputation
        )
        
        # Save activity data
        self.db.set_node_activity(
            node_id,
            {
                "last_active_block": activity.last_active_block,
                "last_decay_block": activity.last_decay_block
            }
        ) 