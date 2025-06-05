"""
Smart contract implementation with route concatenation support
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json
import logging
from ..security.encryption import encrypt_data, decrypt_data
from ..utils.geo import calculate_distance, is_route_sequential

class ContractStatus(Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass
class RoutePoint:
    """Represents a point in the delivery route"""
    latitude: float
    longitude: float
    timestamp: Optional[float] = None
    checkpoint_type: str = "waypoint"  # pickup, delivery, waypoint
    sequence: int = 0
    required: bool = False
    max_deviation_km: float = 1.0

class Contract:
    """Smart contract with route concatenation support"""
    
    def __init__(
        self,
        contract_id: str,
        pickup_location: Dict[str, float],
        delivery_location: Dict[str, float],
        value: float,
        client_address: str,
        allow_concatenation: bool = True,
        max_concatenations: int = 3,
        route_flexibility: float = 1.0  # km of allowed deviation
    ):
        self.contract_id = contract_id
        self.status = ContractStatus.CREATED
        self.value = value
        self.client_address = client_address
        self.driver_address = None
        self.creation_date = datetime.now()
        self.completion_date = None
        self.delivery_signature = None
        self.rating = 0.0
        
        # Route configuration
        self.allow_concatenation = allow_concatenation
        self.max_concatenations = max_concatenations
        self.route_flexibility = route_flexibility
        
        # Route points
        self.route_points = [
            RoutePoint(
                latitude=pickup_location["lat"],
                longitude=pickup_location["lng"],
                checkpoint_type="pickup",
                sequence=0,
                required=True
            ),
            RoutePoint(
                latitude=delivery_location["lat"],
                longitude=delivery_location["lng"],
                checkpoint_type="delivery",
                sequence=1,
                required=True
            )
        ]
        
        # Concatenated contracts
        self.linked_contracts: List[str] = []
        self.previous_contract: Optional[str] = None
        self.next_contract: Optional[str] = None
        
        # Route metrics
        self.estimated_distance = calculate_distance(
            pickup_location["lat"],
            pickup_location["lng"],
            delivery_location["lat"],
            delivery_location["lng"]
        )
        
        # Audit trail
        self.route_history: List[Dict] = []
        
    def can_concatenate_with(self, other_contract: 'Contract') -> Tuple[bool, str]:
        """
        Check if this contract can be concatenated with another contract
        Returns (can_concatenate, reason)
        """
        if not self.allow_concatenation or not other_contract.allow_concatenation:
            return False, "Concatenation not allowed"
            
        if len(self.linked_contracts) >= self.max_concatenations:
            return False, "Maximum concatenations reached"
            
        if self.status != ContractStatus.ACCEPTED or other_contract.status != ContractStatus.ACCEPTED:
            return False, "Contracts must be in ACCEPTED state"
            
        # Check if routes are sequential
        this_end = self.route_points[-1]
        other_start = other_contract.route_points[0]
        
        if not is_route_sequential(
            this_end.latitude,
            this_end.longitude,
            other_start.latitude,
            other_start.longitude,
            max_distance_km=self.route_flexibility
        ):
            return False, "Routes are not sequential"
            
        return True, "Can be concatenated"
        
    def concatenate_with(self, other_contract: 'Contract') -> bool:
        """
        Concatenate this contract with another contract
        Returns success status
        """
        can_concat, reason = self.can_concatenate_with(other_contract)
        if not can_concat:
            logging.warning(f"Cannot concatenate contracts: {reason}")
            return False
            
        # Link contracts
        self.next_contract = other_contract.contract_id
        other_contract.previous_contract = self.contract_id
        
        self.linked_contracts.append(other_contract.contract_id)
        other_contract.linked_contracts.append(self.contract_id)
        
        # Merge route points
        next_sequence = len(self.route_points)
        for point in other_contract.route_points:
            point.sequence = next_sequence
            next_sequence += 1
            self.route_points.append(point)
            
        # Update metrics
        self.estimated_distance = sum(
            calculate_distance(
                self.route_points[i].latitude,
                self.route_points[i].longitude,
                self.route_points[i+1].latitude,
                self.route_points[i+1].longitude
            )
            for i in range(len(self.route_points)-1)
        )
        
        # Log concatenation
        self.route_history.append({
            "event": "concatenation",
            "timestamp": datetime.now().isoformat(),
            "linked_contract": other_contract.contract_id,
            "new_distance": self.estimated_distance
        })
        
        logging.info(f"Contracts concatenated: {self.contract_id} -> {other_contract.contract_id}")
        return True
        
    def get_optimized_route(self) -> List[RoutePoint]:
        """Get optimized route including all concatenated contracts"""
        return sorted(self.route_points, key=lambda x: x.sequence)
        
    def get_route_summary(self) -> Dict:
        """Get summary of the complete route"""
        return {
            "total_distance": self.estimated_distance,
            "num_checkpoints": len(self.route_points),
            "linked_contracts": self.linked_contracts,
            "route_points": [
                {
                    "lat": point.latitude,
                    "lng": point.longitude,
                    "type": point.checkpoint_type,
                    "sequence": point.sequence,
                    "required": point.required
                }
                for point in self.get_optimized_route()
            ]
        }

    def _generate_contract_hash(self, initiator: str, coordinates: Dict[str, int]) -> str:
        """Generate unique hash for contract."""
        data = f"{initiator}-{coordinates['lat']},{coordinates['lng']}-{datetime.now().timestamp()}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def accept_contract(self, acceptor: str, accept_tx: str):
        """Accept a pending contract."""
        if self.data["status"] != "PENDING":
            raise ValueError("Contract not in PENDING state")
            
        self.data["status"] = "ACTIVE"
        self.data["parties"]["acceptor"] = acceptor
        self.data["accept_tx"] = accept_tx
        self.data["timestamps"]["accepted"] = datetime.now().timestamp()
    
    def add_pod_checkpoint(self, checkpoint_data: Dict):
        """Add a proof of delivery checkpoint."""
        if self.data["status"] != "ACTIVE":
            raise ValueError("Contract not in ACTIVE state")
            
        self.data["delivery"]["pod_checkpoints"].append({
            "tx_hash": checkpoint_data["tx_hash"],
            "timestamp": datetime.now().timestamp(),
            "status": "VERIFIED",
            "data": checkpoint_data
        })
    
    def complete_delivery(self, final_pod: Dict, mining_data: Dict):
        """Complete the delivery with final POD and mining confirmation."""
        if self.data["status"] != "ACTIVE":
            raise ValueError("Contract not in ACTIVE state")
            
        self.data["status"] = "COMPLETED"
        self.data["delivery"]["final_pod"] = {
            "tx_hash": final_pod["tx_hash"],
            "timestamp": datetime.now().timestamp(),
            "status": "VERIFIED",
            "data": final_pod
        }
        self.data["delivery"]["mining_confirmation"] = mining_data
        self.data["timestamps"]["completed"] = datetime.now().timestamp()
    
    def to_dict(self) -> Dict:
        """Convert contract to dictionary."""
        return self.data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Contract':
        """Create contract instance from dictionary."""
        contract = cls(
            contract_id=data["contract_id"],
            pickup_location=data["pickup_location"],
            delivery_location=data["delivery_location"],
            value=data["value"],
            client_address=data["client_address"],
            allow_concatenation=data["allow_concatenation"],
            max_concatenations=data["max_concatenations"],
            route_flexibility=data["route_flexibility"]
        )
        contract.data = data
        return contract 