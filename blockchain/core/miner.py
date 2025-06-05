"""
Sistema de mineração que integra mempool com PoW
"""

import time
import asyncio
import logging
import hashlib
import json
from typing import Dict, Optional
from dataclasses import dataclass
from .block import Block
from .mempool import Mempool
from .wallet import Wallet
from ..consensus.pow_consensus import PoWConsensus
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class MiningConfig:
    """Configuração de mineração"""
    block_reward: float = 50.0  # Recompensa base por bloco
    target_block_time: int = 60  # Tempo alvo entre blocos (segundos)
    difficulty_adjustment_interval: int = 2016  # Blocos entre ajustes
    max_threads: int = 4  # Número máximo de threads para mineração
    nonce_range_per_thread: int = 1000000  # Range de nonce por thread

class Miner:
    def __init__(self, wallet: Wallet, mempool: Mempool, consensus: PoWConsensus, config: MiningConfig):
        self.wallet = wallet
        self.mempool = mempool
        self.consensus = consensus
        self.config = config
        
        self.running = False
        self.current_block = None
        self.start_time = 0
        self.total_hashes = 0
        self.total_mined = 0
        self.executor = ThreadPoolExecutor(max_workers=config.max_threads)
        self.mining_tasks = []
        self.last_mined_hash = "0" * 64
        
    async def start(self):
        """Inicia mineração"""
        if self.running:
            return
            
        logger.info(f"Iniciando mineração com {self.config.max_threads} threads")
        
        self.running = True
        self.start_time = time.time()
        
        # Inicia threads de mineração com ranges diferentes de nonce
        for thread_id in range(self.config.max_threads):
            task = asyncio.create_task(
                self._mining_task(
                    thread_id,
                    thread_id * self.config.nonce_range_per_thread,
                    (thread_id + 1) * self.config.nonce_range_per_thread
                )
            )
            self.mining_tasks.append(task)
            
    async def stop(self):
        """Para mineração"""
        if not self.running:
            return
            
        logger.info("Parando mineração...")
        self.running = False
        
        # Cancela todas as tasks
        for task in self.mining_tasks:
            task.cancel()
        self.mining_tasks.clear()
        
        self.executor.shutdown(wait=True)
        
    async def _mining_task(self, thread_id: int, nonce_start: int, nonce_end: int):
        """Tarefa de mineração"""
        logger.info(f"Thread {thread_id} iniciada com range de nonce {nonce_start}-{nonce_end}")
        
        while self.running:
            try:
                # Obtém novo bloco para minerar
                block = await self._get_block_template()
                block.nonce = nonce_start
                
                # Minera o bloco
                mined_block = await self._mine_block(block, nonce_end)
                
                if mined_block:
                    # Submete bloco minerado
                    if await self._submit_block(mined_block):
                        self.total_mined += 1
                        self.last_mined_hash = mined_block.hash
                        logger.info(f"Thread {thread_id} minerou bloco com sucesso: {mined_block.hash}")
                        
                        # Atualiza último hash para próximo bloco
                        await self._update_chain_state(mined_block)
                    
            except Exception as e:
                logger.error(f"Erro na mineração (thread {thread_id}): {e}")
                await asyncio.sleep(1)
                
    async def _get_block_template(self) -> Block:
        """Obtém template do próximo bloco"""
        # Obtém transações pendentes
        transactions = await self.mempool.get_transactions()
        
        # Cria transação de recompensa
        coinbase_tx = {
            "type": "coinbase",
            "to": self.wallet.address,
            "amount": self.config.block_reward,
            "timestamp": int(time.time())
        }
        
        # Monta bloco
        block = Block(
            version=1,
            timestamp=int(time.time()),
            previous_hash=self.last_mined_hash,  # Usa último hash minerado
            transactions=[coinbase_tx] + transactions,
            miner=self.wallet.address,
            nonce=0
        )
        
        return block
        
    async def _mine_block(self, block: Block, nonce_limit: int) -> Optional[Block]:
        """Minera um bloco usando força bruta real"""
        target = 2 ** (256 - self.consensus.difficulty)
        
        while self.running and block.nonce < nonce_limit:
            try:
                # Incrementa nonce
                block.nonce += 1
                self.total_hashes += 1
                
                # Calcula hash real do bloco
                block_data = self._prepare_block_data(block)
                block_hash = self._calculate_block_hash(block_data)
                
                # Atualiza hash do bloco
                block.hash = block_hash
                
                # Verifica dificuldade
                if int(block_hash, 16) < target:
                    block.timestamp = int(time.time())  # Atualiza timestamp
                    self.last_block_time = block.timestamp
                    
                    # Valida bloco antes de submeter
                    if await self._validate_block(block):
                        return block
                    
                # A cada 1000 hashes verifica se deve continuar e atualiza mempool
                if block.nonce % 1000 == 0:
                    # Atualiza transações do bloco
                    new_txs = await self.mempool.get_transactions()
                    if new_txs != block.transactions[1:]:  # Ignora coinbase
                        block.transactions = [block.transactions[0]] + new_txs
                        block.timestamp = int(time.time())
                    
                    # Verifica se outro thread já minerou um bloco
                    if self.last_mined_hash != block.previous_hash:
                        return None
                        
                    await asyncio.sleep(0)
                    
            except Exception as e:
                logger.error(f"Erro durante mineração: {e}")
                await asyncio.sleep(1)
                
        return None
        
    async def _update_chain_state(self, block: Block):
        """Atualiza estado da chain após minerar bloco"""
        self.last_mined_hash = block.hash
        await self._add_block(block)
        
    def _prepare_block_data(self, block: Block) -> bytes:
        """Prepara dados do bloco para hash"""
        # Ordena transações por timestamp
        sorted_txs = sorted(block.transactions, key=lambda x: x["timestamp"])
        
        # Monta dados do bloco
        block_data = {
            "version": block.version,
            "timestamp": block.timestamp,
            "previous_hash": block.previous_hash,
            "transactions": sorted_txs,
            "miner": block.miner,
            "nonce": block.nonce
        }
        
        # Serializa para bytes
        return json.dumps(block_data, sort_keys=True).encode()
        
    def _calculate_block_hash(self, data: bytes) -> str:
        """Calcula hash real do bloco usando SHA3-256"""
        hasher = hashlib.sha3_256()
        hasher.update(data)
        return hasher.hexdigest()
        
    async def _validate_block(self, block: Block) -> bool:
        """Valida bloco minerado"""
        try:
            # Valida estrutura básica
            if not self._validate_block_structure(block):
                return False
                
            # Valida proof of work
            if not self.consensus.validate_block(block):
                return False
                
            # Valida transações
            if not await self._validate_transactions(block.transactions):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Erro na validação do bloco: {e}")
            return False
            
    def _validate_block_structure(self, block: Block) -> bool:
        """Valida estrutura básica do bloco"""
        required_fields = ["version", "timestamp", "previous_hash", 
                         "transactions", "miner", "nonce", "hash"]
                         
        return all(hasattr(block, field) for field in required_fields)
        
    async def _validate_transactions(self, transactions: list) -> bool:
        """Valida transações do bloco"""
        # Verifica se tem pelo menos uma transação (coinbase)
        if not transactions:
            return False
            
        # Valida coinbase
        if not self._validate_coinbase(transactions[0]):
            return False
            
        # Valida demais transações
        # TODO: Implementar validação completa
        
        return True
        
    def _validate_coinbase(self, tx: dict) -> bool:
        """Valida transação coinbase"""
        return (
            tx["type"] == "coinbase" and
            tx["to"] == self.wallet.address and
            tx["amount"] == self.config.block_reward
        )
        
    async def _submit_block(self, block: Block) -> bool:
        """Submete bloco minerado"""
        # TODO: Implementar submissão do bloco
        return True
        
    async def _get_previous_hash(self) -> str:
        """Obtém hash do último bloco"""
        return self.last_mined_hash
        
    async def _get_last_block(self) -> Optional[Block]:
        """Obtém último bloco da chain"""
        # TODO: Implementar
        return None
        
    async def _add_block(self, block: Block) -> bool:
        """Adiciona bloco ao blockchain"""
        # TODO: Implementar
        pass
        
    def get_stats(self) -> Dict:
        """Obtém estatísticas de mineração em tempo real"""
        current_time = time.time()
        uptime = max(1.0, current_time - self.start_time)  # Garante uptime mínimo de 1 segundo
        hash_rate = self.total_hashes / uptime
        
        return {
            "running": self.running,
            "uptime": int(uptime),
            "hash_rate": int(hash_rate),
            "total_hashes": self.total_hashes,
            "total_mined": self.total_mined,
            "threads": self.config.max_threads,
            "difficulty": self.consensus.difficulty,
            "last_block_time": self.last_block_time if hasattr(self, 'last_block_time') else 0,
            "last_mined_hash": self.last_mined_hash
        } 