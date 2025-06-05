"""
Implementação simplificada de carteiras para o sistema LogiChain
"""

import json
import hashlib
import secrets
import time
from typing import Optional

class Wallet:
    def __init__(self, private_key: Optional[str] = None):
        """
        Inicializa uma carteira.
        Se private_key não for fornecida, gera uma nova.
        """
        if private_key:
            self.private_key = private_key
        else:
            # Gera uma chave privada aleatória de 32 bytes (64 caracteres hex)
            self.private_key = secrets.token_hex(32)
            
        # Gera a chave pública usando SHA-256 da chave privada
        self.public_key = hashlib.sha256(self.private_key.encode()).hexdigest()
        
        # Gera o endereço usando os primeiros 32 caracteres da chave pública
        # com o prefixo LOGI
        self.address = "LOGI" + self.public_key[:32]
        
        # Contador de transações
        self.nonce = 0
        
    def sign_transaction(self, to_address: str, amount: float) -> dict:
        """
        Cria e assina uma transação.
        """
        transaction = {
            "from": self.address,
            "to": to_address,
            "amount": amount,
            "nonce": self.nonce,
            "timestamp": int(time.time())
        }
        
        # Assina a transação usando a chave privada
        message = json.dumps(transaction, sort_keys=True)
        signature = hashlib.sha256(
            (message + self.private_key).encode()
        ).hexdigest()
        
        transaction["signature"] = signature
        self.nonce += 1
        
        return transaction
        
    def verify_transaction(self, transaction: dict) -> bool:
        """
        Verifica se uma transação foi assinada por esta carteira.
        """
        if transaction.get("from") != self.address:
            return False
            
        signature = transaction.pop("signature")
        message = json.dumps(transaction, sort_keys=True)
        expected_signature = hashlib.sha256(
            (message + self.private_key).encode()
        ).hexdigest()
        
        transaction["signature"] = signature
        return signature == expected_signature
        
    def save(self, path: str):
        """
        Salva a carteira em um arquivo JSON.
        """
        data = {
            "address": self.address,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "nonce": self.nonce
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
            
    @classmethod
    def load(cls, path: str) -> 'Wallet':
        """
        Carrega uma carteira de um arquivo JSON.
        """
        with open(path) as f:
            data = json.load(f)
            
        wallet = cls(private_key=data["private_key"])
        wallet.nonce = data.get("nonce", 0)
        return wallet
        
    @classmethod
    def from_mnemonic(cls, mnemonic: str) -> 'Wallet':
        """
        Cria uma carteira a partir de palavras mnemônicas.
        """
        # Usa as palavras mnemônicas como entrada para gerar a chave privada
        private_key = hashlib.sha256(mnemonic.encode()).hexdigest()
        return cls(private_key=private_key) 