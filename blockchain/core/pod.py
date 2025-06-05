import hashlib
import time
import math
import json
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature
from .key_manager import KeyManager
from dataclasses import dataclass
from decimal import Decimal
import logging

from .merkle import MerkleTree
from .utils.crypto import verify_signature
from .utils.validation import validate_gps_point
from .location.gps_manager import GPSPoint

@dataclass
class GeoPoint:
    """Ponto geográfico com timestamp"""
    latitude: Decimal
    longitude: Decimal
    timestamp: int
    accuracy: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "lat": str(self.latitude),
            "lng": str(self.longitude),
            "ts": self.timestamp,
            "acc": self.accuracy
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GeoPoint':
        return cls(
            latitude=Decimal(data["lat"]),
            longitude=Decimal(data["lng"]),
            timestamp=data["ts"],
            accuracy=data.get("acc")
        )

@dataclass
class RoutePoint:
    latitude: float
    longitude: float
    timestamp: float
    accuracy: float
    speed: Optional[float]
    heading: Optional[float]
    hash: str
    signature: str
    previous_hash: Optional[str]

class ProofOfDelivery:
    """
    Implements Proof of Delivery for supply chain tracking.
    """
    
    def __init__(self):
        self.e = math.e  # Transcendental number for mathematical security
        self.pi = math.pi  # Additional transcendental number for entropy
        self.offline_proofs = []  # Store proofs when offline
        self.key_manager = KeyManager()
        self.logger = logging.getLogger('pod')
        self.merkle_tree = MerkleTree()
        
    def generate_keys(self) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        """Generate RSA key pair for digital signatures"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        return private_key, public_key

    def create_location_proof(self, latitude: float, longitude: float, timestamp: float) -> str:
        """
        Create a proof of location using GPS coordinates and timestamp
        """
        location_data = f"{latitude},{longitude},{timestamp}"
        location_hash = hashlib.sha256(location_data.encode()).hexdigest()
        return location_hash

    def validate_route(self, 
                      coordinates: List[Tuple[float, float]], 
                      timestamps: List[float],
                      max_speed: float = 130.0,  # km/h
                      min_speed: float = 0.0) -> bool:
        """
        Validate delivery route based on coordinates and timestamps
        """
        if len(coordinates) != len(timestamps) or len(coordinates) < 2:
            return False

        for i in range(len(coordinates) - 1):
            # Calculate distance and time between consecutive points
            dist = self._haversine_distance(coordinates[i], coordinates[i + 1])
            time_diff = (timestamps[i + 1] - timestamps[i]) / 3600  # Convert to hours
            
            if time_diff <= 0:
                return False
            
            # Calculate speed in km/h
            speed = dist / time_diff
            
            # Validate speed constraints
            if speed > max_speed or speed < min_speed:
                return False
            
        return True

    def _haversine_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """
        Calculate distance between two GPS points using Haversine formula
        Returns distance in kilometers
        """
        lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
        lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Earth's radius in kilometers
        
        return c * r

    def create_delivery_proof(
        self,
        delivery_id: str,
        origin: str,
        destination: str,
        items: List[Dict[str, Any]],
        carrier_address: str,
        checkpoints: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates a new delivery proof.
        
        Args:
            delivery_id: Unique delivery identifier
            origin: Origin location
            destination: Destination location
            items: List of items being delivered
            carrier_address: Blockchain address of carrier
            checkpoints: Optional list of delivery checkpoints
        """
        proof = {
            "delivery_id": delivery_id,
            "origin": origin,
            "destination": destination,
            "items": items,
            "carrier": carrier_address,
            "timestamp": int(time.time()),
            "status": "created",
            "checkpoints": checkpoints or []
        }
        
        return proof
        
    def add_checkpoint(
        self,
        proof: Dict[str, Any],
        location: str,
        status: str,
        timestamp: int = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Adds a new checkpoint to the delivery proof.
        """
        checkpoint = {
            "location": location,
            "status": status,
            "timestamp": timestamp or int(time.time()),
            "metadata": metadata or {}
        }
        
        proof["checkpoints"].append(checkpoint)
        proof["status"] = status
        
        return proof
        
    def sign_proof(
        self,
        proof: Dict[str, Any],
        signer_address: str
    ) -> Dict[str, Any]:
        """
        Signs a delivery proof with the signer's private key.
        """
        # Load signer's keys
        keys = self.key_manager.load_keys(signer_address)
        if not keys:
            raise ValueError("Signer keys not found")
            
        # Create signature
        message = json.dumps(proof, sort_keys=True)
        signature = self.key_manager.sign_message(keys[0], message)
        
        if not signature:
            raise ValueError("Failed to sign proof")
            
        # Add signature to proof
        signed_proof = proof.copy()
        signed_proof["signature"] = {
            "signer": signer_address,
            "value": signature,
            "timestamp": int(time.time())
        }
        
        return signed_proof
        
    def verify_proof(
        self,
        proof: Dict[str, Any],
        required_signers: List[str] = None
    ) -> bool:
        """
        Verifies a signed delivery proof.
        
        Args:
            proof: The signed delivery proof
            required_signers: Optional list of addresses that must have signed
        """
        try:
            if "signature" not in proof:
                return False
                
            # Get signature data
            signature = proof["signature"]
            signer = signature["signer"]
            
            # Check required signers
            if required_signers and signer not in required_signers:
                return False
                
            # Load signer's public key
            keys = self.key_manager.load_keys(signer)
            if not keys:
                return False
                
            # Verify signature
            proof_copy = proof.copy()
            del proof_copy["signature"]
            
            message = json.dumps(proof_copy, sort_keys=True)
            return self.key_manager.verify_signature(
                keys[1],
                message,
                signature["value"]
            )
            
        except Exception:
            return False
            
    def complete_delivery(
        self,
        proof: Dict[str, Any],
        recipient_address: str,
        location: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Marks a delivery as complete and signs it.
        """
        # Add completion checkpoint
        proof = self.add_checkpoint(
            proof,
            location=location,
            status="delivered",
            metadata=metadata
        )
        
        # Sign by recipient
        proof = self.sign_proof(proof, recipient_address)
        
        return proof
        
    def get_delivery_status(self, proof: Dict[str, Any]) -> str:
        """Returns the current status of a delivery."""
        return proof.get("status", "unknown")
        
    def get_delivery_timeline(
        self,
        proof: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Returns the timeline of a delivery with all checkpoints.
        """
        timeline = []
        
        # Add creation
        timeline.append({
            "event": "created",
            "timestamp": proof["timestamp"],
            "location": proof["origin"]
        })
        
        # Add checkpoints
        for checkpoint in proof["checkpoints"]:
            timeline.append({
                "event": checkpoint["status"],
                "timestamp": checkpoint["timestamp"],
                "location": checkpoint["location"],
                "metadata": checkpoint.get("metadata", {})
            })
            
        return sorted(timeline, key=lambda x: x["timestamp"])

    def store_offline_proof(self, proof: Dict) -> bool:
        """
        Stores a proof for later verification when online.
        """
        try:
            # Basic validation before storing
            if not all(k in proof for k in ['delivery_data', 'signature', 'timestamp']):
                return False
                
            self.offline_proofs.append({
                'proof': proof,
                'stored_at': int(datetime.utcnow().timestamp())
            })
            return True
        except Exception:
            return False

    def sync_offline_proofs(self, blockchain) -> List[Dict]:
        """
        Synchronizes stored offline proofs with the blockchain.
        Returns list of successfully synced proofs.
        """
        synced_proofs = []
        failed_proofs = []
        
        for stored_proof in self.offline_proofs:
            try:
                # Verify the proof is still valid
                if self.verify_proof(stored_proof['proof']):
                    # Add to blockchain
                    if blockchain.handle_pod_verification(stored_proof):
                        synced_proofs.append(stored_proof)
                    else:
                        failed_proofs.append(stored_proof)
                else:
                    failed_proofs.append(stored_proof)
            except Exception:
                failed_proofs.append(stored_proof)
        
        # Keep only failed proofs for retry
        self.offline_proofs = failed_proofs
        
        return synced_proofs

    def create_offline_delivery_proof(self,
                                   delivery_id: str,
                                   coordinates: List[Tuple[float, float]],
                                   timestamps: List[float],
                                   private_key: rsa.RSAPrivateKey) -> Dict:
        """
        Creates a proof of delivery that can be verified offline.
        Includes additional security measures for offline operation.
        """
        proof = self.create_delivery_proof(delivery_id, coordinates, timestamps, private_key)
        
        # Add offline-specific security measures
        proof['offline_data'] = {
            'creation_time': int(datetime.utcnow().timestamp()),
            'entropy_chain': [self._generate_entropy() for _ in range(3)],
            'security_hash': self._create_offline_security_hash(proof)
        }
        
        return proof
        
    def _create_offline_security_hash(self, proof: Dict) -> str:
        """
        Creates an additional security hash for offline proofs.
        """
        security_data = {
            'proof_data': proof['delivery_data'],
            'timestamp': proof['timestamp'],
            'entropy': proof['entropy_factor']
        }
        return hashlib.sha3_256(json.dumps(security_data).encode()).hexdigest()

    def verify_offline_proof(self, proof: Dict) -> bool:
        """
        Verifies an offline proof with additional security checks.
        """
        try:
            # Verify basic proof first
            if not self.verify_proof(proof):
                return False
                
            # Verify offline-specific security measures
            if 'offline_data' not in proof:
                return False
                
            offline_data = proof['offline_data']
            
            # Check creation time is reasonable
            now = int(datetime.utcnow().timestamp())
            if offline_data['creation_time'] > now:
                return False
                
            # Verify security hash
            expected_hash = self._create_offline_security_hash(proof)
            if offline_data['security_hash'] != expected_hash:
                return False
                
            # Verify entropy chain
            if not all(0 <= e <= 1 for e in offline_data['entropy_chain']):
                return False
                
            return True
            
        except Exception:
            return False

    def _generate_entropy(self) -> float:
        """
        Generate entropy using transcendental numbers and chaos theory
        """
        current_time = time.time()
        x = (current_time * self.e) % self.pi
        # Using logistic map from chaos theory
        r = 3.99  # Chaos parameter
        for _ in range(10):
            x = r * x * (1 - x)
        return x 

    def create_pod(
        self,
        contract_id: str,
        driver_wallet: str,
        pickup_point: GeoPoint,
        delivery_point: GeoPoint,
        checkpoints: List[GeoPoint],
        signature: str
    ) -> Dict:
        """Cria prova de entrega"""
        
        # Valida pontos
        if not self._validate_points([pickup_point, delivery_point] + checkpoints):
            raise ValueError("Invalid geographic points")
        
        # Cria dados da prova
        pod_data = {
            "contract_id": contract_id,
            "driver": driver_wallet,
            "pickup": pickup_point.to_dict(),
            "delivery": delivery_point.to_dict(),
            "checkpoints": [p.to_dict() for p in checkpoints],
            "created_at": int(datetime.now().timestamp()),
            "signature": signature
        }
        
        # Adiciona prova de timestamp
        pod_with_proof = self.crypto.create_timestamp_proof(pod_data)
        
        # Gera hash final
        pod_hash = self.crypto.hash_data(pod_with_proof)
        pod_with_proof["hash"] = pod_hash
        
        return pod_with_proof
    
    def verify_pod(
        self,
        pod_data: Dict,
        max_age: Optional[int] = None
    ) -> bool:
        """Verifica prova de entrega"""
        try:
            # Verifica hash
            pod_hash = pod_data.pop("hash")
            calculated_hash = self.crypto.hash_data(pod_data)
            if calculated_hash != pod_hash:
                return False
            
            # Verifica timestamp
            if not self.crypto.verify_timestamp_proof(pod_data, max_age):
                return False
            
            # Verifica pontos
            points = [
                GeoPoint.from_dict(pod_data["data"]["pickup"]),
                GeoPoint.from_dict(pod_data["data"]["delivery"])
            ]
            points.extend([
                GeoPoint.from_dict(p)
                for p in pod_data["data"]["checkpoints"]
            ])
            
            if not self._validate_points(points):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_points(self, points: List[GeoPoint]) -> bool:
        """Valida sequência de pontos geográficos"""
        try:
            last_timestamp = 0
            
            for point in points:
                # Valida coordenadas
                if not (-90 <= float(point.latitude) <= 90):
                    return False
                if not (-180 <= float(point.longitude) <= 180):
                    return False
                
                # Valida sequência temporal
                if point.timestamp < last_timestamp:
                    return False
                last_timestamp = point.timestamp
                
                # Valida precisão se disponível
                if point.accuracy is not None and point.accuracy <= 0:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def calculate_route_stats(
        self,
        points: List[GeoPoint]
    ) -> Dict:
        """Calcula estatísticas da rota"""
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine(p1: GeoPoint, p2: GeoPoint) -> float:
            """Calcula distância entre pontos em km"""
            R = 6371  # Raio da Terra em km
            
            lat1, lon1 = radians(float(p1.latitude)), radians(float(p1.longitude))
            lat2, lon2 = radians(float(p2.latitude)), radians(float(p2.longitude))
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            
            return R * c
        
        total_distance = 0
        total_time = 0
        
        for i in range(len(points)-1):
            total_distance += haversine(points[i], points[i+1])
            total_time += points[i+1].timestamp - points[i].timestamp
        
        return {
            "total_distance_km": round(total_distance, 2),
            "total_time_sec": total_time,
            "avg_speed_kmh": round(
                (total_distance / total_time) * 3600, 2
            ) if total_time > 0 else 0
        } 

    def validate_route_proof(
        self,
        points: List[Dict],
        merkle_root: str,
        signature: str,
        public_key: bytes,
        expected_distance: Optional[float] = None,
        max_speed: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Validates a route proof
        Returns (is_valid, error_message)
        """
        try:
            # Verify signature
            if not verify_signature(
                merkle_root.encode(),
                signature,
                public_key
            ):
                return False, "Invalid route signature"
                
            # Verify points chain
            route_points = []
            previous_hash = None
            
            for point_data in points:
                # Validate point format
                if not validate_gps_point(point_data["point"]):
                    return False, f"Invalid point format: {point_data['point']}"
                    
                # Create RoutePoint
                point = RoutePoint(
                    latitude=point_data["point"]["latitude"],
                    longitude=point_data["point"]["longitude"],
                    timestamp=point_data["point"]["timestamp"],
                    accuracy=point_data["point"]["accuracy"],
                    speed=point_data["point"]["speed"],
                    heading=point_data["point"]["heading"],
                    hash=point_data["hash"],
                    signature=point_data["proof"]["signature"],
                    previous_hash=point_data["proof"].get("previous_hash")
                )
                
                # Verify hash chain
                if previous_hash is not None:
                    if point.previous_hash != previous_hash:
                        return False, "Invalid hash chain"
                        
                previous_hash = point.hash
                route_points.append(point)
                
            # Verify Merkle root
            tree = MerkleTree()
            for point_data in points:
                tree.add_leaf(str(point_data))
            if tree.get_merkle_root() != merkle_root:
                return False, "Invalid Merkle root"
                
            # Validate route metrics
            if not self._validate_route_metrics(
                route_points,
                expected_distance,
                max_speed
            ):
                return False, "Invalid route metrics"
                
            return True, "Route proof valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
            
    def _validate_route_metrics(
        self,
        points: List[RoutePoint],
        expected_distance: Optional[float],
        max_speed: Optional[float]
    ) -> bool:
        """Validates route metrics like distance and speed"""
        if len(points) < 2:
            return False
            
        total_distance = 0
        max_speed_found = 0
        
        for i in range(1, len(points)):
            prev = points[i-1]
            curr = points[i]
            
            # Calculate distance
            distance = self._haversine_distance(
                prev.latitude, prev.longitude,
                curr.latitude, curr.longitude
            )
            total_distance += distance
            
            # Calculate speed
            time_diff = curr.timestamp - prev.timestamp
            if time_diff > 0:
                speed = distance / (time_diff / 3600)  # km/h
                max_speed_found = max(max_speed_found, speed)
                
                # Validate speed if specified
                if max_speed and speed > max_speed:
                    return False
                    
        # Validate total distance if specified
        if expected_distance:
            distance_diff = abs(total_distance - expected_distance)
            if distance_diff > (expected_distance * 0.1):  # 10% tolerance
                return False
                
        return True
        
    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two points using Haversine formula
        Returns distance in kilometers
        """
        R = 6371  # Earth's radius in km
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c 