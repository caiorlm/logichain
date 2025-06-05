"""
Sistema de mempool para gerenciar transações pendentes
"""

import time
import json
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
from .transaction import Transaction

@dataclass
class MempoolConfig:
    """Configuração do mempool"""
    max_size: int = 5000  # Número máximo de transações
    min_fee: float = 0.0001  # Taxa mínima por transação
    max_block_size: int = 1000  # Transações por bloco
    expiry_time: int = 3600  # Tempo até expirar (1 hora)

class Mempool:
    def __init__(self, config: Optional[MempoolConfig] = None):
        self.config = config or MempoolConfig()
        self.transactions: Dict[str, Transaction] = {}
        self.pending_rewards: List[Transaction] = []
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Adiciona uma transação ao mempool"""
        # Verificar tamanho máximo
        if len(self.transactions) >= self.config.max_size:
            return False
            
        # Verificar taxa mínima
        if transaction.fee < self.config.min_fee:
            return False
            
        # Adicionar transação
        self.transactions[transaction.tx_id] = transaction
        return True
        
    def add_mining_reward(self, miner_address: str, amount: float) -> Transaction:
        """Cria uma transação de recompensa de mineração"""
        reward = Transaction(
            sender="0x0000000000000000000000000000000000000000",
            recipient=miner_address,
            amount=amount,
            fee=0,
            timestamp=int(time.time()),
            data={"type": "mining_reward"}
        )
        self.pending_rewards.append(reward)
        return reward
        
    def get_block_transactions(self) -> List[Transaction]:
        """Retorna transações para o próximo bloco"""
        # Ordenar por taxa (maior primeiro)
        sorted_txs = sorted(
            self.transactions.values(),
            key=lambda tx: tx.fee,
            reverse=True
        )
        
        # Pegar transações até o limite do bloco
        block_txs = sorted_txs[:self.config.max_block_size]
        
        # Adicionar recompensa pendente se houver
        if self.pending_rewards:
            block_txs.append(self.pending_rewards.pop(0))
            
        return block_txs
        
    async def get_transactions(self) -> List[Transaction]:
        """Retorna todas as transações pendentes ordenadas por taxa"""
        # Usar o mesmo método que get_block_transactions mas sem limite de tamanho
        sorted_txs = sorted(
            self.transactions.values(),
            key=lambda tx: tx.fee,
            reverse=True
        )
        return sorted_txs
        
    def remove_transactions(self, transaction_ids: List[str]):
        """Remove transações que já foram mineradas"""
        for tx_id in transaction_ids:
            self.transactions.pop(tx_id, None)
            
    def clear_expired(self):
        """Remove transações expiradas"""
        current_time = int(time.time())
        expired = [
            tx_id for tx_id, tx in self.transactions.items()
            if current_time - tx.timestamp > self.config.expiry_time
        ]
        for tx_id in expired:
            self.transactions.pop(tx_id)
            
    async def start_cleanup(self):
        """Inicia limpeza periódica de transações expiradas"""
        while True:
            self.clear_expired()
            await asyncio.sleep(300)  # Limpar a cada 5 minutos 