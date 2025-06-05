import time
import hashlib
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from enum import Enum

class PODStatus(Enum):
    VALID = "VALID"
    DUPLICATE = "DUPLICATE"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    EXPIRED = "EXPIRED"
    SUSPICIOUS = "SUSPICIOUS"

@dataclass
class PODAttempt:
    pod_id: str
    delivery_id: str
    timestamp: float
    status: PODStatus
    details: Dict
    signatures: List[bytes]

class PODDetector:
    def __init__(self):
        self.used_pods: Set[str] = set()  # pod_id
        self.pod_attempts: Dict[str, List[PODAttempt]] = {}  # delivery_id -> attempts
        self.suspicious_deliveries: Set[str] = set()
        self.max_pod_age = 86400 * 7  # 7 days
        self.max_attempts_per_delivery = 3
        
    def check_pod(
        self,
        pod_id: str,
        delivery_id: str,
        timestamp: float,
        location: Dict,
        signatures: List[bytes],
        metadata: Dict
    ) -> PODStatus:
        """Check POD for duplicates and validity"""
        try:
            # Check if POD was already used
            if pod_id in self.used_pods:
                self._record_attempt(
                    PODAttempt(
                        pod_id=pod_id,
                        delivery_id=delivery_id,
                        timestamp=timestamp,
                        status=PODStatus.DUPLICATE,
                        details={"reason": "POD already used"},
                        signatures=signatures
                    )
                )
                return PODStatus.DUPLICATE
                
            # Check POD age
            if time.time() - timestamp > self.max_pod_age:
                return PODStatus.EXPIRED
                
            # Check signatures
            if not self._verify_signatures(
                pod_id,
                delivery_id,
                timestamp,
                location,
                signatures
            ):
                return PODStatus.INVALID_SIGNATURE
                
            # Check for suspicious patterns
            if self._is_suspicious(
                delivery_id,
                timestamp,
                location,
                metadata
            ):
                self.suspicious_deliveries.add(delivery_id)
                return PODStatus.SUSPICIOUS
                
            # Record valid attempt
            self._record_attempt(
                PODAttempt(
                    pod_id=pod_id,
                    delivery_id=delivery_id,
                    timestamp=timestamp,
                    status=PODStatus.VALID,
                    details={
                        "location": location,
                        "metadata": metadata
                    },
                    signatures=signatures
                )
            )
            
            return PODStatus.VALID
            
        except Exception as e:
            print(f"Error checking POD: {e}")
            return PODStatus.INVALID_SIGNATURE
            
    def confirm_pod(
        self,
        pod_id: str,
        delivery_id: str
    ):
        """Mark POD as confirmed/used"""
        self.used_pods.add(pod_id)
        
    def get_delivery_attempts(
        self,
        delivery_id: str
    ) -> List[PODAttempt]:
        """Get all POD attempts for a delivery"""
        return self.pod_attempts.get(delivery_id, [])
        
    def _record_attempt(
        self,
        attempt: PODAttempt
    ):
        """Record a POD attempt"""
        if attempt.delivery_id not in self.pod_attempts:
            self.pod_attempts[attempt.delivery_id] = []
            
        self.pod_attempts[attempt.delivery_id].append(attempt)
        
        # Check for multiple attempts
        if len(self.pod_attempts[attempt.delivery_id]) > self.max_attempts_per_delivery:
            self.suspicious_deliveries.add(attempt.delivery_id)
            
    def _verify_signatures(
        self,
        pod_id: str,
        delivery_id: str,
        timestamp: float,
        location: Dict,
        signatures: List[bytes]
    ) -> bool:
        """Verify POD signatures"""
        try:
            # Must have both driver and client signatures
            if len(signatures) != 2:
                return False
                
            # Create message
            message = (
                f"{pod_id}:{delivery_id}:{timestamp}:"
                f"{location['lat']}:{location['lon']}"
            ).encode()
            
            # Verify each signature
            # Implementation depends on signature scheme
            return True  # Placeholder
            
        except Exception:
            return False
            
    def _is_suspicious(
        self,
        delivery_id: str,
        timestamp: float,
        location: Dict,
        metadata: Dict
    ) -> bool:
        """Check for suspicious patterns"""
        try:
            previous_attempts = self.get_delivery_attempts(delivery_id)
            
            if not previous_attempts:
                return False
                
            last_attempt = previous_attempts[-1]
            
            # Check time between attempts
            if timestamp - last_attempt.timestamp < 300:  # 5 minutes
                return True
                
            # Check location jump
            if self._calculate_distance(
                location,
                last_attempt.details.get("location", {})
            ) > 100:  # 100km
                return True
                
            # Check metadata consistency
            if not self._verify_metadata_consistency(
                metadata,
                last_attempt.details.get("metadata", {})
            ):
                return True
                
            return False
            
        except Exception:
            return True
            
    def _calculate_distance(
        self,
        loc1: Dict,
        loc2: Dict
    ) -> float:
        """Calculate distance between locations in km"""
        try:
            # Simple distance calculation
            # Should use proper geodesic distance in production
            lat_diff = loc1.get("lat", 0) - loc2.get("lat", 0)
            lon_diff = loc1.get("lon", 0) - loc2.get("lon", 0)
            return ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111  # rough km conversion
            
        except Exception:
            return 0
            
    def _verify_metadata_consistency(
        self,
        meta1: Dict,
        meta2: Dict
    ) -> bool:
        """Verify metadata consistency between attempts"""
        try:
            # Check essential fields match
            essential_fields = [
                "driver_id",
                "vehicle_id",
                "cargo_id"
            ]
            
            return all(
                meta1.get(field) == meta2.get(field)
                for field in essential_fields
                if field in meta1 and field in meta2
            )
            
        except Exception:
            return False
            
    def cleanup_old_attempts(self):
        """Cleanup expired POD attempts"""
        current_time = time.time()
        
        # Remove old attempts
        for delivery_id in list(self.pod_attempts.keys()):
            self.pod_attempts[delivery_id] = [
                attempt for attempt in self.pod_attempts[delivery_id]
                if current_time - attempt.timestamp <= self.max_pod_age
            ]
            
            if not self.pod_attempts[delivery_id]:
                del self.pod_attempts[delivery_id]
                
    def get_delivery_status(self, delivery_id: str) -> Dict:
        """Get delivery's POD status"""
        attempts = self.get_delivery_attempts(delivery_id)
        
        return {
            "total_attempts": len(attempts),
            "is_suspicious": delivery_id in self.suspicious_deliveries,
            "last_attempt": max(
                [a.timestamp for a in attempts]
                if attempts else [0]
            ),
            "valid_pods": len([
                a for a in attempts
                if a.status == PODStatus.VALID
            ]),
            "latest_status": attempts[-1].status.value if attempts else None
        } 