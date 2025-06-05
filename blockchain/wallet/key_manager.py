"""
Gerenciador de chaves e carteiras da blockchain
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging
from datetime import datetime
import time

from mnemonic import Mnemonic
from bip_utils import (
    Bip39SeedGenerator,
    Bip44,
    Bip44Coins,
    Bip44Changes
)
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class KeyManager:
    def __init__(self, db_path: str, wallet_dir: str):
        """
        Inicializa o gerenciador de chaves
        
        Args:
            db_path: Caminho para o banco de dados SQLite
            wallet_dir: Diretório onde as carteiras serão armazenadas
        """
        self.db_path = Path(db_path)
        self.wallet_dir = Path(wallet_dir)
        self.wallet_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializa gerador de mnemônicos
        self.mnemonic = Mnemonic("portuguese")
        
        # Cache de carteiras em memória
        self._wallets: Dict[str, dict] = {}
        
        # Chave para criptografia
        self._key = None
    
    def _get_db(self) -> sqlite3.Connection:
        """Retorna conexão com o banco de dados"""
        return sqlite3.connect(self.db_path)
    
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Deriva uma chave de criptografia a partir da senha
        
        Args:
            password: Senha do usuário
            salt: Salt opcional para derivação da chave
            
        Returns:
            Tupla com (chave, salt)
        """
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def init_encryption(self, password: str):
        """
        Inicializa a criptografia com uma senha
        
        Args:
            password: Senha para criptografia
        """
        key, salt = self._derive_key(password)
        self._key = Fernet(key)
        
        # Salva salt em arquivo seguro
        salt_path = self.wallet_dir / '.salt'
        with open(salt_path, 'wb') as f:
            f.write(salt)
    
    def load_encryption(self, password: str) -> bool:
        """
        Carrega chave de criptografia existente
        
        Args:
            password: Senha para descriptografia
            
        Returns:
            True se senha correta, False caso contrário
        """
        try:
            salt_path = self.wallet_dir / '.salt'
            if not salt_path.exists():
                return False
                
            with open(salt_path, 'rb') as f:
                salt = f.read()
            
            key, _ = self._derive_key(password, salt)
            self._key = Fernet(key)
            return True
            
        except Exception as e:
            logging.error(f"Erro ao carregar criptografia: {e}")
            return False
    
    def create_wallet(self, password: str = None) -> dict:
        """
        Cria uma nova carteira
        
        Args:
            password: Senha opcional para criptografia
            
        Returns:
            Dados da carteira criada
        """
        # Gera novo mnemônico
        mnemonic = self.mnemonic.generate(strength=256)
        
        # Gera seed e derivação BIP44
        seed = Bip39SeedGenerator(mnemonic).Generate()
        bip44_mst = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
        bip44_acc = bip44_mst.Purpose().Coin().Account(0)
        bip44_chain = bip44_acc.Change(Bip44Changes.CHAIN_EXT)
        bip44_addr = bip44_chain.AddressIndex(0)
        
        # Extrai chaves
        private_key = bip44_addr.PrivateKey().Raw().ToHex()
        public_key = bip44_addr.PublicKey().RawCompressed().ToHex()
        address = f"LOGI{public_key[-40:]}"  # Usa últimos 40 chars como endereço
        
        # Criptografa chave privada se senha fornecida
        if password and self._key:
            encrypted_key = self._key.encrypt(private_key.encode())
            private_key = base64.b64encode(encrypted_key).decode()
        
        # Cria carteira no banco
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO wallets (
                    address, public_key, encrypted_private_key,
                    balance, nonce, last_updated, status, created_at
                ) VALUES (?, ?, ?, 0.0, 0, ?, 'active', ?)
            """, (
                address, public_key, private_key,
                time.time(), time.time()
            ))
        
        wallet_data = {
            'address': address,
            'public_key': public_key,
            'private_key': private_key,
            'mnemonic': mnemonic
        }
        
        # Salva em arquivo local
        wallet_path = self.wallet_dir / f"{address}.json"
        with open(wallet_path, 'w') as f:
            json.dump(wallet_data, f, indent=4)
        
        self._wallets[address] = wallet_data
        return wallet_data
    
    def load_wallet(self, address: str, password: str = None) -> Optional[dict]:
        """
        Carrega uma carteira existente
        
        Args:
            address: Endereço da carteira
            password: Senha opcional para descriptografia
            
        Returns:
            Dados da carteira ou None se não encontrada
        """
        # Verifica cache
        if address in self._wallets:
            return self._wallets[address]
        
        # Tenta carregar do arquivo
        wallet_path = self.wallet_dir / f"{address}.json"
        if not wallet_path.exists():
            return None
            
        with open(wallet_path) as f:
            wallet_data = json.load(f)
        
        # Descriptografa chave privada se necessário
        if password and self._key and 'private_key' in wallet_data:
            try:
                encrypted = base64.b64decode(wallet_data['private_key'])
                private_key = self._key.decrypt(encrypted).decode()
                wallet_data['private_key'] = private_key
            except Exception as e:
                logging.error(f"Erro ao descriptografar chave: {e}")
                return None
        
        self._wallets[address] = wallet_data
        return wallet_data
    
    def list_wallets(self) -> List[dict]:
        """
        Lista todas as carteiras
        
        Returns:
            Lista com dados básicos das carteiras
        """
        with self._get_db() as conn:
            wallets = conn.execute("""
                SELECT address, public_key, balance, status, last_updated
                FROM wallets
                WHERE status = 'active'
                ORDER BY created_at DESC
            """).fetchall()
            
        return [{
            'address': w[0],
            'public_key': w[1],
            'balance': w[2],
            'status': w[3],
            'last_updated': datetime.fromtimestamp(w[4]).isoformat()
        } for w in wallets]
    
    def get_balance(self, address: str) -> float:
        """
        Retorna o saldo de uma carteira
        
        Args:
            address: Endereço da carteira
            
        Returns:
            Saldo atual
        """
        with self._get_db() as conn:
            result = conn.execute("""
                SELECT balance 
                FROM wallets 
                WHERE address = ?
            """, (address,)).fetchone()
            
        return result[0] if result else 0.0
    
    def update_balance(self, address: str, new_balance: float):
        """
        Atualiza o saldo de uma carteira
        
        Args:
            address: Endereço da carteira
            new_balance: Novo saldo
        """
        with self._get_db() as conn:
            conn.execute("""
                UPDATE wallets
                SET balance = ?,
                    last_updated = ?
                WHERE address = ?
            """, (new_balance, time.time(), address))
    
    def increment_nonce(self, address: str) -> int:
        """
        Incrementa e retorna o nonce de uma carteira
        
        Args:
            address: Endereço da carteira
            
        Returns:
            Novo valor do nonce
        """
        with self._get_db() as conn:
            conn.execute("""
                UPDATE wallets
                SET nonce = nonce + 1,
                    last_updated = ?
                WHERE address = ?
            """, (time.time(), address))
            
            result = conn.execute("""
                SELECT nonce
                FROM wallets
                WHERE address = ?
            """, (address,)).fetchone()
            
        return result[0] if result else 0
    
    def validate_signature(self, address: str, message: str, signature: str) -> bool:
        """
        Valida uma assinatura
        
        Args:
            address: Endereço da carteira
            message: Mensagem assinada
            signature: Assinatura a validar
            
        Returns:
            True se assinatura válida
        """
        # TODO: Implementar validação de assinatura
        return True  # Por enquanto retorna sempre válido
    
    def sign_message(self, address: str, message: str, password: str = None) -> Optional[str]:
        """
        Assina uma mensagem com a chave privada
        
        Args:
            address: Endereço da carteira
            message: Mensagem a assinar
            password: Senha para descriptografia
            
        Returns:
            Assinatura ou None se erro
        """
        wallet = self.load_wallet(address, password)
        if not wallet or 'private_key' not in wallet:
            return None
            
        # TODO: Implementar assinatura
        return "dummy_signature"  # Por enquanto retorna assinatura dummy 