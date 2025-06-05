"""
LogiChain Mesh Event Handler
Handles all mesh network events and state transitions
"""

import logging
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
from ..core.blockchain import Blockchain
from .hybrid_manager import HybridMeshManager
from .mesh_logger import MeshLogger
from .validator import MeshValidator
from .state_manager import MeshStateManager

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Tipos de eventos da rede mesh"""
    TRANSACTION = "transaction"
    BLOCK = "block"
    CONTRACT = "contract"
    VALIDATION = "validation"
    SYNC = "sync"
    ERROR = "error"
    STATE = "state"

@dataclass
class MeshEvent:
    """Evento da rede mesh"""
    type: EventType
    data: Dict
    timestamp: float
    node_id: str
    signature: Optional[str] = None
    status: str = "pending"

class MeshEventHandler:
    """Handler de eventos da rede mesh"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        mesh_manager: HybridMeshManager,
        state_manager: MeshStateManager,
        mesh_logger: MeshLogger,
        validator: MeshValidator
    ):
        self.blockchain = blockchain
        self.mesh_manager = mesh_manager
        self.state_manager = state_manager
        self.mesh_logger = mesh_logger
        self.validator = validator
        
        # Cache de eventos processados
        self._processed_events: Dict[str, MeshEvent] = {}
        
    def handle_event(self, event_type: EventType, event_data: Dict) -> bool:
        """Handle mesh network event"""
        try:
            # Criar evento
            event = MeshEvent(
                type=event_type,
                data=event_data,
                timestamp=time.time(),
                node_id=event_data.get("node_id", "unknown")
            )
            
            # Validar evento
            if not self._validate_event(event):
                return False
                
            # Processar por tipo
            handlers = {
                EventType.TRANSACTION: self._handle_transaction,
                EventType.BLOCK: self._handle_block,
                EventType.CONTRACT: self._handle_contract,
                EventType.VALIDATION: self._handle_validation,
                EventType.SYNC: self._handle_sync,
                EventType.STATE: self._handle_state
            }
            
            handler = handlers.get(event_type)
            if not handler:
                logger.error(f"No handler for event type: {event_type}")
                return False
                
            # Executar handler
            success = handler(event)
            
            # Registrar evento
            if success:
                self._processed_events[self._get_event_id(event)] = event
                self.mesh_logger.log_event(event)
                
            return success
            
        except Exception as e:
            logger.error(f"Error handling event: {str(e)}")
            self.mesh_logger.log_error(
                error_type="event_handler_error",
                message=str(e),
                event_type=event_type.value
            )
            return False
            
    def _validate_event(self, event: MeshEvent) -> bool:
        """Validate mesh event"""
        try:
            # Verificar duplicata
            event_id = self._get_event_id(event)
            if event_id in self._processed_events:
                return False
                
            # Validar assinatura se presente
            if event.signature:
                if not self.validator.validate_signature(
                    event.node_id,
                    event.data,
                    event.signature
                ):
                    return False
                    
            # Validar dados específicos do tipo
            return self.validator.validate_event(event)
            
        except Exception as e:
            logger.error(f"Error validating event: {str(e)}")
            return False
            
    def _handle_transaction(self, event: MeshEvent) -> bool:
        """Handle transaction event"""
        try:
            tx_data = event.data
            
            # Validar transação
            if not self.validator.validate_transaction(tx_data):
                return False
                
            # Adicionar ao pool
            if self.blockchain.is_online():
                # Online: adicionar direto ao pool
                return self.blockchain.add_transaction(tx_data)
            else:
                # Offline: armazenar para sync posterior
                return self.state_manager.add_pending_transaction(tx_data)
                
        except Exception as e:
            logger.error(f"Error handling transaction: {str(e)}")
            return False
            
    def _handle_block(self, event: MeshEvent) -> bool:
        """Handle block event"""
        try:
            block_data = event.data
            
            # Validar bloco
            if not self.validator.validate_block(block_data):
                return False
                
            # Processar bloco
            if self.blockchain.is_online():
                # Online: adicionar à chain
                return self.blockchain.add_block(block_data)
            else:
                # Offline: armazenar para sync posterior
                return self.state_manager.add_pending_block(block_data)
                
        except Exception as e:
            logger.error(f"Error handling block: {str(e)}")
            return False
            
    def _handle_contract(self, event: MeshEvent) -> bool:
        """Handle contract event"""
        try:
            contract_data = event.data
            
            # Validar contrato
            if not self.validator.validate_contract(contract_data):
                return False
                
            # Processar contrato
            if self.blockchain.is_online():
                return self.blockchain.add_contract(contract_data)
            else:
                return self.state_manager.add_pending_contract(contract_data)
                
        except Exception as e:
            logger.error(f"Error handling contract: {str(e)}")
            return False
            
    def _handle_validation(self, event: MeshEvent) -> bool:
        """Handle validation event"""
        try:
            validation_data = event.data
            
            # Validar prova
            if not self.validator.validate_proof(validation_data):
                return False
                
            # Processar validação
            return self.state_manager.add_validation(validation_data)
            
        except Exception as e:
            logger.error(f"Error handling validation: {str(e)}")
            return False
            
    def _handle_sync(self, event: MeshEvent) -> bool:
        """Handle sync event"""
        try:
            sync_data = event.data
            
            # Validar dados de sync
            if not self.validator.validate_sync_data(sync_data):
                return False
                
            # Processar sync
            return self.state_manager.handle_sync(sync_data)
            
        except Exception as e:
            logger.error(f"Error handling sync: {str(e)}")
            return False
            
    def _handle_state(self, event: MeshEvent) -> bool:
        """Handle state event"""
        try:
            state_data = event.data
            
            # Validar estado
            if not self.validator.validate_state(state_data):
                return False
                
            # Atualizar estado
            return self.state_manager.update_state(state_data)
            
        except Exception as e:
            logger.error(f"Error handling state: {str(e)}")
            return False
            
    def _get_event_id(self, event: MeshEvent) -> str:
        """Generate unique event ID"""
        return f"{event.type.value}:{event.node_id}:{event.timestamp}"
        
    def get_pending_events(self) -> List[MeshEvent]:
        """Get pending events"""
        return [
            event for event in self._processed_events.values()
            if event.status == "pending"
        ]
        
    def get_event_history(self) -> List[MeshEvent]:
        """Get event history"""
        return list(self._processed_events.values()) 