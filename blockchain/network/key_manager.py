from __future__ import annotations
import os
import json
import base64
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import stat
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class KeyManager:
    """
    Manages cryptographic keys securely.
    """
    
    KEY_ROTATION_DAYS = 30  # Rotate keys every 30 days
    KEY_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR  # Read/write for owner only (0600)
    
    def __init__(self, base_path: str = None):
        """
        Initializes the key manager.
        
        Args:
            base_path: Base path for storage (optional)
        """
        self.base_path = base_path or os.path.expanduser("~/.blockchain")
        self.keys_path = os.path.join(self.base_path, "keys")
        
        # Create directories with secure permissions
        os.makedirs(self.keys_path, mode=0o700, exist_ok=True)
        
        # Initialize Fernet for symmetric encryption
        self.fernet_key = self._load_or_create_fernet_key()
        self.fernet = Fernet(self.fernet_key)
        
        # Check key rotation
        self._check_key_rotation()
        
        logging.info("Key manager initialized")

    def _check_key_rotation(self):
        """
        Checks if keys need rotation based on age
        """
        key_path = os.path.join(self.keys_path, "fernet.key")
        if os.path.exists(key_path):
            key_age = datetime.fromtimestamp(os.path.getctime(key_path))
            if datetime.now() - key_age > timedelta(days=self.KEY_ROTATION_DAYS):
                logging.info("Rotating encryption keys")
                self._rotate_keys()

    def _rotate_keys(self):
        """
        Rotates all encryption keys and re-encrypts stored data
        """
        try:
            # Generate new Fernet key
            new_key = Fernet.generate_key()
            new_fernet = Fernet(new_key)
            
            # Re-encrypt all private keys with new key
            for file in os.listdir(self.keys_path):
                if file.endswith('.priv'):
                    file_path = os.path.join(self.keys_path, file)
                    with open(file_path, 'rb') as f:
                        encrypted_data = f.read()
                    decrypted_data = self.fernet.decrypt(encrypted_data)
                    new_encrypted = new_fernet.encrypt(decrypted_data)
                    self._write_file(file_path, new_encrypted)
            
            # Save new Fernet key
            self._write_file(
                os.path.join(self.keys_path, "fernet.key"),
                new_key
            )
            
            # Update current Fernet instance
            self.fernet_key = new_key
            self.fernet = new_fernet
            
            logging.info("Key rotation completed successfully")
            
        except Exception as e:
            logging.error(f"Error during key rotation: {e}")
            raise

    def generate_key_pair(self, node_id: str) -> Tuple[bytes, bytes]:
        """
        Gera um novo par de chaves RSA.
        
        Args:
            node_id: Identificador do nó
            
        Returns:
            Tuple[bytes, bytes]: (chave privada, chave pública)
        """
        try:
            # Gerar par de chaves RSA
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            public_key = private_key.public_key()
            
            # Serializar chaves
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Salvar chaves
            self._save_key_pair(node_id, private_bytes, public_bytes)
            
            return private_bytes, public_bytes
            
        except Exception as e:
            logging.error(f"Error generating key pair: {e}")
            raise

    def get_key_pair(self, node_id: str) -> Optional[Tuple[bytes, bytes]]:
        """
        Obtém um par de chaves existente.
        
        Args:
            node_id: Identificador do nó
            
        Returns:
            Tuple[bytes, bytes] ou None: (chave privada, chave pública)
        """
        try:
            private_path = os.path.join(self.keys_path, f"{node_id}.priv")
            public_path = os.path.join(self.keys_path, f"{node_id}.pub")
            
            if not (os.path.exists(private_path) and os.path.exists(public_path)):
                return None
                
            # Carregar e descriptografar chave privada
            with open(private_path, 'rb') as f:
                encrypted_private = f.read()
            private_key = self.fernet.decrypt(encrypted_private)
            
            # Carregar chave pública
            with open(public_path, 'rb') as f:
                public_key = f.read()
                
            return private_key, public_key
            
        except Exception as e:
            logging.error(f"Error getting key pair: {e}")
            return None

    def import_public_key(self, node_id: str, public_key: bytes) -> bool:
        """
        Importa uma chave pública.
        
        Args:
            node_id: Identificador do nó
            public_key: Chave pública em bytes
            
        Returns:
            bool: True se importado com sucesso
        """
        try:
            # Validar chave pública
            serialization.load_pem_public_key(public_key)
            
            # Salvar chave
            public_path = os.path.join(self.keys_path, f"{node_id}.pub")
            self._write_file(public_path, public_key)
            
            return True
            
        except Exception as e:
            logging.error(f"Error importing public key: {e}")
            return False

    def delete_keys(self, node_id: str) -> bool:
        """
        Remove par de chaves.
        
        Args:
            node_id: Identificador do nó
            
        Returns:
            bool: True se removido com sucesso
        """
        try:
            private_path = os.path.join(self.keys_path, f"{node_id}.priv")
            public_path = os.path.join(self.keys_path, f"{node_id}.pub")
            
            if os.path.exists(private_path):
                os.remove(private_path)
                
            if os.path.exists(public_path):
                os.remove(public_path)
                
            return True
            
        except Exception as e:
            logging.error(f"Error deleting keys: {e}")
            return False

    def _save_key_pair(self, node_id: str, private_key: bytes, public_key: bytes):
        """
        Salva um par de chaves de forma segura.
        
        Args:
            node_id: Identificador do nó
            private_key: Chave privada em bytes
            public_key: Chave pública em bytes
        """
        try:
            # Criptografar chave privada
            encrypted_private = self.fernet.encrypt(private_key)
            
            # Salvar chaves
            private_path = os.path.join(self.keys_path, f"{node_id}.priv")
            public_path = os.path.join(self.keys_path, f"{node_id}.pub")
            
            self._write_file(private_path, encrypted_private)
            self._write_file(public_path, public_key)
            
        except Exception as e:
            logging.error(f"Error saving key pair: {e}")
            raise

    def _load_or_create_fernet_key(self) -> bytes:
        """
        Loads or creates a new Fernet key with secure storage.
        
        Returns:
            bytes: Fernet key
        """
        key_path = os.path.join(self.keys_path, "fernet.key")
        
        if os.path.exists(key_path):
            # Verify file permissions
            stat_info = os.stat(key_path)
            if stat_info.st_mode & 0o777 != 0o600:
                logging.warning("Fixing insecure key file permissions")
                os.chmod(key_path, self.KEY_PERMISSIONS)
            
            with open(key_path, 'rb') as f:
                return f.read()
                
        # Generate new key
        key = Fernet.generate_key()
        self._write_file(key_path, key)
        return key

    def _write_file(self, path: str, data: bytes):
        """
        Writes data to file securely with proper permissions.
        
        Args:
            path: File path
            data: Data in bytes
        """
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        
        # Write file with secure permissions
        with open(path, 'wb') as f:
            f.write(data)
        os.chmod(path, self.KEY_PERMISSIONS)

    def list_peers(self) -> list[str]:
        """
        Lista todos os peers com chaves registradas.
        """
        peers = set()
        for file in os.listdir(self.keys_path):
            if file.endswith('.pub'):
                peers.add(file.replace('.pub', ''))
        return list(peers)

    def export_public_key(self, peer_id: str, output_path: str) -> bool:
        """
        Exporta a chave pública de um peer para um arquivo.
        """
        try:
            keys = self.get_key_pair(peer_id)
            if not keys:
                return False
                
            _, public_pem = keys
            self._write_file(output_path, public_pem)
            return True
            
        except Exception as e:
            logging.error(f"Error exporting public key for {peer_id}: {e}")
            return False 