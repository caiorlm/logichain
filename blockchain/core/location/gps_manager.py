import threading
import time
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import hashlib
import hmac
import base64

@dataclass
class GPSPoint:
    latitude: float
    longitude: float
    timestamp: float
    accuracy: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp,
            "accuracy": self.accuracy,
            "speed": self.speed,
            "heading": self.heading
        }

class LocationProof:
    def __init__(self, private_key: bytes):
        self.private_key = private_key
        
    def create_proof(self, point: GPSPoint, previous_hash: str = None) -> Dict:
        """Creates cryptographic proof of location"""
        data = point.to_dict()
        if previous_hash:
            data["previous_hash"] = previous_hash
            
        # Create HMAC signature
        message = json.dumps(data, sort_keys=True).encode()
        signature = hmac.new(self.private_key, message, hashlib.sha256).hexdigest()
        
        return {
            "point": data,
            "signature": signature,
            "timestamp": time.time()
        }
        
    def verify_proof(self, proof: Dict, public_key: bytes) -> bool:
        """Verifies a location proof"""
        message = json.dumps(proof["point"], sort_keys=True).encode()
        expected_sig = hmac.new(public_key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(proof["signature"], expected_sig)

class GPSManager:
    def __init__(self, node_id: str, db_path: str = "gps_cache.db"):
        self.node_id = node_id
        self.db_path = db_path
        self.current_location: Optional[GPSPoint] = None
        self.location_history: List[Dict] = []
        self.proof_chain: List[str] = []
        self._setup_database()
        self._running = False
        self._lock = threading.Lock()
        
    def _setup_database(self):
        """Sets up SQLite database for local caching"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gps_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    accuracy REAL NOT NULL,
                    speed REAL,
                    heading REAL,
                    proof TEXT NOT NULL,
                    synced INTEGER DEFAULT 0
                )
            """)
            
    def start_collection(self, interval_ms: int = 5000):
        """Starts GPS collection in background"""
        if self._running:
            return
            
        self._running = True
        
        def collection_loop():
            while self._running:
                try:
                    point = self._collect_gps_data()
                    if point:
                        self._process_point(point)
                except Exception as e:
                    self._handle_error(e)
                time.sleep(interval_ms / 1000)
                
        self.collection_thread = threading.Thread(
            target=collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        
    def stop_collection(self):
        """Stops GPS collection"""
        self._running = False
        if hasattr(self, 'collection_thread'):
            self.collection_thread.join(timeout=5.0)
            
    def _collect_gps_data(self) -> Optional[GPSPoint]:
        """
        Collects GPS data from available source
        Override this method based on platform (mobile/desktop)
        """
        raise NotImplementedError(
            "GPS collection must be implemented by platform specific class"
        )
        
    def _process_point(self, point: GPSPoint):
        """Processes and stores a new GPS point"""
        with self._lock:
            # Create proof
            proof = LocationProof(self._get_private_key()).create_proof(
                point,
                self.proof_chain[-1] if self.proof_chain else None
            )
            
            # Store locally
            self._store_point(point, proof)
            
            # Update current location
            self.current_location = point
            
            # Add to proof chain
            self.proof_chain.append(proof["signature"])
            
            # Try to sync
            self._try_sync()
            
    def _store_point(self, point: GPSPoint, proof: Dict):
        """Stores point in local database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO gps_points (
                    latitude, longitude, timestamp, accuracy,
                    speed, heading, proof, synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    point.latitude, point.longitude,
                    point.timestamp, point.accuracy,
                    point.speed, point.heading,
                    json.dumps(proof)
                )
            )
            
    def _try_sync(self):
        """Attempts to sync stored points with network"""
        with sqlite3.connect(self.db_path) as conn:
            unsynced = conn.execute(
                "SELECT * FROM gps_points WHERE synced = 0"
            ).fetchall()
            
            if unsynced:
                # TODO: Implement network sync
                pass
                
    def _handle_error(self, error: Exception):
        """Handles collection errors"""
        # TODO: Implement proper error handling and logging
        print(f"GPS Collection Error: {str(error)}")
        
    def _get_private_key(self) -> bytes:
        """Gets node's private key for signing"""
        # TODO: Implement proper key management
        return hashlib.sha256(self.node_id.encode()).digest()
        
    def get_route_proof(self, start_time: float, end_time: float) -> List[Dict]:
        """Gets proof of route for time period"""
        with sqlite3.connect(self.db_path) as conn:
            points = conn.execute(
                """
                SELECT proof FROM gps_points 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
                """,
                (start_time, end_time)
            ).fetchall()
            
        return [json.loads(p[0]) for p in points] 