"""
LogiChain Smart Contract System with Reputation Requirements
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import hashlib
import json
import time
from enum import Enum
import threading
from datetime import datetime, timedelta
import logging
from ..reputation.reputation_system import ReputationType, ReputationManager

class ContractStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REPUTATION_ADJUSTED = "reputation_adjusted"

@dataclass
class ContractRequirements:
    min_pool_reputation: float = 0.0
    min_driver_reputation: float = 0.0
    min_establishment_reputation: float = 0.0
    allow_reputation_adjustment: bool = True
    reputation_adjustment_delay: int = 60  # minutes
    reputation_adjustment_steps: int = 2

@dataclass
class ContractEvent:
    """Contract event"""
    name: str
    data: Dict[str, Any]
    timestamp: float
    contract_id: str

class SmartContract:
    """Smart contract with reputation requirements"""
    
    def __init__(
        self,
        contract_id: str,
        client_address: str,
        value: float,
        pickup_location: Dict[str, float],
        delivery_location: Dict[str, float],
        requirements: ContractRequirements = None,
        reputation_manager: ReputationManager = None
    ):
        self.contract_id = contract_id
        self.client_address = client_address
        self.value = value
        self.pickup_location = pickup_location
        self.delivery_location = delivery_location
        self.requirements = requirements or ContractRequirements()
        self.reputation_manager = reputation_manager
        
        # Contract state
        self.status = ContractStatus.PENDING
        self.driver_address = None
        self.pool_address = None
        self.creation_time = datetime.now()
        self.acceptance_time = None
        self.completion_time = None
        
        # Reputation adjustment tracking
        self.original_requirements = requirements
        self.adjustment_count = 0
        self.last_adjustment_time = None
        
        self.events: List[ContractEvent] = []
        self.created_at = time.time()
        self._reentrancy_lock = threading.Lock()
        self._execution_depth = 0
        self._MAX_EXECUTION_DEPTH = 8
        
    def execute(
        self,
        method: str,
        params: Dict[str, Any],
        sender: str
    ) -> Dict[str, Any]:
        """
        Execute contract method with reentrancy protection
        """
        try:
            # Reentrancy protection
            if not self._reentrancy_lock.acquire(blocking=False):
                raise ValueError("Reentrant call detected")
                
            # Check max depth
            self._execution_depth += 1
            if self._execution_depth > self._MAX_EXECUTION_DEPTH:
                raise ValueError("Max execution depth exceeded")
                
            # Validations
            if not self._validate_method(method):
                raise ValueError(f"Invalid method: {method}")
                
            if not self._validate_params(method, params):
                raise ValueError(f"Invalid parameters for method: {method}")
                
            if not self._check_permissions(method, sender):
                raise ValueError(f"Permission denied for sender: {sender}")
                
            # Execute
            self.status = ContractStatus.ACCEPTED
            result = self._execute_method(method, params, sender)
            
            return result
            
        finally:
            self._execution_depth -= 1
            self._reentrancy_lock.release()
            
    def get_state(self) -> Dict[str, Any]:
        """Return current contract state"""
        return {
            "contract_id": self.contract_id,
            "client_address": self.client_address,
            "driver_address": self.driver_address,
            "pool_address": self.pool_address,
            "value": self.value,
            "pickup_location": self.pickup_location,
            "delivery_location": self.delivery_location,
            "status": self.status.value,
            "creation_time": self.creation_time.isoformat(),
            "acceptance_time": self.acceptance_time.isoformat() if self.acceptance_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "requirements": {
                "min_driver_reputation": self.requirements.min_driver_reputation,
                "min_pool_reputation": self.requirements.min_pool_reputation,
                "min_establishment_reputation": self.requirements.min_establishment_reputation,
                "allow_adjustment": self.requirements.allow_reputation_adjustment,
                "adjustment_delay": self.requirements.reputation_adjustment_delay,
                "adjustment_steps": self.requirements.adjustment_steps
            }
        }
        
    def get_events(
        self,
        event_name: Optional[str] = None,
        start_time: Optional[float] = None
    ) -> List[ContractEvent]:
        """Return filtered events"""
        events = self.events
        
        if event_name:
            events = [e for e in events if e.name == event_name]
            
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
            
        return events
        
    def _validate_method(self, method: str) -> bool:
        """Validate if method exists"""
        return hasattr(self, f"method_{method}")
        
    def _validate_params(self, method: str, params: Dict) -> bool:
        """Validate method parameters"""
        # TODO: Implement parameter validation
        return True
        
    def _check_permissions(self, method: str, sender: str) -> bool:
        """Check permissions"""
        if method.startswith("admin_") and sender != self.client_address:
            return False
        return True
        
    def _execute_method(
        self,
        method: str,
        params: Dict[str, Any],
        sender: str
    ) -> Dict[str, Any]:
        """Execute contract method"""
        method_func = getattr(self, f"method_{method}")
        result = method_func(params, sender)
        
        # Emit event
        self._emit_event(
            method,
            {
                "params": params,
                "sender": sender,
                "result": result
            }
        )
        
        return result
        
    def _emit_event(self, name: str, data: Dict[str, Any]):
        """Emit contract event"""
        event = ContractEvent(
            name=name,
            data=data,
            timestamp=time.time(),
            contract_id=self.contract_id
        )
        self.events.append(event)
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize contract"""
        return {
            "contract_id": self.contract_id,
            "client_address": self.client_address,
            "driver_address": self.driver_address,
            "pool_address": self.pool_address,
            "value": self.value,
            "pickup_location": self.pickup_location,
            "delivery_location": self.delivery_location,
            "status": self.status.value,
            "creation_time": self.creation_time.isoformat(),
            "acceptance_time": self.acceptance_time.isoformat() if self.acceptance_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "requirements": {
                "min_driver_reputation": self.requirements.min_driver_reputation,
                "min_pool_reputation": self.requirements.min_pool_reputation,
                "min_establishment_reputation": self.requirements.min_establishment_reputation,
                "allow_adjustment": self.requirements.allow_reputation_adjustment,
                "adjustment_delay": self.requirements.reputation_adjustment_delay,
                "adjustment_steps": self.requirements.adjustment_steps
            },
            "events": [
                {
                    "name": e.name,
                    "data": e.data,
                    "timestamp": e.timestamp,
                    "contract_id": e.contract_id
                }
                for e in self.events
            ],
            "created_at": self.created_at
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any], reputation_manager: Optional[ReputationManager] = None) -> 'SmartContract':
        """Deserialize contract"""
        requirements = ContractRequirements(
            min_driver_reputation=data["requirements"]["min_driver_reputation"],
            min_pool_reputation=data["requirements"]["min_pool_reputation"],
            min_establishment_reputation=data["requirements"]["min_establishment_reputation"],
            allow_reputation_adjustment=data["requirements"]["allow_adjustment"],
            reputation_adjustment_delay=data["requirements"]["adjustment_delay"],
            reputation_adjustment_steps=data["requirements"]["adjustment_steps"]
        )
        
        contract = cls(
            contract_id=data["contract_id"],
            client_address=data["client_address"],
            value=data["value"],
            pickup_location=data["pickup_location"],
            delivery_location=data["delivery_location"],
            requirements=requirements,
            reputation_manager=reputation_manager
        )
        
        # Restore events
        contract.events = [
            ContractEvent(
                name=e["name"],
                data=e["data"],
                timestamp=e["timestamp"],
                contract_id=e["contract_id"]
            )
            for e in data["events"]
        ]
        
        contract.created_at = data["created_at"]
        contract.status = ContractStatus(data["status"])
        
        if data.get("acceptance_time"):
            contract.acceptance_time = datetime.fromisoformat(data["acceptance_time"])
        if data.get("completion_time"):
            contract.completion_time = datetime.fromisoformat(data["completion_time"])
        
        return contract
        
    @staticmethod
    def generate_id(client_address: str, timestamp: float) -> str:
        """Generate unique contract ID"""
        data = f"{client_address}{timestamp}".encode()
        return hashlib.sha256(data).hexdigest()
        
    def can_accept(self, driver_address: str, pool_address: str) -> bool:
        """
        Check if driver and pool meet reputation requirements
        """
        if not self.reputation_manager:
            return True
            
        # Get reputations
        driver_rep = self.reputation_manager.get_reputation(
            driver_address,
            ReputationType.DRIVER
        )
        pool_rep = self.reputation_manager.get_reputation(
            pool_address,
            ReputationType.POOL
        )
        
        # Check minimum requirements
        if not driver_rep or driver_rep.current_score < self.requirements.min_driver_reputation:
            return False
            
        if not pool_rep or pool_rep.current_score < self.requirements.min_pool_reputation:
            return False
            
        return True
        
    def accept_contract(self, driver_address: str, pool_address: str) -> bool:
        """
        Accept contract if reputation requirements are met
        """
        if self.status != ContractStatus.PENDING:
            return False
            
        if not self.can_accept(driver_address, pool_address):
            return False
            
        self.driver_address = driver_address
        self.pool_address = pool_address
        self.status = ContractStatus.ACCEPTED
        self.acceptance_time = datetime.now()
        
        logging.info(f"Contract {self.contract_id} accepted by driver {driver_address}")
        return True
        
    def check_reputation_adjustment(self) -> bool:
        """
        Check if contract should have reputation requirements adjusted
        """
        if not self.requirements.allow_reputation_adjustment:
            return False
            
        if self.status != ContractStatus.PENDING:
            return False
            
        if self.adjustment_count >= self.requirements.reputation_adjustment_steps:
            return False
            
        time_since_creation = datetime.now() - self.creation_time
        time_since_adjustment = datetime.now() - (self.last_adjustment_time or self.creation_time)
        
        adjustment_window = timedelta(minutes=self.requirements.reputation_adjustment_delay)
        
        if time_since_adjustment >= adjustment_window:
            return True
            
        return False
        
    def adjust_reputation_requirements(self) -> bool:
        """
        Lower reputation requirements if no acceptance after delay
        """
        if not self.check_reputation_adjustment():
            return False
            
        # Reduce requirements by 20% each adjustment
        reduction = 0.2
        
        self.requirements.min_driver_reputation *= (1 - reduction)
        self.requirements.min_pool_reputation *= (1 - reduction)
        self.requirements.min_establishment_reputation *= (1 - reduction)
        
        self.adjustment_count += 1
        self.last_adjustment_time = datetime.now()
        self.status = ContractStatus.REPUTATION_ADJUSTED
        
        logging.info(
            f"Contract {self.contract_id} requirements adjusted: "
            f"driver={self.requirements.min_driver_reputation:.2f}, "
            f"pool={self.requirements.min_pool_reputation:.2f}"
        )
        
        return True 