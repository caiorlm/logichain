"""
Blockchain governance system.
Implements proposal management, voting, and execution of governance decisions.
"""

from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum
import time
import json
import hashlib
import logging
from datetime import datetime, timedelta

class ProposalType(Enum):
    """Types of governance proposals"""
    PARAMETER_CHANGE = "parameter_change"
    PROTOCOL_UPGRADE = "protocol_upgrade"
    TREASURY = "treasury"
    EMERGENCY = "emergency"
    GENERAL = "general"

class ProposalStatus(Enum):
    """Status of governance proposals"""
    PENDING = "pending"
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"

@dataclass
class VotingPower:
    """Voting power calculation parameters"""
    stake_weight: float = 0.7  # Weight of staked tokens
    reputation_weight: float = 0.2  # Weight of reputation
    age_weight: float = 0.1  # Weight of account age

@dataclass
class VotingConfig:
    """Voting configuration"""
    quorum: float = 0.4  # Minimum participation (40%)
    threshold: float = 0.6  # Minimum approval (60%)
    voting_period: int = 7 * 24 * 3600  # 7 days in seconds
    execution_delay: int = 24 * 3600  # 24 hours in seconds
    min_deposit: int = 1000  # Minimum deposit for proposal

class Proposal:
    """Governance proposal"""
    
    def __init__(self,
                 id: str,
                 type: ProposalType,
                 title: str,
                 description: str,
                 proposer: str,
                 deposit: int,
                 changes: Dict[str, Any],
                 voting_config: Optional[VotingConfig] = None):
        self.id = id
        self.type = type
        self.title = title
        self.description = description
        self.proposer = proposer
        self.deposit = deposit
        self.changes = changes
        self.config = voting_config or VotingConfig()
        
        # Voting state
        self.status = ProposalStatus.PENDING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.execution_time: Optional[float] = None
        self.votes: Dict[str, bool] = {}  # voter -> vote
        self.vote_weights: Dict[str, float] = {}  # voter -> weight
        self.total_weight = 0
        self.yes_weight = 0
        
        # Execution state
        self.executed = False
        self.execution_error: Optional[str] = None
    
    def start_voting(self, start_time: Optional[float] = None):
        """Start voting period"""
        self.start_time = start_time or time.time()
        self.end_time = self.start_time + self.config.voting_period
        self.status = ProposalStatus.ACTIVE
    
    def add_vote(self, voter: str, vote: bool, weight: float):
        """Add weighted vote"""
        if self.status != ProposalStatus.ACTIVE:
            raise ValueError("Voting is not active")
            
        if time.time() > self.end_time:
            raise ValueError("Voting period has ended")
            
        # Update vote
        self.votes[voter] = vote
        self.vote_weights[voter] = weight
        
        # Update totals
        self.total_weight = sum(self.vote_weights.values())
        self.yes_weight = sum(
            weight for voter, weight in self.vote_weights.items()
            if self.votes[voter]
        )
    
    def finalize(self) -> bool:
        """
        Finalize voting and determine result
        Returns True if proposal passed
        """
        if self.status != ProposalStatus.ACTIVE:
            return False
            
        # Check quorum
        participation = self.total_weight / self.config.quorum
        if participation < self.config.quorum:
            self.status = ProposalStatus.REJECTED
            return False
            
        # Check approval
        approval = self.yes_weight / self.total_weight
        passed = approval >= self.config.threshold
        
        self.status = ProposalStatus.PASSED if passed else ProposalStatus.REJECTED
        
        if passed:
            self.execution_time = time.time() + self.config.execution_delay
            
        return passed
    
    def to_dict(self) -> Dict:
        """Convert proposal to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'title': self.title,
            'description': self.description,
            'proposer': self.proposer,
            'deposit': self.deposit,
            'changes': self.changes,
            'status': self.status.value,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'execution_time': self.execution_time,
            'total_weight': self.total_weight,
            'yes_weight': self.yes_weight,
            'executed': self.executed,
            'execution_error': self.execution_error
        }

class Governance:
    """Main governance system"""
    
    def __init__(self,
                 voting_power: Optional[VotingPower] = None,
                 voting_config: Optional[VotingConfig] = None):
        self.voting_power = voting_power or VotingPower()
        self.voting_config = voting_config or VotingConfig()
        
        # State
        self.proposals: Dict[str, Proposal] = {}
        self.parameters: Dict[str, Any] = {}
        self.stake_data: Dict[str, float] = {}
        self.reputation: Dict[str, float] = {}
        self.join_times: Dict[str, float] = {}
        
        # Execution handlers
        self.execution_handlers = {
            ProposalType.PARAMETER_CHANGE: self._execute_parameter_change,
            ProposalType.PROTOCOL_UPGRADE: self._execute_protocol_upgrade,
            ProposalType.TREASURY: self._execute_treasury,
            ProposalType.EMERGENCY: self._execute_emergency
        }
    
    def create_proposal(self,
                       type: ProposalType,
                       title: str,
                       description: str,
                       proposer: str,
                       deposit: int,
                       changes: Dict[str, Any]) -> str:
        """
        Create new governance proposal
        
        Args:
            type: Proposal type
            title: Proposal title
            description: Detailed description
            proposer: Address of proposer
            deposit: Deposit amount
            changes: Proposed changes
            
        Returns:
            str: Proposal ID
        """
        # Validate deposit
        if deposit < self.voting_config.min_deposit:
            raise ValueError(f"Deposit too low. Minimum: {self.voting_config.min_deposit}")
            
        # Generate proposal ID
        proposal_id = hashlib.sha256(
            f"{proposer}-{title}-{time.time()}".encode()
        ).hexdigest()
        
        # Create proposal
        proposal = Proposal(
            id=proposal_id,
            type=type,
            title=title,
            description=description,
            proposer=proposer,
            deposit=deposit,
            changes=changes,
            voting_config=self.voting_config
        )
        
        # Store proposal
        self.proposals[proposal_id] = proposal
        
        return proposal_id
    
    def activate_proposal(self, proposal_id: str):
        """Activate proposal and start voting period"""
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
            
        proposal = self.proposals[proposal_id]
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError("Proposal cannot be activated")
            
        proposal.start_voting()
    
    def vote(self, proposal_id: str, voter: str, vote: bool):
        """Cast vote on proposal"""
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
            
        proposal = self.proposals[proposal_id]
        
        # Calculate voting weight
        weight = self._calculate_voting_weight(voter)
        
        # Add vote
        proposal.add_vote(voter, vote, weight)
    
    def _calculate_voting_weight(self, voter: str) -> float:
        """Calculate voter's voting weight"""
        # Get components
        stake = self.stake_data.get(voter, 0)
        reputation = self.reputation.get(voter, 0)
        age = time.time() - self.join_times.get(voter, time.time())
        max_age = 365 * 24 * 3600  # 1 year
        age_factor = min(age / max_age, 1)
        
        # Calculate weighted sum
        weight = (
            stake * self.voting_power.stake_weight +
            reputation * self.voting_power.reputation_weight +
            age_factor * self.voting_power.age_weight
        )
        
        return weight
    
    def finalize_proposal(self, proposal_id: str) -> bool:
        """
        Finalize proposal voting
        Returns True if proposal passed
        """
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
            
        proposal = self.proposals[proposal_id]
        return proposal.finalize()
    
    def execute_proposal(self, proposal_id: str) -> bool:
        """
        Execute passed proposal
        Returns True if execution successful
        """
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
            
        proposal = self.proposals[proposal_id]
        
        if proposal.status != ProposalStatus.PASSED:
            return False
            
        if time.time() < proposal.execution_time:
            return False
            
        try:
            # Get execution handler
            handler = self.execution_handlers.get(proposal.type)
            if not handler:
                raise ValueError(f"No handler for proposal type: {proposal.type}")
                
            # Execute changes
            handler(proposal.changes)
            
            proposal.executed = True
            proposal.status = ProposalStatus.EXECUTED
            return True
            
        except Exception as e:
            proposal.execution_error = str(e)
            proposal.status = ProposalStatus.FAILED
            logging.error(f"Proposal execution failed: {e}")
            return False
    
    def _execute_parameter_change(self, changes: Dict[str, Any]):
        """Execute parameter change proposal"""
        for param, value in changes.items():
            if param not in self.parameters:
                raise ValueError(f"Invalid parameter: {param}")
            self.parameters[param] = value
    
    def _execute_protocol_upgrade(self, changes: Dict[str, Any]):
        """Execute protocol upgrade proposal"""
        version = changes.get('version')
        if not version:
            raise ValueError("No version specified")
            
        # Protocol upgrade logic here
        pass
    
    def _execute_treasury(self, changes: Dict[str, Any]):
        """Execute treasury proposal"""
        recipient = changes.get('recipient')
        amount = changes.get('amount')
        
        if not recipient or not amount:
            raise ValueError("Invalid treasury proposal")
            
        # Treasury transfer logic here
        pass
    
    def _execute_emergency(self, changes: Dict[str, Any]):
        """Execute emergency proposal"""
        action = changes.get('action')
        if not action:
            raise ValueError("No action specified")
            
        # Emergency action logic here
        pass
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Get proposal details"""
        if proposal_id not in self.proposals:
            return None
            
        return self.proposals[proposal_id].to_dict()
    
    def get_active_proposals(self) -> List[Dict]:
        """Get list of active proposals"""
        now = time.time()
        return [
            proposal.to_dict()
            for proposal in self.proposals.values()
            if proposal.status == ProposalStatus.ACTIVE
            and proposal.end_time > now
        ]
    
    def get_pending_executions(self) -> List[Dict]:
        """Get list of proposals pending execution"""
        now = time.time()
        return [
            proposal.to_dict()
            for proposal in self.proposals.values()
            if proposal.status == ProposalStatus.PASSED
            and not proposal.executed
            and proposal.execution_time <= now
        ]
    
    def update_stake(self, address: str, amount: float):
        """Update staked amount for address"""
        self.stake_data[address] = amount
    
    def update_reputation(self, address: str, score: float):
        """Update reputation score for address"""
        self.reputation[address] = max(0, min(1, score))
    
    def register_join_time(self, address: str, timestamp: Optional[float] = None):
        """Register join time for new address"""
        self.join_times[address] = timestamp or time.time() 