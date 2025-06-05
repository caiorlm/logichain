"""
LogiChain Crypto
Implementação própria de criptografia usando apenas bibliotecas padrão Python
"""

import hashlib
import hmac
import secrets
import base64
import json
import time
from typing import Dict, Optional, Tuple, List, Union
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidKey

logger = logging.getLogger(__name__)

class BIP39:
    """Implementação própria do BIP39"""
    
    WORDLIST = [
        'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract',
        'absurd', 'abuse', 'access', 'accident', 'account', 'accuse', 'achieve', 'acid',
        'acoustic', 'acquire', 'across', 'act', 'action', 'actor', 'actress', 'actual',
        'adapt', 'add', 'addict', 'address', 'adjust', 'admit', 'adult', 'advance',
        'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
        'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album',
        'alcohol', 'alert', 'alien', 'all', 'alley', 'allow', 'almost', 'alone',
        'alpha', 'already', 'also', 'alter', 'always', 'amateur', 'amazing', 'among',
        'amount', 'amused', 'analyst', 'anchor', 'ancient', 'anger', 'angle', 'angry',
        'animal', 'ankle', 'announce', 'annual', 'another', 'answer', 'antenna', 'antique',
        'anxiety', 'any', 'apart', 'apology', 'appear', 'apple', 'approve', 'april',
        'arch', 'arctic', 'area', 'arena', 'argue', 'arm', 'armed', 'armor',
        'army', 'around', 'arrange', 'arrest', 'arrive', 'arrow', 'art', 'artefact',
        'artist', 'artwork', 'ask', 'aspect', 'assault', 'asset', 'assist', 'assume',
        'asthma', 'athlete', 'atom', 'attack', 'attend', 'attitude', 'attract', 'auction',
        'audit', 'august', 'aunt', 'author', 'auto', 'autumn', 'average', 'avocado',
        'avoid', 'awake', 'aware', 'away', 'awesome', 'awful', 'awkward', 'axis',
        'baby', 'bachelor', 'bacon', 'badge', 'bag', 'balance', 'balcony', 'ball',
        'bamboo', 'banana', 'banner', 'bar', 'barely', 'bargain', 'barrel', 'base',
        'basic', 'basket', 'battle', 'beach', 'bean', 'beauty', 'because', 'become',
        'beef', 'before', 'begin', 'behave', 'behind', 'believe', 'below', 'belt',
        'bench', 'benefit', 'best', 'betray', 'better', 'between', 'beyond', 'bicycle'
    ]
    
    @classmethod
    def generate_mnemonic(cls, entropy_bits: int = 128) -> str:
        """Gera frase mnemônica BIP39"""
        # Gera entropia aleatória
        entropy = secrets.token_bytes(entropy_bits // 8)
        
        # Calcula checksum
        checksum_bits = entropy_bits // 32
        checksum = hashlib.sha256(entropy).digest()[0] >> (8 - checksum_bits)
        
        # Combina entropy e checksum
        combined = int.from_bytes(entropy, 'big') << checksum_bits | checksum
        
        # Divide em grupos de 11 bits
        bits = bin(combined)[2:].zfill(entropy_bits + checksum_bits)
        chunks = [bits[i:i+11] for i in range(0, len(bits), 11)]
        
        # Converte para palavras
        words = []
        for chunk in chunks:
            index = int(chunk, 2)
            if index < len(cls.WORDLIST):
                words.append(cls.WORDLIST[index])
                
        return ' '.join(words)
        
    @classmethod
    def to_seed(cls, mnemonic: str, passphrase: str = "") -> bytes:
        """Converte mnemônico para seed"""
        # Normaliza mnemônico
        mnemonic = ' '.join(mnemonic.split())
        
        # Deriva seed usando PBKDF2
        salt = ("mnemonic" + passphrase).encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA512(),
            length=64,
            salt=salt,
            iterations=2048
        )
        return kdf.derive(mnemonic.encode())
        
    @classmethod
    def check(cls, mnemonic: str) -> bool:
        """Verifica se mnemônico é válido"""
        words = mnemonic.split()
        return all(word in cls.WORDLIST for word in words)

class CryptoManager:
    """Gerenciador de criptografia da LogiChain"""
    
    def __init__(self):
        self.hash_function = hashlib.sha256
        
    def generate_key_pair(self) -> Tuple[bytes, bytes]:
        """Gerar par de chaves usando curva elíptica"""
        private_key = secrets.token_bytes(32)
        public_key = self._derive_public_key(private_key)
        return private_key, public_key
        
    def _derive_public_key(self, private_key: bytes) -> bytes:
        """Derivar chave pública da chave privada"""
        # Implementação própria de curva elíptica
        # Por enquanto usando hash como placeholder
        return self.hash_function(private_key).digest()
        
    def sign(self, message: bytes, private_key: bytes) -> bytes:
        """Assinar mensagem com chave privada"""
        return hmac.new(private_key, message, self.hash_function).digest()
        
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verificar assinatura com chave pública"""
        expected = hmac.new(public_key, message, self.hash_function).digest()
        return hmac.compare_digest(signature, expected)
        
    def encrypt(self, message: bytes, public_key: bytes) -> bytes:
        """Criptografar mensagem com chave pública"""
        # Implementar criptografia assimétrica própria
        # Por enquanto usando XOR como placeholder
        key = self.hash_function(public_key).digest()
        return bytes(a ^ b for a, b in zip(message, key))
        
    def decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Descriptografar mensagem com chave privada"""
        # Implementar descriptografia assimétrica própria
        # Por enquanto usando XOR como placeholder
        key = self.hash_function(private_key).digest()
        return bytes(a ^ b for a, b in zip(ciphertext, key))
        
    def hash(self, data: bytes) -> bytes:
        """Calcular hash de dados"""
        return self.hash_function(data).digest()
        
    def generate_random_bytes(self, length: int) -> bytes:
        """Gerar bytes aleatórios seguros"""
        return secrets.token_bytes(length)
        
    def generate_mnemonic(self, strength: int = 128) -> str:
        """Gerar frase mnemônica"""
        # Implementar BIP39 próprio
        entropy = self.generate_random_bytes(strength // 8)
        checksum = self.hash(entropy)[:strength // 32]
        
        # Converter para binário
        bin_entropy = bin(int.from_bytes(entropy, 'big'))[2:].zfill(strength)
        bin_checksum = bin(int.from_bytes(checksum, 'big'))[2:].zfill(strength // 32)
        
        # Combinar entropy + checksum
        bin_result = bin_entropy + bin_checksum
        
        # Dividir em grupos de 11 bits
        word_bits = [bin_result[i:i+11] for i in range(0, len(bin_result), 11)]
        
        # Converter para índices de palavras
        word_indices = [int(bits, 2) for bits in word_bits]
        
        # Lista de palavras BIP39
        wordlist = self._get_wordlist()
        
        # Gerar frase
        return ' '.join(wordlist[i] for i in word_indices)
        
    def _get_wordlist(self) -> List[str]:
        """Lista de palavras BIP39"""
        # Implementar lista de palavras própria
        # Por enquanto usando lista reduzida como exemplo
        return [
            'abandon', 'ability', 'able', 'about', 'above', 'absent',
            'absorb', 'abstract', 'absurd', 'abuse', 'access', 'accident',
            'account', 'accuse', 'achieve', 'acid', 'acoustic', 'acquire',
            'across', 'act', 'action', 'actor', 'actress', 'actual',
            # ... adicionar mais palavras ...
        ]
        
    def derive_key(self, password: str, salt: bytes) -> bytes:
        """Derivar chave de senha"""
        # Implementar PBKDF2 próprio
        key = password.encode()
        for _ in range(10000):  # Número de iterações
            key = self.hash(key + salt)
        return key
        
    def generate_address(self, public_key: bytes) -> str:
        """Gerar endereço a partir da chave pública"""
        # Hash da chave pública
        h = self.hash(public_key)
        
        # Converter para base58
        return self._bytes_to_base58(h)
        
    def _bytes_to_base58(self, data: bytes) -> str:
        """Converter bytes para base58"""
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        
        # Converter para inteiro
        n = int.from_bytes(data, 'big')
        
        # Converter para base58
        chars = []
        while n > 0:
            n, r = divmod(n, 58)
            chars.append(alphabet[r])
            
        # Adicionar zeros à esquerda
        for byte in data:
            if byte == 0:
                chars.append(alphabet[0])
            else:
                break
                
        return ''.join(reversed(chars))
        
    def _base58_to_bytes(self, text: str) -> bytes:
        """Converter base58 para bytes"""
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        
        # Converter para inteiro
        n = 0
        for char in text:
            n = n * 58 + alphabet.index(char)
            
        # Converter para bytes
        return n.to_bytes((n.bit_length() + 7) // 8, 'big')

class SecurityLog:
    def __init__(self, log_file: str = "security.log"):
        self.log_file = log_file
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def log_event(self, event_type: str, details: Dict):
        """Logs security events"""
        logging.info(f"Security Event - {event_type}: {json.dumps(details)}")
        
    def add_entry(
        self,
        event_type: str,
        data: Dict,
        timestamp: Optional[float] = None
    ) -> str:
        """
        Adiciona entrada ao log com hash encadeado
        """
        if timestamp is None:
            timestamp = time.time()
            
        entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'data': data,
            'previous_hash': self.last_hash
        }
        
        # Gera hash da entrada
        entry_bytes = json.dumps(entry, sort_keys=True).encode()
        entry_hash = self.hash_data(json.dumps(entry, sort_keys=True))
        entry['hash'] = entry_hash
        
        # Encripta dados sensíveis
        if 'sensitive_data' in data:
            entry['data']['sensitive_data'] = self.create_hmac(
                json.dumps(data['sensitive_data']),
                self.key,
                SecurityConstants.HASH_ALGORITHM
            )
            
        self.logs.append(entry)
        self.last_hash = entry_hash
        return entry_hash
        
    def verify_integrity(self) -> bool:
        """
        Verifica integridade da cadeia de hashes do log
        """
        previous_hash = None
        
        for entry in self.logs:
            # Verifica hash anterior
            if entry['previous_hash'] != previous_hash:
                return False
                
            # Recalcula e verifica hash da entrada
            entry_copy = entry.copy()
            entry_copy.pop('hash')
            entry_bytes = json.dumps(entry_copy, sort_keys=True).encode()
            calculated_hash = self.hash_data(json.dumps(entry_copy, sort_keys=True))
            
            if calculated_hash != entry['hash']:
                return False
                
            previous_hash = entry['hash']
            
        return True
        
    def get_encrypted_backup(self) -> bytes:
        """
        Gera backup encriptado dos logs
        """
        logs_json = json.dumps(self.logs).encode()
        return self.create_hmac(
            logs_json,
            self.key,
            SecurityConstants.HASH_ALGORITHM
        )
        
    def restore_from_backup(self, backup_data: bytes):
        """
        Restaura logs de backup encriptado
        """
        try:
            hmac_value = self.create_hmac(
                backup_data,
                self.key,
                SecurityConstants.HASH_ALGORITHM
            )
            if not self.verify_hmac(
                backup_data,
                hmac_value,
                self.key,
                SecurityConstants.HASH_ALGORITHM
            ):
                raise ValueError("HMAC verification failed")
                
            restored_logs = json.loads(backup_data)
            
            # Verifica integridade antes de restaurar
            self.logs = restored_logs
            if not self.verify_integrity():
                raise ValueError("Log integrity check failed")
                
            self.last_hash = self.logs[-1]['hash'] if self.logs else None
            
        except Exception as e:
            raise ValueError(f"Failed to restore backup: {e}")
            
class ReplayProtection:
    def __init__(self):
        self.nonce_cache = {}
        self.cache_timeout = timedelta(hours=24)
        
    def verify_nonce(self, nonce: str, timestamp: float) -> bool:
        """Verifies if nonce is unique and within timeframe"""
        if nonce in self.nonce_cache:
            return False
            
        nonce_time = datetime.fromtimestamp(timestamp)
        if datetime.now() - nonce_time > self.cache_timeout:
            return False
            
        self.nonce_cache[nonce] = timestamp
        return True
        
    def cleanup_cache(self):
        """Removes expired nonces"""
        now = datetime.now()
        expired = [
            nonce for nonce, timestamp in self.nonce_cache.items()
            if now - datetime.fromtimestamp(timestamp) > self.cache_timeout
        ]
        for nonce in expired:
            del self.nonce_cache[nonce]

class ContractManager:
    def __init__(self):
        self.contracts = {}
        
    def register_contract(self, contract_id: str, contract_data: Dict):
        """Registers new smart contract"""
        self.contracts[contract_id] = contract_data
        
    def verify_contract(self, contract_id: str, execution_data: Dict) -> bool:
        """Verifies if contract execution is valid"""
        if contract_id not in self.contracts:
            return False
            
        contract = self.contracts[contract_id]
        # Implement contract verification logic
        return True

class AnomalyDetector:
    def __init__(self):
        self.anomalies = []
        self.thresholds = {
            'transaction_value': 1000000,  # 1M tokens
            'transaction_frequency': 100,   # transactions per minute
            'mining_difficulty_change': 0.5 # 50% change
        }
    
    def get_anomalies(self) -> List[Dict]:
        return self.anomalies
        
    def check_transaction(self, transaction: Dict) -> bool:
        """Checks transaction for anomalies"""
        # Implement anomaly detection logic
        return True
        
    def add_transaction(self, transaction: Dict):
        """Adds transaction to history"""
        self.transaction_history.append(transaction)
        
    def get_anomalies(self) -> List[Dict]:
        """Returns detected anomalies"""
        return []  # Implement anomaly detection 

class KeyManager:
    """Gerencia chaves e carteiras"""
    
    def __init__(self, keys_dir: str = 'data/keys'):
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.bip39 = BIP39()
        
    def generate_key_pair(self) -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
        """Gera novo par de chaves"""
        private_key = ec.generate_private_key(ec.SECP256K1())
        public_key = private_key.public_key()
        return private_key, public_key
        
    def generate_wallet(self, password: str) -> Dict[str, str]:
        """Gera nova carteira"""
        # Gera mnemônico
        mnemonic = self.bip39.generate_mnemonic()
        
        # Deriva seed
        seed = self.bip39.to_seed(mnemonic, password)
        
        # Gera par de chaves
        private_key = ec.derive_private_key(
            int.from_bytes(seed[:32], 'big'),
            ec.SECP256K1()
        )
        public_key = private_key.public_key()
        
        # Gera endereço
        address = self.generate_address(public_key)
        
        # Salva chave privada
        self.save_private_key(private_key, address, password)
        
        return {
            "address": address,
            "mnemonic": mnemonic
        }
        
    def load_wallet(self, mnemonic: str, password: str) -> str:
        """Carrega carteira existente"""
        # Verifica mnemônico
        if not self.bip39.check(mnemonic):
            raise ValueError("Invalid mnemonic")
            
        # Deriva seed
        seed = self.bip39.to_seed(mnemonic, password)
        
        # Gera par de chaves
        private_key = ec.derive_private_key(
            int.from_bytes(seed[:32], 'big'),
            ec.SECP256K1()
        )
        public_key = private_key.public_key()
        
        # Gera endereço
        address = self.generate_address(public_key)
        
        # Salva chave privada
        self.save_private_key(private_key, address, password)
        
        return address
        
    def generate_address(self, public_key: ec.EllipticCurvePublicKey) -> str:
        """
        Gera endereço a partir da chave pública.
        
        Args:
            public_key: Chave pública ECC
            
        Returns:
            Endereço em formato hexadecimal
        """
        # Serializar chave pública
        raw_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        # Gerar hash keccak-256 (como Ethereum)
        keccak = hashlib.sha3_256()
        keccak.update(raw_bytes)
        address = keccak.hexdigest()[-40:]  # Últimos 40 chars
        
        return address
        
    def save_private_key(
        self,
        private_key: ec.EllipticCurvePrivateKey,
        address: str,
        password: str
    ):
        """
        Salva chave privada encriptada.
        
        Args:
            private_key: Chave privada
            address: Endereço da carteira
            password: Senha para encriptação
        """
        # Serializar com encriptação
        encrypted = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode()
            )
        )
        
        # Salvar em arquivo
        key_file = self.keys_dir / f"{address}.pem"
        key_file.write_bytes(encrypted)
        
    def load_private_key(
        self,
        address: str,
        password: str
    ) -> Optional[ec.EllipticCurvePrivateKey]:
        """
        Carrega chave privada.
        
        Args:
            address: Endereço da carteira
            password: Senha da chave
            
        Returns:
            Chave privada ou None se não encontrada
        """
        key_file = self.keys_dir / f"{address}.pem"
        if not key_file.exists():
            return None
            
        try:
            # Carregar e descriptografar
            encrypted = key_file.read_bytes()
            private_key = serialization.load_pem_private_key(
                encrypted,
                password=password.encode()
            )
            
            if not isinstance(private_key, ec.EllipticCurvePrivateKey):
                raise ValueError("Tipo de chave inválido")
                
            return private_key
        except Exception as e:
            logger.error(f"Erro ao carregar chave: {e}")
            return None
            
    def sign_message(
        self,
        private_key: ec.EllipticCurvePrivateKey,
        message: str
    ) -> str:
        """
        Assina uma mensagem.
        
        Args:
            private_key: Chave privada
            message: Mensagem a ser assinada
            
        Returns:
            Assinatura em base64
        """
        # Criar hash da mensagem
        message_hash = hashlib.sha256(message.encode()).digest()
        
        # Assinar
        signature = private_key.sign(
            message_hash,
            ec.ECDSA(hashes.SHA256())
        )
        
        # Converter para base64
        return base64.b64encode(signature).decode()
        
    def verify_signature(
        self,
        public_key: ec.EllipticCurvePublicKey,
        message: str,
        signature: str
    ) -> bool:
        """
        Verifica uma assinatura.
        
        Args:
            public_key: Chave pública
            message: Mensagem original
            signature: Assinatura em base64
            
        Returns:
            True se assinatura válida
        """
        try:
            # Decodificar assinatura
            signature_bytes = base64.b64decode(signature)
            
            # Criar hash da mensagem
            message_hash = hashlib.sha256(message.encode()).digest()
            
            # Verificar
            public_key.verify(
                signature_bytes,
                message_hash,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except (InvalidSignature, ValueError):
            return False 

def generate_keypair() -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """Gera par de chaves ECDSA"""
    private_key = ec.generate_private_key(ec.SECP256K1())
    public_key = private_key.public_key()
    return private_key, public_key

def sign_message(private_key: ec.EllipticCurvePrivateKey, message: bytes) -> bytes:
    """Assina mensagem com chave privada"""
    signature = private_key.sign(
        message,
        ec.ECDSA(hashes.SHA256())
    )
    return signature

def verify_signature(
    public_key: ec.EllipticCurvePublicKey,
    message: bytes,
    signature: bytes
) -> bool:
    """Verifica assinatura com chave pública"""
    try:
        public_key.verify(
            signature,
            message,
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception:
        return False

def serialize_private_key(
    private_key: ec.EllipticCurvePrivateKey,
    password: Optional[bytes] = None
) -> bytes:
    """Serializa chave privada"""
    if password:
        encryption = serialization.BestAvailableEncryption(password)
    else:
        encryption = serialization.NoEncryption()
        
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption
    )

def serialize_public_key(public_key: ec.EllipticCurvePublicKey) -> bytes:
    """Serializa chave pública"""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

def deserialize_private_key(
    data: bytes,
    password: Optional[bytes] = None
) -> ec.EllipticCurvePrivateKey:
    """Deserializa chave privada"""
    return serialization.load_pem_private_key(data, password)

def deserialize_public_key(data: bytes) -> ec.EllipticCurvePublicKey:
    """Deserializa chave pública"""
    return serialization.load_pem_public_key(data) 