from typing import Tuple, Optional
import os
import json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)
import base64

class KeyManager:
    """
    Manages cryptographic keys and signing operations.
    """
    
    def __init__(self, keys_dir: str = "~/.blockchain/keys"):
        self.keys_dir = os.path.expanduser(keys_dir)
        os.makedirs(self.keys_dir, exist_ok=True)
        
    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Generates a new RSA key pair.
        Returns (private_key_pem, public_key_pem)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        return private_pem, public_pem
        
    def save_keys(self, address: str, private_key: str, public_key: str) -> bool:
        """
        Saves key pair to files.
        """
        try:
            private_path = os.path.join(self.keys_dir, f"{address}.priv")
            public_path = os.path.join(self.keys_dir, f"{address}.pub")
            
            with open(private_path, "w") as f:
                f.write(private_key)
                
            with open(public_path, "w") as f:
                f.write(public_key)
                
            return True
            
        except Exception:
            return False
            
    def load_keys(self, address: str) -> Optional[Tuple[str, str]]:
        """
        Loads key pair from files.
        Returns (private_key_pem, public_key_pem) or None
        """
        try:
            private_path = os.path.join(self.keys_dir, f"{address}.priv")
            public_path = os.path.join(self.keys_dir, f"{address}.pub")
            
            with open(private_path) as f:
                private_key = f.read()
                
            with open(public_path) as f:
                public_key = f.read()
                
            return private_key, public_key
            
        except Exception:
            return None
            
    def sign_message(self, private_key_pem: str, message: str) -> str:
        """
        Signs a message using private key.
        Returns base64 encoded signature.
        """
        try:
            private_key = load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
            
            message_bytes = message.encode()
            signature = private_key.sign(
                message_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return base64.b64encode(signature).decode()
            
        except Exception:
            return ""
            
    def verify_signature(
        self,
        public_key_pem: str,
        message: str,
        signature: str
    ) -> bool:
        """
        Verifies a signature using public key.
        """
        try:
            public_key = load_pem_public_key(public_key_pem.encode())
            signature_bytes = base64.b64decode(signature)
            message_bytes = message.encode()
            
            public_key.verify(
                signature_bytes,
                message_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception:
            return False
            
    def sign_transaction(self, private_key_pem: str, transaction_dict: dict) -> str:
        """
        Signs a transaction dictionary.
        """
        message = json.dumps(transaction_dict, sort_keys=True)
        return self.sign_message(private_key_pem, message)
        
    def verify_transaction(
        self,
        public_key_pem: str,
        transaction_dict: dict,
        signature: str
    ) -> bool:
        """
        Verifies a transaction signature.
        """
        message = json.dumps(transaction_dict, sort_keys=True)
        return self.verify_signature(public_key_pem, message, signature) 