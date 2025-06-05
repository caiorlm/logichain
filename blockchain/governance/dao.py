"""
LogiChain DAO System
Implements reputation-weighted governance with on-chain audit
"""

from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum
import time
import json
import hashlib
import logging
from datetime import datetime, timedelta
from ..core.blockchain import Blockchain
from ..storage.database import BlockchainDB
from ..security.crypto import CryptoManager

class ProposalType(Enum):
    """Types of governance proposals"""
    PARAMETER_CHANGE = "parameter_change"
    PROTOCOL_UPGRADE = "protocol_upgrade"
    TREASURY = "treasury"
    EMERGENCY = "emergency"
    POOL_MANAGEMENT = "pool_management"
    NODE_MANAGEMENT = "node_management"
    REPUTATION_UPDATE = "reputation_update"

@dataclass
class VotingPower:
    """Voting power calculation with reputation"""
    stake_weight: float = 0.4  # Weight of staked tokens
    reputation_weight: float = 0.4  # Weight of reputation
    activity_weight: float = 0.2  # Weight of recent activity

@dataclass
class ProposalConfig:
    """Proposal configuration"""
    min_stake: float  # Minimum stake to create proposal
    voting_period: int  # Voting period in seconds
    execution_delay: int  # Delay before execution
    quorum: float  # Minimum participation required
    majority: float  # Required majority to pass

class VoteRecord:
    """Immutable vote record for on-chain audit"""
    def __init__(
        self,
        voter: str,
        proposal_id: str,
        vote: bool,
        stake_weight: float,
        reputation_weight: float,
        activity_weight: float,
        timestamp: float
    ):
        self.voter = voter
        self.proposal_id = proposal_id
        self.vote = vote
        self.stake_weight = stake_weight
        self.reputation_weight = reputation_weight
        self.activity_weight = activity_weight
        self.timestamp = timestamp
        self.vote_hash = self._calculate_hash()
        
    def _calculate_hash(self) -> str:
        """Calculate immutable vote hash"""
        vote_data = f"{self.voter}{self.proposal_id}{self.vote}{self.stake_weight}{self.reputation_weight}{self.activity_weight}{self.timestamp}"
        return hashlib.sha256(vote_data.encode()).hexdigest()
        
    def to_dict(self) -> Dict:
        return {
            "voter": self.voter,
            "proposal_id": self.proposal_id,
            "vote": self.vote,
            "stake_weight": self.stake_weight,
            "reputation_weight": self.reputation_weight,
            "activity_weight": self.activity_weight,
            "timestamp": self.timestamp,
            "vote_hash": self.vote_hash
        }

class LogiChainDAO:
    """Main DAO implementation"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        db: BlockchainDB,
        crypto: CryptoManager,
        config: Optional[ProposalConfig] = None
    ):
        self.blockchain = blockchain
        self.db = db
        self.crypto = crypto
        self.config = config or ProposalConfig(
            min_stake=1000.0,
            voting_period=7 * 24 * 3600,  # 7 days
            execution_delay=24 * 3600,  # 24 hours
            quorum=0.4,  # 40% participation
            majority=0.6  # 60% majority
        )
        
        # State
        self.proposals: Dict[str, Any] = {}
        self.votes: Dict[str, List[VoteRecord]] = {}  # proposal_id -> votes
        self.stake_data: Dict[str, float] = {}
        self.reputation_data: Dict[str, float] = {}
        self.activity_data: Dict[str, List[float]] = {}  # address -> timestamps
        
    def create_proposal(
        self,
        proposer: str,
        proposal_type: ProposalType,
        title: str,
        description: str,
        changes: Dict[str, Any]
    ) -> str:
        """Create new proposal"""
        # Verify proposer stake
        if self.stake_data.get(proposer, 0) < self.config.min_stake:
            raise ValueError(f"Insufficient stake. Required: {self.config.min_stake}")
            
        # Generate proposal ID
        proposal_id = hashlib.sha256(
            f"{proposer}{title}{time.time()}".encode()
        ).hexdigest()
        
        # Create proposal
        proposal = {
            "id": proposal_id,
            "type": proposal_type.value,
            "proposer": proposer,
            "title": title,
            "description": description,
            "changes": changes,
            "status": "active",
            "created_at": time.time(),
            "ends_at": time.time() + self.config.voting_period,
            "execution_time": None,
            "total_weight": 0,
            "yes_weight": 0,
            "vote_count": 0
        }
        
        # Store proposal
        self.proposals[proposal_id] = proposal
        self.votes[proposal_id] = []
        
        # Record on chain
        self._record_proposal(proposal)
        
        return proposal_id
        
    def cast_vote(
        self,
        proposal_id: str,
        voter: str,
        vote: bool
    ) -> bool:
        """Cast vote on proposal"""
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
            
        proposal = self.proposals[proposal_id]
        if proposal["status"] != "active":
            raise ValueError("Proposal is not active")
            
        if time.time() > proposal["ends_at"]:
            raise ValueError("Voting period has ended")
            
        # Calculate voting weights
        stake_power = self._calculate_stake_power(voter)
        reputation_power = self._calculate_reputation_power(voter)
        activity_power = self._calculate_activity_power(voter)
        
        total_power = (
            stake_power * self.config.stake_weight +
            reputation_power * self.config.reputation_weight +
            activity_power * self.config.activity_weight
        )
        
        # Create vote record
        vote_record = VoteRecord(
            voter=voter,
            proposal_id=proposal_id,
            vote=vote,
            stake_weight=stake_power,
            reputation_weight=reputation_power,
            activity_weight=activity_power,
            timestamp=time.time()
        )
        
        # Update proposal state
        proposal["total_weight"] += total_power
        if vote:
            proposal["yes_weight"] += total_power
        proposal["vote_count"] += 1
        
        # Store vote
        self.votes[proposal_id].append(vote_record)
        
        # Record on chain
        self._record_vote(vote_record)
        
        return True
        
    def finalize_proposal(self, proposal_id: str) -> bool:
        """Finalize proposal and determine result"""
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
            
        proposal = self.proposals[proposal_id]
        if proposal["status"] != "active":
            return False
            
        # Check if voting period ended
        if time.time() <= proposal["ends_at"]:
            return False
            
        # Calculate result
        total_possible_weight = sum(
            self._calculate_total_power(voter)
            for voter in self.stake_data.keys()
        )
        
        participation = proposal["total_weight"] / total_possible_weight
        if participation < self.config.quorum:
            proposal["status"] = "rejected"
            self._record_result(proposal_id, "rejected", "Insufficient quorum")
            return False
            
        approval = proposal["yes_weight"] / proposal["total_weight"]
        passed = approval >= self.config.majority
        
        if passed:
            proposal["status"] = "passed"
            proposal["execution_time"] = time.time() + self.config.execution_delay
        else:
            proposal["status"] = "rejected"
            
        # Record result
        self._record_result(
            proposal_id,
            proposal["status"],
            f"Approval: {approval:.2%}, Participation: {participation:.2%}"
        )
        
        return passed
        
    def _calculate_stake_power(self, voter: str) -> float:
        """Calculate stake-based voting power"""
        return self.stake_data.get(voter, 0)
        
    def _calculate_reputation_power(self, voter: str) -> float:
        """Calculate reputation-based voting power"""
        return self.reputation_data.get(voter, 0)
        
    def _calculate_activity_power(self, voter: str) -> float:
        """Calculate activity-based voting power"""
        if voter not in self.activity_data:
            return 0
            
        recent_activities = [
            ts for ts in self.activity_data[voter]
            if time.time() - ts < 30 * 24 * 3600  # Last 30 days
        ]
        
        return len(recent_activities)
        
    def _calculate_total_power(self, voter: str) -> float:
        """Calculate total voting power"""
        return (
            self._calculate_stake_power(voter) * self.config.stake_weight +
            self._calculate_reputation_power(voter) * self.config.reputation_weight +
            self._calculate_activity_power(voter) * self.config.activity_weight
        )
        
    def _record_proposal(self, proposal: Dict):
        """Record proposal on chain"""
        self.blockchain.add_transaction(
            from_address="0",  # System
            to_address="0",  # System
            amount=0,
            data={
                "type": "dao_proposal",
                "proposal": proposal
            }
        )
        
    def _record_vote(self, vote: VoteRecord):
        """Record vote on chain"""
        self.blockchain.add_transaction(
            from_address=vote.voter,
            to_address="0",  # System
            amount=0,
            data={
                "type": "dao_vote",
                "vote": vote.to_dict()
            }
        )
        
    def _record_result(self, proposal_id: str, result: str, details: str):
        """Record proposal result on chain"""
        self.blockchain.add_transaction(
            from_address="0",  # System
            to_address="0",  # System
            amount=0,
            data={
                "type": "dao_result",
                "proposal_id": proposal_id,
                "result": result,
                "details": details,
                "timestamp": time.time()
            }
        )
        
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Get proposal details with votes"""
        if proposal_id not in self.proposals:
            return None
            
        proposal = self.proposals[proposal_id].copy()
        proposal["votes"] = [
            vote.to_dict() for vote in self.votes[proposal_id]
        ]
        
        return proposal
        
    def get_voter_power(self, voter: str) -> Dict[str, float]:
        """Get voter's power breakdown"""
        return {
            "stake_power": self._calculate_stake_power(voter),
            "reputation_power": self._calculate_reputation_power(voter),
            "activity_power": self._calculate_activity_power(voter),
            "total_power": self._calculate_total_power(voter)
        }
        
    def update_stake(self, address: str, amount: float):
        """Update staked amount"""
        self.stake_data[address] = amount
        
    def update_reputation(self, address: str, score: float):
        """Update reputation score"""
        self.reputation_data[address] = max(0, min(1, score))
        
    def record_activity(self, address: str):
        """Record activity for power calculation"""
        if address not in self.activity_data:
            self.activity_data[address] = []
        self.activity_data[address].append(time.time()) 