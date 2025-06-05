"""
Timelock validation system with secure time constraints
"""

import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class TimelockState(Enum):
    PENDING = "PENDING"
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"

@dataclass
class TimelockConstraint:
    """Time constraint definition"""
    start_time: float
    end_time: float
    min_blocks: int
    max_blocks: int
    required_confirmations: int
    grace_period: float
    
@dataclass
class TimelockValidation:
    """Validation state with timelock"""
    validation_id: str
    constraint: TimelockConstraint
    current_state: TimelockState
    block_height: int
    confirmation_count: int
    last_update: float
    hash_chain: List[str]
    
class TimelockValidator:
    def __init__(self):
        self.min_lock_time = 300  # 5 minutes
        self.max_lock_time = 86400  # 24 hours
        self.min_confirmations = 6
        self.max_grace_period = 3600  # 1 hour
        
        self.validations: Dict[str, TimelockValidation] = {}
        self.constraints: Dict[str, TimelockConstraint] = {}
        
    def create_timelock(
        self,
        start_time: float,
        duration: float,
        min_blocks: int,
        required_confirmations: int,
        grace_period: float
    ) -> Optional[str]:
        """Create new timelock constraint"""
        try:
            # Validate parameters
            if not self._validate_timelock_params(
                start_time,
                duration,
                min_blocks,
                required_confirmations,
                grace_period
            ):
                return None
                
            # Calculate end time
            end_time = start_time + duration
            
            # Create constraint
            constraint = TimelockConstraint(
                start_time=start_time,
                end_time=end_time,
                min_blocks=min_blocks,
                max_blocks=min_blocks * 2,  # Double min blocks for max
                required_confirmations=required_confirmations,
                grace_period=grace_period
            )
            
            # Generate ID
            constraint_id = self._generate_constraint_id(constraint)
            
            # Store constraint
            self.constraints[constraint_id] = constraint
            
            return constraint_id
            
        except Exception as e:
            print(f"Error creating timelock: {e}")
            return None
            
    def start_validation(
        self,
        constraint_id: str,
        block_height: int
    ) -> Optional[str]:
        """Start timelock validation"""
        try:
            # Get constraint
            constraint = self.constraints.get(constraint_id)
            if not constraint:
                return None
                
            # Check if validation can start
            current_time = time.time()
            if current_time < constraint.start_time:
                return None
                
            # Create validation
            validation_id = self._generate_validation_id(
                constraint_id,
                block_height
            )
            
            validation = TimelockValidation(
                validation_id=validation_id,
                constraint=constraint,
                current_state=TimelockState.PENDING,
                block_height=block_height,
                confirmation_count=0,
                last_update=current_time,
                hash_chain=[]
            )
            
            # Store validation
            self.validations[validation_id] = validation
            
            return validation_id
            
        except Exception as e:
            print(f"Error starting validation: {e}")
            return None
            
    def update_validation(
        self,
        validation_id: str,
        current_height: int,
        block_hash: str
    ) -> bool:
        """Update validation state"""
        try:
            # Get validation
            validation = self.validations.get(validation_id)
            if not validation:
                return False
                
            # Check if expired
            if self._is_validation_expired(validation):
                validation.current_state = TimelockState.EXPIRED
                return False
                
            # Update state
            current_time = time.time()
            blocks_passed = current_height - validation.block_height
            
            # Check block constraints
            if blocks_passed < validation.constraint.min_blocks:
                validation.current_state = TimelockState.LOCKED
                
            elif blocks_passed > validation.constraint.max_blocks:
                validation.current_state = TimelockState.EXPIRED
                return False
                
            # Update confirmations
            if blocks_passed >= validation.constraint.min_blocks:
                validation.confirmation_count += 1
                
            # Add to hash chain
            validation.hash_chain.append(block_hash)
            
            # Check if can unlock
            if (validation.confirmation_count >= 
                validation.constraint.required_confirmations):
                validation.current_state = TimelockState.UNLOCKED
                
            validation.last_update = current_time
            return True
            
        except Exception as e:
            print(f"Error updating validation: {e}")
            return False
            
    def verify_validation(
        self,
        validation_id: str
    ) -> Tuple[bool, TimelockState]:
        """Verify validation state"""
        try:
            # Get validation
            validation = self.validations.get(validation_id)
            if not validation:
                return False, TimelockState.INVALID
                
            # Check expiration
            if self._is_validation_expired(validation):
                validation.current_state = TimelockState.EXPIRED
                return False, TimelockState.EXPIRED
                
            # Verify hash chain
            if not self._verify_hash_chain(validation):
                validation.current_state = TimelockState.INVALID
                return False, TimelockState.INVALID
                
            return True, validation.current_state
            
        except Exception:
            return False, TimelockState.INVALID
            
    def _validate_timelock_params(
        self,
        start_time: float,
        duration: float,
        min_blocks: int,
        required_confirmations: int,
        grace_period: float
    ) -> bool:
        """Validate timelock parameters"""
        current_time = time.time()
        
        # Check times
        if start_time < current_time:
            return False
            
        if duration < self.min_lock_time:
            return False
            
        if duration > self.max_lock_time:
            return False
            
        # Check blocks
        if min_blocks < 1:
            return False
            
        # Check confirmations
        if required_confirmations < self.min_confirmations:
            return False
            
        # Check grace period
        if grace_period < 0 or grace_period > self.max_grace_period:
            return False
            
        return True
        
    def _generate_constraint_id(
        self,
        constraint: TimelockConstraint
    ) -> str:
        """Generate unique constraint ID"""
        constraint_data = (
            f"{constraint.start_time}:"
            f"{constraint.end_time}:"
            f"{constraint.min_blocks}:"
            f"{constraint.required_confirmations}:"
            f"{constraint.grace_period}"
        )
        return hashlib.sha256(constraint_data.encode()).hexdigest()
        
    def _generate_validation_id(
        self,
        constraint_id: str,
        block_height: int
    ) -> str:
        """Generate unique validation ID"""
        validation_data = f"{constraint_id}:{block_height}:{time.time()}"
        return hashlib.sha256(validation_data.encode()).hexdigest()
        
    def _is_validation_expired(
        self,
        validation: TimelockValidation
    ) -> bool:
        """Check if validation is expired"""
        current_time = time.time()
        
        # Check end time
        if current_time > validation.constraint.end_time:
            return True
            
        # Check grace period
        if (current_time - validation.last_update >
            validation.constraint.grace_period):
            return True
            
        return False
        
    def _verify_hash_chain(
        self,
        validation: TimelockValidation
    ) -> bool:
        """Verify validation hash chain"""
        try:
            if not validation.hash_chain:
                return False
                
            # Verify chain is continuous
            for i in range(1, len(validation.hash_chain)):
                current_hash = validation.hash_chain[i]
                previous_hash = validation.hash_chain[i - 1]
                
                # Verify link
                if not self._verify_hash_link(
                    previous_hash,
                    current_hash
                ):
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def _verify_hash_link(
        self,
        previous_hash: str,
        current_hash: str
    ) -> bool:
        """Verify hash chain link"""
        try:
            # Hash previous + current
            combined = f"{previous_hash}:{current_hash}"
            link_hash = hashlib.sha256(combined.encode()).hexdigest()
            
            # Verify link hash exists in chain
            return link_hash in self.validations
            
        except Exception:
            return False 