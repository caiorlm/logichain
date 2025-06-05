import json
import os
import platform
import uuid
import hashlib
import ed25519
from pathlib import Path
from typing import Dict, Optional

class NodeIdentity:
    def __init__(self, identity_path: str = "data/identity"):
        self.path = Path(identity_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.identity_file = self.path / "identity.json"
        self.identity: Optional[Dict] = None
        
    def _generate_device_fingerprint(self) -> str:
        """Generate unique device fingerprint"""
        system = platform.system()
        machine = platform.machine()
        node = platform.node()
        processor = platform.processor()
        
        # Get additional hardware info
        try:
            # For Linux systems with /proc
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    cpu_info = f.read()
            else:
                cpu_info = processor
        except:
            cpu_info = processor
            
        # Combine all info
        fingerprint_raw = f"{system}:{machine}:{node}:{cpu_info}"
        return hashlib.sha256(fingerprint_raw.encode()).hexdigest()
        
    def generate_new_identity(self) -> Dict:
        """Generate new node identity with Ed25519 keypair"""
        # Generate signing key
        signing_key, verifying_key = ed25519.create_keypair()
        
        # Create identity object
        self.identity = {
            "node_id": str(uuid.uuid4()),
            "public_key": verifying_key.to_ascii(encoding="hex").decode(),
            "device_fingerprint": self._generate_device_fingerprint(),
            "created_at": str(int(time.time())),
            "version": "1.0"
        }
        
        # Save private key securely
        private_key_file = self.path / "private.key"
        private_key_file.write_bytes(signing_key.to_bytes())
        
        # Save identity file
        self.save_identity()
        
        return self.identity
        
    def load_identity(self) -> Optional[Dict]:
        """Load existing identity if available"""
        try:
            if self.identity_file.exists():
                self.identity = json.loads(self.identity_file.read_text())
                return self.identity
        except Exception as e:
            print(f"Error loading identity: {e}")
        return None
        
    def save_identity(self):
        """Save identity to file"""
        if self.identity:
            self.identity_file.write_text(
                json.dumps(self.identity, indent=2)
            )
            
    def sign_message(self, message: bytes) -> bytes:
        """Sign a message using node's private key"""
        private_key_file = self.path / "private.key"
        if not private_key_file.exists():
            raise Exception("Private key not found")
            
        signing_key = ed25519.SigningKey(private_key_file.read_bytes())
        return signing_key.sign(message)
        
    def verify_signature(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature from another node"""
        try:
            verifying_key = ed25519.VerifyingKey(public_key)
            verifying_key.verify(signature, message)
            return True
        except:
            return False 