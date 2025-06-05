"""
LogiChain Mesh State Manager
Handles mesh network state and synchronization
"""

import json
import time
import logging
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from ..core.blockchain import Blockchain
from .mesh_logger import MeshLogger
from .validator import MeshValidator

logger = logging.getLogger(__name__)

@dataclass
class PendingState:
    """Estado pendente para sincronização"""
    transactions: List[Dict] = field(default_factory=list)
    blocks: List[Dict] = field(default_factory=list)
    contracts: List[Dict] = field(default_factory=list)
    validations: List[Dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
class MeshStateManager:
    """Gerenciador de estado da rede mesh"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        mesh_logger: MeshLogger,
        validator: MeshValidator
    ):
        self.blockchain = blockchain
        self.mesh_logger = mesh_logger
        self.validator = validator
        
        # Estados pendentes por nó
        self.pending_states: Dict[str, PendingState] = {}
        
        # Cache de estados validados
        self.validated_states: Dict[str, Dict] = {}
        
        # Conjunto de hashes processados
        self.processed_hashes: Set[str] = set()
        
        # Lock para thread safety
        self._state_lock = threading.Lock()
        
    def add_pending_transaction(self, tx_data: Dict) -> bool:
        """Adiciona transação pendente"""
        try:
            node_id = tx_data.get("node_id")
            if not node_id:
                return False
                
            with self._state_lock:
                if node_id not in self.pending_states:
                    self.pending_states[node_id] = PendingState()
                    
                # Verificar duplicata
                tx_hash = self._calculate_hash(tx_data)
                if tx_hash in self.processed_hashes:
                    return False
                    
                self.pending_states[node_id].transactions.append(tx_data)
                self.processed_hashes.add(tx_hash)
                
            self.mesh_logger.log_state_event(
                node_id=node_id,
                event_type="pending_transaction_added",
                status="success"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding pending transaction: {str(e)}")
            return False
            
    def add_pending_block(self, block_data: Dict) -> bool:
        """Adiciona bloco pendente"""
        try:
            node_id = block_data.get("node_id")
            if not node_id:
                return False
                
            with self._state_lock:
                if node_id not in self.pending_states:
                    self.pending_states[node_id] = PendingState()
                    
                # Verificar duplicata
                block_hash = self._calculate_hash(block_data)
                if block_hash in self.processed_hashes:
                    return False
                    
                self.pending_states[node_id].blocks.append(block_data)
                self.processed_hashes.add(block_hash)
                
            self.mesh_logger.log_state_event(
                node_id=node_id,
                event_type="pending_block_added",
                status="success"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding pending block: {str(e)}")
            return False
            
    def add_pending_contract(self, contract_data: Dict) -> bool:
        """Adiciona contrato pendente"""
        try:
            node_id = contract_data.get("node_id")
            if not node_id:
                return False
                
            with self._state_lock:
                if node_id not in self.pending_states:
                    self.pending_states[node_id] = PendingState()
                    
                # Verificar duplicata
                contract_hash = self._calculate_hash(contract_data)
                if contract_hash in self.processed_hashes:
                    return False
                    
                self.pending_states[node_id].contracts.append(contract_data)
                self.processed_hashes.add(contract_hash)
                
            self.mesh_logger.log_state_event(
                node_id=node_id,
                event_type="pending_contract_added",
                status="success"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding pending contract: {str(e)}")
            return False
            
    def add_validation(self, validation_data: Dict) -> bool:
        """Adiciona validação"""
        try:
            node_id = validation_data.get("node_id")
            if not node_id:
                return False
                
            with self._state_lock:
                if node_id not in self.pending_states:
                    self.pending_states[node_id] = PendingState()
                    
                # Verificar duplicata
                validation_hash = self._calculate_hash(validation_data)
                if validation_hash in self.processed_hashes:
                    return False
                    
                self.pending_states[node_id].validations.append(validation_data)
                self.processed_hashes.add(validation_hash)
                
            self.mesh_logger.log_state_event(
                node_id=node_id,
                event_type="validation_added",
                status="success"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding validation: {str(e)}")
            return False
            
    def handle_sync(self, sync_data: Dict) -> bool:
        """Processa dados de sincronização"""
        try:
            node_id = sync_data.get("node_id")
            if not node_id:
                return False
                
            # Validar dados
            if not self.validator.validate_sync_data(sync_data):
                return False
                
            with self._state_lock:
                # Atualizar estado validado
                self.validated_states[node_id] = sync_data
                
                # Limpar estados pendentes processados
                if node_id in self.pending_states:
                    del self.pending_states[node_id]
                    
            self.mesh_logger.log_state_event(
                node_id=node_id,
                event_type="sync_processed",
                status="success"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling sync: {str(e)}")
            return False
            
    def update_state(self, state_data: Dict) -> bool:
        """Atualiza estado do nó"""
        try:
            node_id = state_data.get("node_id")
            if not node_id:
                return False
                
            # Validar estado
            if not self.validator.validate_state(state_data):
                return False
                
            with self._state_lock:
                # Atualizar estado validado
                self.validated_states[node_id] = state_data
                
            self.mesh_logger.log_state_event(
                node_id=node_id,
                event_type="state_updated",
                status="success"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating state: {str(e)}")
            return False
            
    def get_pending_state(self, node_id: str) -> Optional[PendingState]:
        """Retorna estado pendente do nó"""
        return self.pending_states.get(node_id)
        
    def get_validated_state(self, node_id: str) -> Optional[Dict]:
        """Retorna estado validado do nó"""
        return self.validated_states.get(node_id)
        
    def get_all_pending_states(self) -> Dict[str, PendingState]:
        """Retorna todos os estados pendentes"""
        return self.pending_states.copy()
        
    def get_all_validated_states(self) -> Dict[str, Dict]:
        """Retorna todos os estados validados"""
        return self.validated_states.copy()
        
    def _calculate_hash(self, data: Dict) -> str:
        """Calcula hash dos dados"""
        data_str = json.dumps(data, sort_keys=True)
        return self.blockchain.calculate_hash(data_str) 