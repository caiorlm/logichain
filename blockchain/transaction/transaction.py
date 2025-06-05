"""
Implementação de transações seguras para blockchain
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from decimal import Decimal

from .wallet import Wallet
from .security import SecurityConfig

@dataclass
class Transaction:
    """
    Transação imutável
    Representa transferência de tokens
    """
    from_address: str
    to_address: str
    amount: Decimal
    token_type: str
    timestamp: int
    nonce: str
    region_hash: Optional[str] = None
    coords: Optional[Tuple[float, float]] = None
    signature: Optional[str] = None
    hash: Optional[str] = None
    chain_id: int = 0
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
            
    def calculate_hash(self) -> str:
        """Calcula hash da transação"""
        tx_dict = {
            'from_address': self.from_address,
            'to_address': self.to_address,
            'amount': str(self.amount),
            'token_type': self.token_type,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'region_hash': self.region_hash,
            'coords': self.coords
        }
        tx_string = json.dumps(tx_dict, sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()
        
    def sign(self, wallet: Wallet):
        """Assina transação com carteira"""
        if wallet.address != self.from_address:
            raise ValueError("Apenas remetente pode assinar")
            
        self.signature = wallet.signing_key.sign(
            self.hash.encode(),
            hashfunc=hashlib.sha256
        ).hex()
        
    def verify(self) -> bool:
        """Verifica assinatura"""
        try:
            if not self.signature:
                return False
                
            # Recupera chave pública
            wallet = Wallet.get_wallet_by_address(self.from_address)
            if not wallet:
                return False
                
            # Verifica assinatura
            signature = bytes.fromhex(self.signature)
            wallet.verifying_key.verify(
                signature,
                self.hash.encode(),
                hashfunc=hashlib.sha256
            )
            
            return True
            
        except:
            return False

class TransactionPool:
    """
    Pool de transações pendentes
    Mantém transações não confirmadas
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.transactions: List[Transaction] = []
        self.used_nonces: Dict[int, Set[str]] = {}  # Chain ID -> Set of nonces
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """
        Adiciona transação ao pool
        Retorna False se inválida
        """
        # Valida campos básicos
        if not self._validate_transaction_basics(transaction):
            return False
            
        # Initialize nonce set for chain if needed
        if transaction.chain_id not in self.used_nonces:
            self.used_nonces[transaction.chain_id] = set()
            
        # Valida nonce
        if not self._validate_transaction_nonce(transaction):
            return False
            
        # Valida assinatura
        if not transaction.verify():
            return False
            
        # Adiciona ao pool
        self.transactions.append(transaction)
        self.used_nonces[transaction.chain_id].add(transaction.nonce)
        
        return True
        
    def get_transactions(
        self,
        chain_id: Optional[int] = None,
        max_count: Optional[int] = None
    ) -> List[Transaction]:
        """
        Retorna transações pendentes
        Ordenadas por timestamp
        
        Args:
            chain_id: Optional chain ID to filter by
            max_count: Maximum number of transactions to return
        """
        transactions = sorted(
            [tx for tx in self.transactions if chain_id is None or tx.chain_id == chain_id],
            key=lambda t: t.timestamp
        )
        
        if max_count:
            transactions = transactions[:max_count]
            
        return transactions
        
    def remove_transactions(self, transactions: List[Transaction]):
        """Remove transações confirmadas"""
        tx_hashes = {t.hash for t in transactions}
        
        # Remove transactions and their nonces
        removed_txs = [tx for tx in self.transactions if tx.hash in tx_hashes]
        self.transactions = [tx for tx in self.transactions if tx.hash not in tx_hashes]
        
        # Remove nonces for removed transactions
        for tx in removed_txs:
            if tx.chain_id in self.used_nonces:
                self.used_nonces[tx.chain_id].discard(tx.nonce)
                
                # Clean up empty nonce sets
                if not self.used_nonces[tx.chain_id]:
                    del self.used_nonces[tx.chain_id]
                    
    def _validate_transaction_basics(self, transaction: Transaction) -> bool:
        """Valida campos básicos"""
        
        try:
            # Verifica campos obrigatórios
            if not all([
                transaction.from_address,
                transaction.to_address,
                transaction.amount,
                transaction.token_type,
                transaction.timestamp,
                transaction.nonce
            ]):
                return False
                
            # Verifica tipos
            if not isinstance(transaction.amount, Decimal):
                return False
                
            if transaction.amount <= 0:
                return False
                
            if transaction.token_type not in ('central', 'lateral'):
                return False
                
            # Verifica timestamp
            current_time = int(time.time())
            if (transaction.timestamp > current_time + self.config.max_future_time or
                transaction.timestamp < current_time - 86400):  # 24h
                return False
                
            # Verifica região para token lateral
            if (transaction.token_type == 'lateral' and
                not transaction.region_hash):
                return False
                
            return True
            
        except:
            return False
            
    def _validate_transaction_nonce(self, transaction: Transaction) -> bool:
        """
        Validates transaction nonce
        Prevents replay attacks within same chain
        """
        # Check if nonce already used in this chain
        if transaction.nonce in self.used_nonces.get(transaction.chain_id, set()):
            return False
            
        return True

class TransactionValidator:
    """
    Validador de transações
    Garante integridade e segurança
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        
    def validate_transaction(
        self,
        transaction: Transaction,
        chain_id: int,
        check_balance: bool = True
    ) -> bool:
        """
        Valida transação completa
        
        Args:
            transaction: Transação a validar
            chain_id: Chain ID for replay protection
            check_balance: Se deve verificar saldo
        """
        try:
            # Valida hash
            if transaction.hash != transaction.calculate_hash():
                return False
                
            # Valida assinatura
            if not transaction.verify():
                return False
                
            # Validate chain_id
            if transaction.chain_id != chain_id:
                return False
                
            # Valida saldo
            if check_balance:
                wallet = Wallet.get_wallet_by_address(transaction.from_address)
                if not wallet:
                    return False
                    
                balance = wallet.get_balance(
                    transaction.token_type,
                    transaction.region_hash
                )
                if transaction.amount > balance:
                    return False
                    
            return True
            
        except:
            return False
            
    def validate_transactions(
        self,
        transactions: List[Transaction]
    ) -> List[bool]:
        """
        Valida lista de transações
        Retorna lista de resultados
        """
        results = []
        used_nonces = set()
        
        for tx in transactions:
            # Valida transação
            if not self.validate_transaction(tx):
                results.append(False)
                continue
                
            # Verifica double spend no bloco
            if tx.nonce in used_nonces:
                results.append(False)
                continue
                
            used_nonces.add(tx.nonce)
            results.append(True)
            
        return results 