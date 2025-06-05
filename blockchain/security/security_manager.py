"""
Gerenciador de segurança da blockchain
"""

import os
import hashlib
import base64
import json
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet
from .crypto import (
    generate_keypair,
    sign_message,
    verify_signature,
    serialize_private_key,
    serialize_public_key,
    deserialize_private_key,
    deserialize_public_key
)

class SecurityManager:
    """Gerenciador central de segurança"""
    
    def __init__(self, node_id: str, key_dir: str = "keys"):
        self.node_id = node_id
        self.key_dir = key_dir
        self.private_key: Optional[ec.EllipticCurvePrivateKey] = None
        self.public_key: Optional[ec.EllipticCurvePublicKey] = None
        
        # Cria diretório de chaves se não existir
        if not os.path.exists(key_dir):
            os.makedirs(key_dir)
            
    def initialize(self, password: Optional[bytes] = None) -> None:
        """Inicializa par de chaves"""
        # Tenta carregar chaves existentes
        if self._load_keys(password):
            return
            
        # Gera novo par de chaves
        self.private_key, self.public_key = generate_keypair()
        
        # Salva chaves
        self._save_keys(password)
        
    def sign(self, message: bytes) -> bytes:
        """Assina mensagem"""
        if not self.private_key:
            raise ValueError("Private key not initialized")
            
        return sign_message(self.private_key, message)
        
    def verify(self, message: bytes, signature: bytes, public_key: Optional[ec.EllipticCurvePublicKey] = None) -> bool:
        """Verifica assinatura"""
        key = public_key or self.public_key
        if not key:
            raise ValueError("Public key not provided")
            
        return verify_signature(key, message, signature)
        
    def _load_keys(self, password: Optional[bytes] = None) -> bool:
        """Carrega chaves do disco"""
        private_key_path = os.path.join(self.key_dir, f"{self.node_id}_private.pem")
        public_key_path = os.path.join(self.key_dir, f"{self.node_id}_public.pem")
        
        try:
            # Carrega chave privada
            with open(private_key_path, "rb") as f:
                self.private_key = deserialize_private_key(f.read(), password)
                
            # Carrega chave pública
            with open(public_key_path, "rb") as f:
                self.public_key = deserialize_public_key(f.read())
                
            return True
            
        except Exception:
            return False
            
    def _save_keys(self, password: Optional[bytes] = None) -> None:
        """Salva chaves no disco"""
        if not self.private_key or not self.public_key:
            raise ValueError("Keys not initialized")
            
        # Salva chave privada
        private_key_path = os.path.join(self.key_dir, f"{self.node_id}_private.pem")
        with open(private_key_path, "wb") as f:
            f.write(serialize_private_key(self.private_key, password))
            
        # Salva chave pública
        public_key_path = os.path.join(self.key_dir, f"{self.node_id}_public.pem")
        with open(public_key_path, "wb") as f:
            f.write(serialize_public_key(self.public_key))
            
    def get_public_key(self) -> ec.EllipticCurvePublicKey:
        """Retorna chave pública"""
        if not self.public_key:
            raise ValueError("Public key not initialized")
        return self.public_key
        
    def generate_wallet(self) -> Dict:
        """Gera nova carteira"""
        # Gerar par de chaves
        private_key = self.crypto.generate_key_pair()
        public_key = private_key.public_key()
        
        # Gerar endereço
        address = self.crypto.generate_address(public_key)
        
        # Salvar chaves
        self.key_store.save_key_pair(address, private_key, public_key)
        
        return {
            'address': address,
            'public_key': self.crypto.public_key_to_string(public_key)
        }
        
    def sign_transaction(self, 
                        tx_data: Dict,
                        address: str) -> Optional[str]:
        """Assina uma transação"""
        try:
            # Carregar chave privada
            private_key = self.key_store.load_private_key(address)
            if not private_key:
                return None
                
            # Serializar dados
            message = json.dumps(tx_data, sort_keys=True).encode()
            
            # Assinar
            signature = self.crypto.sign_message(private_key, message)
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            logging.error(f"Error signing transaction: {e}")
            return None
            
    def verify_signature(self,
                        message: bytes,
                        signature: str,
                        public_key: str) -> bool:
        """Verifica assinatura"""
        try:
            # Decodificar chave e assinatura
            key_bytes = base64.b64decode(public_key)
            sig_bytes = base64.b64decode(signature)
            
            # Carregar chave pública
            public_key = serialization.load_pem_public_key(key_bytes)
            
            # Verificar
            return self.crypto.verify_signature(
                public_key,
                message,
                sig_bytes
            )
            
        except Exception as e:
            logging.error(f"Error verifying signature: {e}")
            return False
            
    def encrypt_data(self, data: bytes, public_key: str) -> Optional[bytes]:
        """Encripta dados para um destinatário"""
        try:
            key_bytes = base64.b64decode(public_key)
            pub_key = serialization.load_pem_public_key(key_bytes)
            return self.crypto.encrypt_data(data, pub_key)
        except Exception as e:
            logging.error(f"Error encrypting data: {e}")
            return None
            
    def decrypt_data(self, 
                    encrypted_data: bytes,
                    address: str) -> Optional[bytes]:
        """Decripta dados"""
        try:
            private_key = self.key_store.load_private_key(address)
            if not private_key:
                return None
                
            return self.crypto.decrypt_data(encrypted_data, private_key)
            
        except Exception as e:
            logging.error(f"Error decrypting data: {e}")
            return None
            
    def validate_transaction(self, tx: Dict) -> bool:
        """Valida uma transação"""
        try:
            # Verificar campos obrigatórios
            required = ['from', 'to', 'amount', 'signature']
            if not all(k in tx for k in required):
                return False
                
            # Verificar assinatura
            message = json.dumps({
                'from': tx['from'],
                'to': tx['to'],
                'amount': tx['amount'],
                'timestamp': tx.get('timestamp', 0)
            }, sort_keys=True).encode()
            
            return self.verify(
                message,
                base64.b64decode(tx['signature']),
                self.get_public_key()
            )
            
        except Exception as e:
            logging.error(f"Error validating transaction: {e}")
            return False
            
    def get_stats(self) -> Dict:
        """Retorna estatísticas de segurança"""
        return {
            'total_wallets': self.key_store.count_wallets(),
            'min_key_size': self.min_key_size,
            'key_store_path': self.key_dir,
            'last_backup': self.key_store.last_backup
        }

    def add_node_key(
        self,
        node_id: str,
        public_key: str,
        trust: bool = False
    ):
        """Add node public key"""
        self.node_keys[node_id] = public_key
        self.trusted_nodes[node_id] = trust
        
    def get_node_key(self, node_id: str) -> Optional[str]:
        """Get node public key"""
        return self.node_keys.get(node_id)
        
    def is_trusted(self, node_id: str) -> bool:
        """Check if node is trusted"""
        return self.trusted_nodes.get(node_id, False)
        
    def verify_node_signature(
        self,
        node_id: str,
        message: str,
        signature: str
    ) -> bool:
        """Verify node signature"""
        public_key = self.get_node_key(node_id)
        if not public_key:
            return False
            
        return verify_signature(message, signature, public_key)

    def generate_update_hash(self, last_update: float, current_time: float) -> str:
        """Gera hash de atualização para o banco de dados"""
        data = f"{self.node_id}:{last_update}:{current_time}"
        return hashlib.sha256(data.encode()).hexdigest()

class KeyStore:
    """Gerenciador de chaves"""
    
    def __init__(self, key_dir: str):
        self.key_dir = key_dir
        self.last_backup = 0
        
    def save_key_pair(self,
                      address: str,
                      private_key: rsa.RSAPrivateKey,
                      public_key: rsa.RSAPublicKey):
        """Salva par de chaves"""
        # Serializar chaves
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Salvar arquivos
        private_path = os.path.join(self.key_dir, f"{address}.key")
        public_path = os.path.join(self.key_dir, f"{address}.pub")
        
        with open(private_path, 'wb') as f:
            f.write(private_pem)
        os.chmod(private_path, 0o600)
        
        with open(public_path, 'wb') as f:
            f.write(public_pem)
        os.chmod(public_path, 0o644)
        
    def load_private_key(self, address: str) -> Optional[rsa.RSAPrivateKey]:
        """Carrega chave privada"""
        try:
            path = os.path.join(self.key_dir, f"{address}.key")
            with open(path, 'rb') as f:
                private_pem = f.read()
                
            return serialization.load_pem_private_key(
                private_pem,
                password=None
            )
        except Exception as e:
            logging.error(f"Error loading private key: {e}")
            return None
            
    def load_public_key(self, address: str) -> Optional[rsa.RSAPublicKey]:
        """Carrega chave pública"""
        try:
            path = os.path.join(self.key_dir, f"{address}.pub")
            with open(path, 'rb') as f:
                public_pem = f.read()
                
            return serialization.load_pem_public_key(public_pem)
            
        except Exception as e:
            logging.error(f"Error loading public key: {e}")
            return None
            
    def count_wallets(self) -> int:
        """Conta número de carteiras"""
        try:
            return len([f for f in os.listdir(self.key_dir)
                       if f.endswith('.key')])
        except:
            return 0

class CryptoManager:
    """Gerenciador de operações criptográficas"""
    
    def __init__(self, min_key_size: int = 2048):
        self.min_key_size = min_key_size
        
    def generate_key_pair(self) -> rsa.RSAPrivateKey:
        """Gera novo par de chaves RSA"""
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.min_key_size
        )
        
    def generate_address(self, public_key: rsa.RSAPublicKey) -> str:
        """Gera endereço a partir da chave pública"""
        key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        address_bytes = hashlib.sha256(key_bytes).digest()
        return f"LGC{base64.b32encode(address_bytes).decode()[:32]}"
        
    def sign_message(self,
                    private_key: rsa.RSAPrivateKey,
                    message: bytes) -> bytes:
        """Assina uma mensagem"""
        return private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
    def verify_signature(self,
                        public_key: rsa.RSAPublicKey,
                        message: bytes,
                        signature: bytes) -> bool:
        """Verifica uma assinatura"""
        try:
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False
            
    def encrypt_data(self,
                    data: bytes,
                    public_key: rsa.RSAPublicKey) -> bytes:
        """Encripta dados"""
        return public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
    def decrypt_data(self,
                    encrypted_data: bytes,
                    private_key: rsa.RSAPrivateKey) -> bytes:
        """Decripta dados"""
        return private_key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
    def public_key_to_string(self, public_key: rsa.RSAPublicKey) -> str:
        """Converte chave pública para string"""
        key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(key_bytes).decode()

class AccessControl:
    """Controle de acesso"""
    
    def __init__(self):
        self.roles = {
            'admin': ['all'],
            'miner': ['mine', 'validate'],
            'user': ['transfer', 'view']
        }
        self.permissions = {}
        
    def add_permission(self, address: str, role: str) -> bool:
        """Adiciona permissão"""
        if role not in self.roles:
            return False
            
        self.permissions[address] = role
        return True
        
    def check_permission(self, address: str, action: str) -> bool:
        """Verifica permissão"""
        role = self.permissions.get(address)
        if not role:
            return False
            
        allowed = self.roles.get(role, [])
        return 'all' in allowed or action in allowed 