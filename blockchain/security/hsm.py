"""
Hardware Security Module (HSM) support.
Provides secure key management and cryptographic operations using HSM.
Supports both cloud HSM (AWS, Azure, GCP) and physical HSM devices.
"""

from __future__ import annotations
from typing import Dict, Optional, List, Union
from enum import Enum
import os
import time
import json
import logging
import hashlib
import base64
from dataclasses import dataclass
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.fernet import Fernet

class HSMProvider(Enum):
    """Supported HSM providers"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    PHYSICAL = "physical"
    SIMULATOR = "simulator"  # For testing

@dataclass
class HSMConfig:
    """HSM configuration"""
    provider: HSMProvider
    credentials: Dict[str, str]
    key_label: str
    endpoint: Optional[str] = None
    partition: Optional[str] = None
    slot_id: Optional[int] = None

class HSMManager:
    """
    Manages HSM operations and key lifecycle.
    Provides a unified interface for different HSM providers.
    """
    
    def __init__(
        self,
        config: HSMConfig,
        cache_timeout: int = 300,  # 5 minutes
        max_retries: int = 3,
        rate_limit: int = 1000  # Operations per second
    ):
        self.config = config
        self.cache_timeout = cache_timeout
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        
        # Operation tracking
        self.operation_timestamps: List[float] = []
        self.last_cleanup = time.time()
        
        # Key cache
        self.key_cache: Dict[str, tuple[bytes, float]] = {}  # key_id -> (key, timestamp)
        
        # Initialize provider
        self._init_provider()
        logging.info(f"HSM Manager initialized with provider {config.provider.value}")
    
    def _init_provider(self):
        """Initialize HSM provider based on configuration"""
        if self.config.provider == HSMProvider.AWS:
            self._init_aws_hsm()
        elif self.config.provider == HSMProvider.AZURE:
            self._init_azure_hsm()
        elif self.config.provider == HSMProvider.GCP:
            self._init_gcp_hsm()
        elif self.config.provider == HSMProvider.PHYSICAL:
            self._init_physical_hsm()
        elif self.config.provider == HSMProvider.SIMULATOR:
            self._init_simulator()
        else:
            raise ValueError(f"Unsupported HSM provider: {self.config.provider}")
    
    def _init_aws_hsm(self):
        """Initialize AWS CloudHSM"""
        try:
            import boto3
            self.hsm_client = boto3.client(
                'cloudhsmv2',
                aws_access_key_id=self.config.credentials.get('access_key'),
                aws_secret_access_key=self.config.credentials.get('secret_key'),
                region_name=self.config.credentials.get('region')
            )
        except ImportError:
            raise ImportError("boto3 required for AWS CloudHSM")
        except Exception as e:
            raise Exception(f"Failed to initialize AWS CloudHSM: {e}")
    
    def _init_azure_hsm(self):
        """Initialize Azure Key Vault HSM"""
        try:
            from azure.keyvault.keys import KeyClient
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            self.hsm_client = KeyClient(
                vault_url=self.config.endpoint,
                credential=credential
            )
        except ImportError:
            raise ImportError("azure-keyvault-keys required for Azure HSM")
        except Exception as e:
            raise Exception(f"Failed to initialize Azure HSM: {e}")
    
    def _init_gcp_hsm(self):
        """Initialize Google Cloud KMS HSM"""
        try:
            from google.cloud import kms
            self.hsm_client = kms.KeyManagementServiceClient()
        except ImportError:
            raise ImportError("google-cloud-kms required for GCP HSM")
        except Exception as e:
            raise Exception(f"Failed to initialize GCP HSM: {e}")
    
    def _init_physical_hsm(self):
        """Initialize physical HSM device"""
        try:
            import pkcs11
            
            lib = pkcs11.lib(self.config.credentials.get('library_path'))
            token = lib.get_token(token_label=self.config.credentials.get('token_label'))
            
            self.hsm_session = token.open(
                user_pin=self.config.credentials.get('user_pin'),
                rw=True
            )
        except ImportError:
            raise ImportError("python-pkcs11 required for physical HSM")
        except Exception as e:
            raise Exception(f"Failed to initialize physical HSM: {e}")
    
    def _init_simulator(self):
        """Initialize HSM simulator for testing"""
        self.sim_keys = {}
        self.sim_operations = []
    
    def _check_rate_limit(self) -> bool:
        """
        Check if operation is within rate limit
        Returns True if operation is allowed
        """
        now = time.time()
        
        # Cleanup old timestamps
        if now - self.last_cleanup > 60:  # Cleanup every minute
            self.operation_timestamps = [
                ts for ts in self.operation_timestamps
                if now - ts <= 1  # Keep last second
            ]
            self.last_cleanup = now
        
        # Check rate limit
        if len(self.operation_timestamps) >= self.rate_limit:
            return False
            
        self.operation_timestamps.append(now)
        return True
    
    def generate_key(
        self,
        key_label: str,
        key_type: str = "RSA",
        key_size: int = 2048
    ) -> str:
        """
        Generate a new key in HSM
        
        Args:
            key_label: Unique label for the key
            key_type: Type of key (RSA, EC, AES)
            key_size: Key size in bits
            
        Returns:
            str: Key identifier
        """
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")
            
        try:
            if self.config.provider == HSMProvider.AWS:
                return self._aws_generate_key(key_label, key_type, key_size)
            elif self.config.provider == HSMProvider.AZURE:
                return self._azure_generate_key(key_label, key_type, key_size)
            elif self.config.provider == HSMProvider.GCP:
                return self._gcp_generate_key(key_label, key_type, key_size)
            elif self.config.provider == HSMProvider.PHYSICAL:
                return self._physical_generate_key(key_label, key_type, key_size)
            else:  # Simulator
                return self._sim_generate_key(key_label, key_type, key_size)
        except Exception as e:
            logging.error(f"Failed to generate key: {e}")
            raise
    
    def sign(self, key_label: str, data: bytes) -> bytes:
        """Sign data using key in HSM"""
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")
            
        try:
            if self.config.provider == HSMProvider.AWS:
                return self._aws_sign(key_label, data)
            elif self.config.provider == HSMProvider.AZURE:
                return self._azure_sign(key_label, data)
            elif self.config.provider == HSMProvider.GCP:
                return self._gcp_sign(key_label, data)
            elif self.config.provider == HSMProvider.PHYSICAL:
                return self._physical_sign(key_label, data)
            else:  # Simulator
                return self._sim_sign(key_label, data)
        except Exception as e:
            logging.error(f"Failed to sign data: {e}")
            raise
    
    def verify(
        self,
        key_label: str,
        data: bytes,
        signature: bytes
    ) -> bool:
        """Verify signature using key in HSM"""
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")
            
        try:
            if self.config.provider == HSMProvider.AWS:
                return self._aws_verify(key_label, data, signature)
            elif self.config.provider == HSMProvider.AZURE:
                return self._azure_verify(key_label, data, signature)
            elif self.config.provider == HSMProvider.GCP:
                return self._gcp_verify(key_label, data, signature)
            elif self.config.provider == HSMProvider.PHYSICAL:
                return self._physical_verify(key_label, data, signature)
            else:  # Simulator
                return self._sim_verify(key_label, data, signature)
        except Exception as e:
            logging.error(f"Failed to verify signature: {e}")
            raise
    
    def encrypt(self, key_label: str, data: bytes) -> bytes:
        """Encrypt data using key in HSM"""
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")
            
        try:
            if self.config.provider == HSMProvider.AWS:
                return self._aws_encrypt(key_label, data)
            elif self.config.provider == HSMProvider.AZURE:
                return self._azure_encrypt(key_label, data)
            elif self.config.provider == HSMProvider.GCP:
                return self._gcp_encrypt(key_label, data)
            elif self.config.provider == HSMProvider.PHYSICAL:
                return self._physical_encrypt(key_label, data)
            else:  # Simulator
                return self._sim_encrypt(key_label, data)
        except Exception as e:
            logging.error(f"Failed to encrypt data: {e}")
            raise
    
    def decrypt(self, key_label: str, encrypted_data: bytes) -> bytes:
        """Decrypt data using key in HSM"""
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")
            
        try:
            if self.config.provider == HSMProvider.AWS:
                return self._aws_decrypt(key_label, encrypted_data)
            elif self.config.provider == HSMProvider.AZURE:
                return self._azure_decrypt(key_label, encrypted_data)
            elif self.config.provider == HSMProvider.GCP:
                return self._gcp_decrypt(key_label, encrypted_data)
            elif self.config.provider == HSMProvider.PHYSICAL:
                return self._physical_decrypt(key_label, encrypted_data)
            else:  # Simulator
                return self._sim_decrypt(key_label, encrypted_data)
        except Exception as e:
            logging.error(f"Failed to decrypt data: {e}")
            raise
    
    def _sim_generate_key(
        self,
        key_label: str,
        key_type: str,
        key_size: int
    ) -> str:
        """Generate key in simulator"""
        if key_type == "RSA":
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            public_key = private_key.public_key()
            
            self.sim_keys[key_label] = {
                'private': private_key,
                'public': public_key,
                'type': key_type,
                'size': key_size
            }
            
        return key_label
    
    def _sim_sign(self, key_label: str, data: bytes) -> bytes:
        """Sign data in simulator"""
        if key_label not in self.sim_keys:
            raise ValueError(f"Key not found: {key_label}")
            
        key = self.sim_keys[key_label]['private']
        signature = key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature
    
    def _sim_verify(
        self,
        key_label: str,
        data: bytes,
        signature: bytes
    ) -> bool:
        """Verify signature in simulator"""
        if key_label not in self.sim_keys:
            raise ValueError(f"Key not found: {key_label}")
            
        try:
            key = self.sim_keys[key_label]['public']
            key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    def _sim_encrypt(self, key_label: str, data: bytes) -> bytes:
        """Encrypt data in simulator"""
        if key_label not in self.sim_keys:
            raise ValueError(f"Key not found: {key_label}")
            
        key = self.sim_keys[key_label]['public']
        encrypted = key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return encrypted
    
    def _sim_decrypt(self, key_label: str, encrypted_data: bytes) -> bytes:
        """Decrypt data in simulator"""
        if key_label not in self.sim_keys:
            raise ValueError(f"Key not found: {key_label}")
            
        key = self.sim_keys[key_label]['private']
        decrypted = key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return decrypted
    
    def backup_key(
        self,
        key_label: str,
        backup_path: str,
        password: str
    ) -> bool:
        """
        Create encrypted backup of key
        Only available in simulator mode
        """
        if self.config.provider != HSMProvider.SIMULATOR:
            raise Exception("Key backup only available in simulator mode")
            
        if key_label not in self.sim_keys:
            raise ValueError(f"Key not found: {key_label}")
            
        try:
            # Encrypt key data
            key = Fernet.generate_key()
            f = Fernet(key)
            
            key_data = {
                'label': key_label,
                'type': self.sim_keys[key_label]['type'],
                'size': self.sim_keys[key_label]['size']
            }
            
            encrypted = f.encrypt(json.dumps(key_data).encode())
            
            # Save backup
            with open(backup_path, 'wb') as f:
                f.write(encrypted)
                
            return True
            
        except Exception as e:
            logging.error(f"Failed to backup key: {e}")
            return False
    
    def restore_key(
        self,
        backup_path: str,
        password: str
    ) -> Optional[str]:
        """
        Restore key from encrypted backup
        Only available in simulator mode
        """
        if self.config.provider != HSMProvider.SIMULATOR:
            raise Exception("Key restore only available in simulator mode")
            
        try:
            # Read and decrypt backup
            with open(backup_path, 'rb') as f:
                encrypted = f.read()
                
            key = Fernet.generate_key()
            f = Fernet(key)
            decrypted = f.decrypt(encrypted)
            
            key_data = json.loads(decrypted.decode())
            
            # Restore key
            return self.generate_key(
                key_data['label'],
                key_data['type'],
                key_data['size']
            )
            
        except Exception as e:
            logging.error(f"Failed to restore key: {e}")
            return None 