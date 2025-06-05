from typing import Dict, List, Optional
import time
from dataclasses import dataclass
from enum import Enum
import hashlib
import ed25519
from collections import OrderedDict

class NetworkMode(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"

@dataclass
class Location:
    latitude: float
    longitude: float
    timestamp: float
    accuracy: float

@dataclass
class SignatureInfo:
    public_key: bytes
    signature: bytes
    timestamp: float

@dataclass
class DeliveryProof:
    unique_id: str
    contract_hash: str
    timestamp: float
    location_history: List[Location]
    timestamp_history: List[float]
    signature_chain: List[SignatureInfo]
    quorum_sigs: Optional[List[SignatureInfo]] = None

class ValidationResult:
    def __init__(self, valid: bool, reason: str = ""):
        self.valid = valid
        self.reason = reason

class SecurePoD:
    def __init__(self):
        self.proof_cache = OrderedDict()
        self.MAX_CACHE_SIZE = 10000
        self.MAX_TIME_WINDOW = 3600  # 1 hour
        self.MIN_QUORUM_SIZE = 3
        self.MAX_LOCATION_JUMP = 100  # Maximum allowed distance jump in km
        
    def _cleanup_cache(self):
        current_time = time.time()
        for proof_id in list(self.proof_cache.keys()):
            if current_time - self.proof_cache[proof_id] > self.MAX_TIME_WINDOW:
                del self.proof_cache[proof_id]
                
        # Enforce maximum cache size
        while len(self.proof_cache) > self.MAX_CACHE_SIZE:
            self.proof_cache.popitem(last=False)
            
    def _verify_signature_chain(self, proof: DeliveryProof) -> bool:
        try:
            prev_hash = proof.contract_hash.encode()
            
            for sig_info in proof.signature_chain:
                # Create verifying key
                verifying_key = ed25519.VerifyingKey(sig_info.public_key)
                
                # Prepare message
                message = prev_hash + str(sig_info.timestamp).encode()
                
                # Verify signature
                try:
                    verifying_key.verify(sig_info.signature, message)
                except ed25519.BadSignatureError:
                    return False
                    
                # Update previous hash for chain
                prev_hash = hashlib.sha3_256(sig_info.signature).digest()
                
            return True
            
        except Exception:
            return False
            
    def _validate_timestamp_window(self, timestamp: float) -> bool:
        current_time = time.time()
        return abs(current_time - timestamp) <= self.MAX_TIME_WINDOW
        
    def _calculate_distance(self, loc1: Location, loc2: Location) -> float:
        # Haversine formula implementation
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = radians(loc1.latitude), radians(loc1.longitude)
        lat2, lon2 = radians(loc2.latitude), radians(loc2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
        
    def _validate_location_sequence(
        self,
        locations: List[Location],
        timestamps: List[float]
    ) -> bool:
        if len(locations) != len(timestamps):
            return False
            
        for i in range(1, len(locations)):
            # Check timestamp sequence
            if timestamps[i] <= timestamps[i-1]:
                return False
                
            # Check reasonable location jumps
            distance = self._calculate_distance(locations[i], locations[i-1])
            time_diff = timestamps[i] - timestamps[i-1]
            
            # Calculate speed in km/h
            if time_diff > 0:
                speed = (distance / time_diff) * 3600
                if speed > self.MAX_LOCATION_JUMP:
                    return False
                    
        return True
        
    def _validate_quorum_signatures(
        self,
        quorum_sigs: List[SignatureInfo]
    ) -> bool:
        if len(quorum_sigs) < self.MIN_QUORUM_SIZE:
            return False
            
        # Verify each quorum signature
        unique_signers = set()
        for sig_info in quorum_sigs:
            try:
                verifying_key = ed25519.VerifyingKey(sig_info.public_key)
                message = str(sig_info.timestamp).encode()
                verifying_key.verify(sig_info.signature, message)
                unique_signers.add(sig_info.public_key)
            except:
                return False
                
        return len(unique_signers) >= self.MIN_QUORUM_SIZE
        
    def validate_proof_of_delivery(
        self,
        proof: DeliveryProof,
        mode: NetworkMode
    ) -> ValidationResult:
        try:
            # Clean up expired cache entries
            self._cleanup_cache()
            
            # 1. Check for replay attacks
            if proof.unique_id in self.proof_cache:
                return ValidationResult(
                    valid=False,
                    reason="Proof already processed"
                )
                
            # 2. Validate timestamp
            if not self._validate_timestamp_window(proof.timestamp):
                return ValidationResult(
                    valid=False,
                    reason="Proof timestamp outside acceptable window"
                )
                
            # 3. Validate signature chain
            if not self._verify_signature_chain(proof):
                return ValidationResult(
                    valid=False,
                    reason="Invalid signature chain"
                )
                
            # 4. Validate location sequence
            if not self._validate_location_sequence(
                proof.location_history,
                proof.timestamp_history
            ):
                return ValidationResult(
                    valid=False,
                    reason="Invalid location sequence"
                )
                
            # 5. Validate quorum signatures in online mode
            if mode == NetworkMode.ONLINE:
                if not proof.quorum_sigs:
                    return ValidationResult(
                        valid=False,
                        reason="Missing quorum signatures in online mode"
                    )
                    
                if not self._validate_quorum_signatures(proof.quorum_sigs):
                    return ValidationResult(
                        valid=False,
                        reason="Invalid quorum signatures"
                    )
                    
            # Add to cache if all validations pass
            self.proof_cache[proof.unique_id] = time.time()
            
            return ValidationResult(valid=True)
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                reason=f"Validation error: {str(e)}"
            ) 