"""
Sistema de sharding para escalabilidade
"""

from typing import Dict, List, Optional, Set, Tuple, Any
import hashlib
import threading
import time
import logging
from dataclasses import dataclass
from enum import Enum

from ..core.transaction import Transaction
from ..core.block import Block
from ..security import SecurityManager

class ShardType(Enum):
    """Tipos de shard"""
    TRANSACTION = "transaction"  # Processa transações
    STATE = "state"  # Mantém estado
    COMPUTE = "compute"  # Executa contratos

@dataclass
class ShardInfo:
    """Informações do shard"""
    id: str
    type: ShardType
    capacity: int
    current_load: int
    nodes: Set[str]
    created_at: float

class ShardManager:
    """
    Gerenciador de shards com:
    - Criação dinâmica de shards
    - Balanceamento de carga
    - Roteamento de transações
    - Cross-shard communication
    """
    
    def __init__(
        self,
        min_shards: int = 3,
        max_shards: int = 10,
        shard_capacity: int = 1000,
        rebalance_threshold: float = 0.8
    ):
        # Configuração
        self.min_shards = min_shards
        self.max_shards = max_shards
        self.shard_capacity = shard_capacity
        self.rebalance_threshold = rebalance_threshold
        
        # Estado
        self.shards: Dict[str, ShardInfo] = {}
        self.node_to_shard: Dict[str, str] = {}
        self.tx_to_shard: Dict[str, str] = {}
        
        # Componentes
        self.security = SecurityManager()
        
        # Threading
        self.lock = threading.RLock()
        self._start_rebalance_thread()
        
        # Inicialização
        self._create_initial_shards()
        
        logging.info("ShardManager initialized")
        
    def assign_transaction(
        self,
        tx: Transaction
    ) -> str:
        """
        Atribui transação a um shard
        
        Args:
            tx: Transação a ser atribuída
            
        Returns:
            str: ID do shard
        """
        with self.lock:
            # Verifica se já está atribuída
            if tx.hash in self.tx_to_shard:
                return self.tx_to_shard[tx.hash]
                
            # Encontra shard apropriado
            shard_id = self._find_best_shard(tx)
            
            # Atualiza mapeamentos
            self.tx_to_shard[tx.hash] = shard_id
            shard = self.shards[shard_id]
            shard.current_load += 1
            
            # Verifica necessidade de rebalanceamento
            self._check_rebalance_needed()
            
            return shard_id
            
    def get_shard_for_transaction(
        self,
        tx_hash: str
    ) -> Optional[str]:
        """Retorna shard de uma transação"""
        return self.tx_to_shard.get(tx_hash)
        
    def get_shard_info(
        self,
        shard_id: str
    ) -> Optional[ShardInfo]:
        """Retorna informações do shard"""
        return self.shards.get(shard_id)
        
    def register_node(
        self,
        node_id: str,
        shard_type: Optional[ShardType] = None
    ) -> str:
        """
        Registra nó em um shard
        
        Args:
            node_id: ID do nó
            shard_type: Tipo preferido de shard
            
        Returns:
            str: ID do shard atribuído
        """
        with self.lock:
            # Remove registro anterior
            if node_id in self.node_to_shard:
                old_shard = self.shards[self.node_to_shard[node_id]]
                old_shard.nodes.remove(node_id)
                
            # Encontra melhor shard
            shard_id = self._find_best_shard_for_node(node_id, shard_type)
            
            # Atualiza registros
            self.node_to_shard[node_id] = shard_id
            shard = self.shards[shard_id]
            shard.nodes.add(node_id)
            
            return shard_id
            
    def unregister_node(self, node_id: str):
        """Remove nó do shard"""
        with self.lock:
            if node_id in self.node_to_shard:
                shard_id = self.node_to_shard[node_id]
                shard = self.shards[shard_id]
                shard.nodes.remove(node_id)
                del self.node_to_shard[node_id]
                
    def _create_initial_shards(self):
        """Cria shards iniciais"""
        with self.lock:
            # Cria um de cada tipo
            for shard_type in ShardType:
                self._create_shard(shard_type)
                
    def _create_shard(
        self,
        shard_type: ShardType
    ) -> str:
        """
        Cria novo shard
        
        Args:
            shard_type: Tipo do shard
            
        Returns:
            str: ID do shard
        """
        # Gera ID único
        shard_id = hashlib.sha256(
            f"{shard_type.value}{time.time()}".encode()
        ).hexdigest()[:8]
        
        # Cria shard
        shard = ShardInfo(
            id=shard_id,
            type=shard_type,
            capacity=self.shard_capacity,
            current_load=0,
            nodes=set(),
            created_at=time.time()
        )
        
        self.shards[shard_id] = shard
        logging.info(f"Created shard: {shard_id} ({shard_type.value})")
        
        return shard_id
        
    def _find_best_shard(
        self,
        tx: Transaction
    ) -> str:
        """
        Encontra melhor shard para transação
        
        Args:
            tx: Transação
            
        Returns:
            str: ID do melhor shard
        """
        # Prioriza shards de transação
        candidates = [
            s for s in self.shards.values()
            if s.type == ShardType.TRANSACTION
        ]
        
        # Ordena por carga
        candidates.sort(key=lambda s: s.current_load / s.capacity)
        
        # Retorna primeiro ou cria novo
        if not candidates or candidates[0].current_load >= self.shard_capacity:
            if len(self.shards) < self.max_shards:
                return self._create_shard(ShardType.TRANSACTION)
                
        return candidates[0].id
        
    def _find_best_shard_for_node(
        self,
        node_id: str,
        preferred_type: Optional[ShardType]
    ) -> str:
        """
        Encontra melhor shard para nó
        
        Args:
            node_id: ID do nó
            preferred_type: Tipo preferido
            
        Returns:
            str: ID do melhor shard
        """
        candidates = list(self.shards.values())
        
        if preferred_type:
            type_candidates = [
                s for s in candidates
                if s.type == preferred_type
            ]
            if type_candidates:
                candidates = type_candidates
                
        # Ordena por número de nós
        candidates.sort(key=lambda s: len(s.nodes))
        
        # Retorna primeiro ou cria novo
        if not candidates or len(candidates[0].nodes) >= self.shard_capacity:
            if len(self.shards) < self.max_shards:
                return self._create_shard(
                    preferred_type or ShardType.TRANSACTION
                )
                
        return candidates[0].id
        
    def _check_rebalance_needed(self):
        """Verifica necessidade de rebalanceamento"""
        # Calcula carga média
        loads = [
            s.current_load / s.capacity
            for s in self.shards.values()
        ]
        avg_load = sum(loads) / len(loads)
        
        # Verifica threshold
        if avg_load > self.rebalance_threshold:
            self._rebalance_shards()
            
    def _rebalance_shards(self):
        """Rebalanceia shards de forma otimizada"""
        with self.lock:
            if len(self.shards) >= self.max_shards:
                return
                
            # Análise de carga
            loads = [
                (shard_id, shard.current_load / shard.capacity)
                for shard_id, shard in self.shards.items()
            ]
            avg_load = sum(l for _, l in loads) / len(loads)
            
            # Identifica shards desbalanceados
            overloaded = [
                (sid, load) for sid, load in loads
                if load > avg_load * 1.2  # 20% acima da média
            ]
            underloaded = [
                (sid, load) for sid, load in loads
                if load < avg_load * 0.8  # 20% abaixo da média
            ]
            
            if not overloaded:
                return
                
            # Métricas antes do rebalanceamento
            self.metrics.record_rebalance_start(loads)
            
            # Cria novos shards se necessário
            new_shards = []
            while len(self.shards) < self.max_shards and overloaded:
                shard_type = self._determine_shard_type(overloaded[0][0])
                new_shard_id = self._create_shard(shard_type)
                new_shards.append(new_shard_id)
                
            # Redistribui carga
            for old_shard_id, _ in overloaded:
                old_shard = self.shards[old_shard_id]
                
                # Encontra transações para mover
                movable_txs = self._find_movable_transactions(old_shard)
                
                # Distribui entre shards com menos carga
                target_shards = (
                    [sid for sid, _ in underloaded] +
                    new_shards
                )
                
                if not target_shards:
                    continue
                    
                # Move transações
                self._move_transactions(
                    movable_txs,
                    old_shard_id,
                    target_shards
                )
                
            # Métricas após rebalanceamento
            new_loads = [
                (shard_id, shard.current_load / shard.capacity)
                for shard_id, shard in self.shards.items()
            ]
            self.metrics.record_rebalance_end(new_loads)
            
    def _determine_shard_type(self, overloaded_shard_id: str) -> ShardType:
        """Determina melhor tipo para novo shard"""
        overloaded = self.shards[overloaded_shard_id]
        
        # Analisa tipos de transações
        tx_types = self._analyze_transaction_types(overloaded)
        
        # Escolhe tipo mais adequado
        if tx_types.get('contract', 0) > 0.5:  # Mais de 50% contratos
            return ShardType.COMPUTE
        elif tx_types.get('state', 0) > 0.5:  # Mais de 50% estado
            return ShardType.STATE
        else:
            return ShardType.TRANSACTION
            
    def _find_movable_transactions(
        self,
        shard: ShardInfo
    ) -> List[Tuple[str, Transaction]]:
        """Encontra transações que podem ser movidas"""
        movable = []
        
        # Agrupa por endereço
        by_address: Dict[str, List[str]] = {}
        for tx_hash in self.tx_to_shard:
            if self.tx_to_shard[tx_hash] != shard.id:
                continue
                
            tx = self.get_transaction(tx_hash)
            if not tx:
                continue
                
            if tx.from_address not in by_address:
                by_address[tx.from_address] = []
            by_address[tx.from_address].append(tx_hash)
            
        # Seleciona grupos completos
        for address, tx_hashes in by_address.items():
            # Verifica dependências
            if self._can_move_group(tx_hashes):
                for tx_hash in tx_hashes:
                    tx = self.get_transaction(tx_hash)
                    if tx:
                        movable.append((tx_hash, tx))
                        
        return movable
        
    def _can_move_group(self, tx_hashes: List[str]) -> bool:
        """Verifica se grupo pode ser movido"""
        # Verifica dependências entre transações
        deps = self._get_transaction_dependencies(tx_hashes)
        
        # Só move se todas dependências estão no grupo
        return all(dep in tx_hashes for dep in deps)
        
    def _move_transactions(
        self,
        transactions: List[Tuple[str, Transaction]],
        from_shard: str,
        target_shards: List[str]
    ):
        """Move transações entre shards"""
        if not transactions or not target_shards:
            return
            
        # Distribui uniformemente
        txs_per_shard = len(transactions) // len(target_shards)
        if txs_per_shard == 0:
            txs_per_shard = 1
            
        # Move em grupos
        current_shard_idx = 0
        for i in range(0, len(transactions), txs_per_shard):
            if current_shard_idx >= len(target_shards):
                break
                
            target_shard = target_shards[current_shard_idx]
            group = transactions[i:i + txs_per_shard]
            
            # Move grupo
            for tx_hash, tx in group:
                self._move_transaction(tx_hash, from_shard, target_shard)
                
            current_shard_idx += 1
            
    def _move_transaction(
        self,
        tx_hash: str,
        from_shard: str,
        to_shard: str
    ):
        """Move uma transação entre shards"""
        # Atualiza mapeamentos
        self.tx_to_shard[tx_hash] = to_shard
        
        # Atualiza contadores
        self.shards[from_shard].current_load -= 1
        self.shards[to_shard].current_load += 1
        
        # Registra métrica
        self.metrics.record_transaction_move(
            tx_hash,
            from_shard,
            to_shard
        )
        
    def _start_rebalance_thread(self):
        """Inicia thread de rebalanceamento"""
        def rebalance_loop():
            while True:
                try:
                    time.sleep(60)  # 1 minuto
                    self._check_rebalance_needed()
                except Exception as e:
                    logging.error(f"Rebalance error: {e}")
                    
        thread = threading.Thread(
            target=rebalance_loop,
            daemon=True
        )
        thread.start() 

class ShardMetrics:
    """Métricas detalhadas de sharding"""
    
    def __init__(self):
        self.metrics: Dict[str, List[Tuple[float, Any]]] = {}
        self.lock = threading.Lock()
        
    def record_rebalance_start(
        self,
        loads: List[Tuple[str, float]]
    ):
        """Registra início de rebalanceamento"""
        with self.lock:
            self._record(
                'rebalance_start',
                {
                    'loads': dict(loads),
                    'timestamp': time.time()
                }
            )
            
    def record_rebalance_end(
        self,
        loads: List[Tuple[str, float]]
    ):
        """Registra fim de rebalanceamento"""
        with self.lock:
            self._record(
                'rebalance_end',
                {
                    'loads': dict(loads),
                    'timestamp': time.time()
                }
            )
            
    def record_transaction_move(
        self,
        tx_hash: str,
        from_shard: str,
        to_shard: str
    ):
        """Registra movimentação de transação"""
        with self.lock:
            self._record(
                'transaction_move',
                {
                    'tx_hash': tx_hash,
                    'from_shard': from_shard,
                    'to_shard': to_shard,
                    'timestamp': time.time()
                }
            )
            
    def _record(self, name: str, value: Any):
        """Registra métrica"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append((time.time(), value))
        
    def get_stats(
        self,
        metric_name: str,
        window: int = 3600
    ) -> List[Dict]:
        """Retorna estatísticas da métrica"""
        with self.lock:
            if metric_name not in self.metrics:
                return []
                
            now = time.time()
            return [
                value for ts, value in self.metrics[metric_name]
                if now - ts <= window
            ] 