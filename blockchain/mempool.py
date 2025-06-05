"""
Módulo de mempool com priorização de transações
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import heapq
import threading

from .core.transaction import Transaction
from .security import SecurityConfig

@dataclass(order=True)
class MempoolEntry:
    """Entrada do mempool com prioridade"""
    fee_per_byte: float
    timestamp: datetime
    transaction: Transaction = field(compare=False)
    
    def __eq__(self, other):
        if not isinstance(other, MempoolEntry):
            return False
        return self.transaction.hash == other.transaction.hash

class PriorityMempool:
    """Mempool com priorização de transações"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        """Inicializa mempool"""
        self.config = config or SecurityConfig()
        self.entries: List[MempoolEntry] = []
        self.transactions: Dict[str, Transaction] = {}
        self.ancestors: Dict[str, Set[str]] = {}
        self.descendants: Dict[str, Set[str]] = {}
        self.lock = threading.RLock()
        
    def add_transaction(self, tx: Transaction) -> bool:
        """Adiciona transação ao mempool"""
        with self.lock:
            # Verifica se já existe
            if tx.hash in self.transactions:
                return False
                
            # Verifica tamanho
            if len(tx.serialize()) > self.config.max_tx_size:
                return False
                
            # Verifica fee
            if tx.fee < self.config.min_fee:
                return False
                
            # Verifica ancestors
            ancestors = self._get_ancestors(tx)
            if len(ancestors) > self.config.max_mempool_ancestors:
                return False
                
            # Verifica tamanho total do mempool
            if len(self.transactions) >= self.config.max_mempool_size:
                self._evict_low_fee_transactions()
                
            # Calcula prioridade
            fee_per_byte = tx.fee / len(tx.serialize())
            entry = MempoolEntry(
                fee_per_byte=fee_per_byte,
                timestamp=datetime.now(),
                transaction=tx
            )
            
            # Adiciona
            heapq.heappush(self.entries, entry)
            self.transactions[tx.hash] = tx
            
            # Atualiza grafos
            self.ancestors[tx.hash] = ancestors
            for ancestor in ancestors:
                self.descendants[ancestor].add(tx.hash)
                
            return True
            
    def remove_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """Remove transação do mempool"""
        with self.lock:
            if tx_hash not in self.transactions:
                return None
                
            tx = self.transactions.pop(tx_hash)
            
            # Remove dos grafos
            ancestors = self.ancestors.pop(tx_hash, set())
            for ancestor in ancestors:
                self.descendants[ancestor].remove(tx_hash)
                
            descendants = self.descendants.pop(tx_hash, set())
            for descendant in descendants:
                self.ancestors[descendant].remove(tx_hash)
                
            # Remove da fila de prioridade
            self.entries = [
                e for e in self.entries
                if e.transaction.hash != tx_hash
            ]
            heapq.heapify(self.entries)
            
            return tx
            
    def get_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """Retorna transação do mempool"""
        return self.transactions.get(tx_hash)
        
    def contains_transaction(self, tx_hash: str) -> bool:
        """Verifica se transação está no mempool"""
        return tx_hash in self.transactions
        
    def get_transactions(
        self,
        max_size: Optional[int] = None
    ) -> List[Transaction]:
        """Retorna transações ordenadas por prioridade"""
        with self.lock:
            transactions = []
            size = 0
            
            for entry in sorted(
                self.entries,
                key=lambda e: (-e.fee_per_byte, e.timestamp)
            ):
                tx = entry.transaction
                tx_size = len(tx.serialize())
                
                if max_size and size + tx_size > max_size:
                    break
                    
                transactions.append(tx)
                size += tx_size
                
            return transactions
            
    def clear(self):
        """Limpa o mempool"""
        with self.lock:
            self.entries = []
            self.transactions.clear()
            self.ancestors.clear()
            self.descendants.clear()
            
    def _get_ancestors(self, tx: Transaction) -> Set[str]:
        """Retorna ancestrais de uma transação"""
        ancestors = set()
        to_visit = set(tx.inputs)
        
        while to_visit:
            tx_hash = to_visit.pop()
            if tx_hash in self.transactions:
                ancestors.add(tx_hash)
                parent_tx = self.transactions[tx_hash]
                to_visit.update(parent_tx.inputs)
                
        return ancestors
        
    def _evict_low_fee_transactions(self):
        """Remove transações com menor fee quando mempool está cheio"""
        with self.lock:
            # Ordena por fee
            sorted_entries = sorted(
                self.entries,
                key=lambda e: (e.fee_per_byte, -e.timestamp)
            )
            
            # Remove 10% das transações com menor fee
            num_to_remove = max(
                1,
                len(sorted_entries) // 10
            )
            
            for entry in sorted_entries[:num_to_remove]:
                self.remove_transaction(entry.transaction.hash)
                
    @property
    def size(self) -> int:
        """Retorna número de transações no mempool"""
        return len(self.transactions)
        
    @property
    def max_size(self) -> int:
        """Retorna tamanho máximo do mempool"""
        return self.config.max_mempool_size 