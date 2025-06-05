"""
LogiChain Mesh Crypto
Handles cryptographic operations for mesh network
"""

import os
import json
import base64
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidKey, InvalidSignature

logger = logging.getLogger(__name__)

class MeshCrypto:
    """Mesh network cryptography"""
    
    def __init__(
        self,
        key_size: int = 2048,
        hash_algorithm: str = "sha256",
        signature_algorithm: str = "rsa-pss"
    ):
        self.key_size = key_size
        self.hash_algorithm = hash_algorithm
        self.signature_algorithm = signature_algorithm
        
        # Initialize hash function
        if hash_algorithm == "sha256":
            self.hash_func = hashes.SHA256()
        elif hash_algorithm == "sha384":
            self.hash_func = hashes.SHA384()
        elif hash_algorithm == "sha512":
            self.hash_func = hashes.SHA512()
        else:
            raise ValueError(f"Unsupported hash algorithm: {hash_algorithm}")
            
        # Initialize signature padding
        if signature_algorithm == "rsa-pss":
            self.signature_padding = padding.PSS(
                mgf=padding.MGF1(self.hash_func),
                salt_length=padding.PSS.MAX_LENGTH
            )
        else:
            raise ValueError(f"Unsupported signature algorithm: {signature_algorithm}")
            
    def generate_key_pair(self) -> Tuple[bytes, bytes]:
        """Generate RSA key pair"""
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.key_size
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize keys
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return private_bytes, public_bytes
            
        except Exception as e:
            logger.error(f"Failed to generate key pair: {str(e)}")
            raise
            
    def load_private_key(self, key_data: bytes) -> rsa.RSAPrivateKey:
        """Load RSA private key"""
        try:
            return serialization.load_pem_private_key(
                key_data,
                password=None
            )
        except Exception as e:
            logger.error(f"Failed to load private key: {str(e)}")
            raise
            
    def load_public_key(self, key_data: bytes) -> rsa.RSAPublicKey:
        """Load RSA public key"""
        try:
            return serialization.load_pem_public_key(key_data)
        except Exception as e:
            logger.error(f"Failed to load public key: {str(e)}")
            raise
            
    def sign_message(
        self,
        message: Dict[str, Any],
        private_key: bytes
    ) -> str:
        """Sign message with private key"""
        try:
            # Load key
            key = self.load_private_key(private_key)
            
            # Create message digest
            message_bytes = json.dumps(message, sort_keys=True).encode()
            
            # Sign message
            signature = key.sign(
                message_bytes,
                self.signature_padding,
                self.hash_func
            )
            
            # Encode signature
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            logger.error(f"Failed to sign message: {str(e)}")
            raise
            
    def verify_signature(
        self,
        message: Dict[str, Any],
        signature: str,
        public_key: bytes
    ) -> bool:
        """Verify message signature with public key"""
        try:
            # Load key
            key = self.load_public_key(public_key)
            
            # Create message digest
            message_bytes = json.dumps(message, sort_keys=True).encode()
            
            # Decode signature
            signature_bytes = base64.b64decode(signature)
            
            # Verify signature
            key.verify(
                signature_bytes,
                message_bytes,
                self.signature_padding,
                self.hash_func
            )
            
            return True
            
        except InvalidSignature:
            return False
        except Exception as e:
            logger.error(f"Failed to verify signature: {str(e)}")
            return False
            
    def hash_message(self, message: Dict[str, Any]) -> str:
        """Create message hash"""
        try:
            # Create message digest
            message_bytes = json.dumps(message, sort_keys=True).encode()
            
            # Calculate hash
            hasher = hashlib.new(self.hash_algorithm)
            hasher.update(message_bytes)
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"Failed to hash message: {str(e)}")
            raise
            
    def generate_symmetric_key(
        self,
        password: str,
        salt: Optional[bytes] = None
    ) -> Tuple[bytes, bytes]:
        """Generate symmetric encryption key"""
        try:
            # Generate salt if not provided
            if not salt:
                salt = os.urandom(16)
                
            # Create key derivation function
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000
            )
            
            # Generate key
            key = kdf.derive(password.encode())
            
            return key, salt
            
        except Exception as e:
            logger.error(f"Failed to generate symmetric key: {str(e)}")
            raise
            
    def encrypt_message(
        self,
        message: Dict[str, Any],
        key: bytes
    ) -> Tuple[bytes, bytes]:
        """Encrypt message with symmetric key"""
        try:
            # Generate IV
            iv = os.urandom(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv)
            )
            
            # Create encryptor
            encryptor = cipher.encryptor()
            
            # Pad message
            message_bytes = json.dumps(message).encode()
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(message_bytes) + padder.finalize()
            
            # Encrypt message
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            return ciphertext, iv
            
        except Exception as e:
            logger.error(f"Failed to encrypt message: {str(e)}")
            raise
            
    def decrypt_message(
        self,
        ciphertext: bytes,
        key: bytes,
        iv: bytes
    ) -> Dict[str, Any]:
        """Decrypt message with symmetric key"""
        try:
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv)
            )
            
            # Create decryptor
            decryptor = cipher.decryptor()
            
            # Decrypt message
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Unpad message
            unpadder = padding.PKCS7(128).unpadder()
            message_bytes = unpadder.update(padded_data) + unpadder.finalize()
            
            # Parse message
            return json.loads(message_bytes.decode())
            
        except Exception as e:
            logger.error(f"Failed to decrypt message: {str(e)}")
            raise
            
    def verify_key(
        self,
        key: bytes,
        salt: bytes,
        password: str
    ) -> bool:
        """Verify symmetric key"""
        try:
            # Create key derivation function
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000
            )
            
            # Verify key
            kdf.verify(password.encode(), key)
            return True
            
        except InvalidKey:
            return False
        except Exception as e:
            logger.error(f"Failed to verify key: {str(e)}")
            return False 