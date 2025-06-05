"""
LogiChain Mesh Integration
Integra todos os componentes do sistema mesh
"""

import logging
import time
import threading
from typing import Dict, Optional, List
from ..core.blockchain import Blockchain
from ..mempool import PriorityMempool
from ..pod import ProofOfDelivery, Block
from .hybrid_manager import HybridMeshManager
from .lora import LoRaManager
from .mesh_logger import MeshLogger
from .validator import MeshValidator
from .state_manager import MeshStateManager
from .event_handler import MeshEventHandler, EventType
from .config import MeshConfig, load_config

logger = logging.getLogger(__name__)

class MeshIntegration:
    """Integração do sistema mesh com a blockchain"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        mempool: PriorityMempool,
        config_dict: Optional[Dict] = None
    ):
        # Componentes principais
        self.blockchain = blockchain
        self.mempool = mempool
        self.config = load_config(config_dict)
        
        # Componentes mesh
        self.mesh_logger = MeshLogger()
        self.validator = MeshValidator()
        self.state_manager = MeshStateManager(
            blockchain=blockchain,
            mesh_logger=self.mesh_logger,
            validator=self.validator
        )
        
        # LoRa manager
        self.lora = LoRaManager(
            node_id=self.config.NETWORK_ID,
            frequency=self.config.LORA_FREQUENCY,
            bandwidth=self.config.LORA_BANDWIDTH,
            spreading_factor=self.config.LORA_SPREADING_FACTOR,
            coding_rate=self.config.LORA_CODING_RATE,
            power_level=self.config.LORA_POWER,
            sync_word=self.config.LORA_SYNC_WORD
        )
        
        # Mesh manager
        self.mesh_manager = HybridMeshManager(
            blockchain=blockchain,
            lora=self.lora,
            config=self.config
        )
        
        # Event handler
        self.event_handler = MeshEventHandler(
            blockchain=blockchain,
            mesh_manager=self.mesh_manager,
            state_manager=self.state_manager,
            mesh_logger=self.mesh_logger,
            validator=self.validator
        )
        
        # Registra handlers
        self._register_handlers()
        
        # Thread de sincronização
        self._sync_thread = None
        self.running = False
        
    def start(self) -> bool:
        """Inicia integração mesh"""
        try:
            # Valida configuração
            if not self.config.validate():
                logger.error("Configuração inválida")
                return False
                
            # Inicia LoRa
            if self.config.LORA_ENABLED:
                if not self.lora.start():
                    logger.error("Erro ao iniciar LoRa")
                    return False
                    
            # Inicia mesh manager
            if not self.mesh_manager.start():
                logger.error("Erro ao iniciar mesh manager")
                return False
                
            # Inicia thread de sincronização
            self.running = True
            self._sync_thread = threading.Thread(
                target=self._sync_loop
            )
            self._sync_thread.daemon = True
            self._sync_thread.start()
            
            logger.info("Integração mesh iniciada")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar integração: {e}")
            return False
            
    def stop(self):
        """Para integração mesh"""
        self.running = False
        self.mesh_manager.stop()
        self.lora.stop()
        
    def _register_handlers(self):
        """Registra handlers de eventos"""
        # Handler de transações
        self.lora.register_handler(
            "transaction",
            self._handle_transaction
        )
        
        # Handler de blocos
        self.lora.register_handler(
            "block",
            self._handle_block
        )
        
        # Handler de contratos
        self.lora.register_handler(
            "contract",
            self._handle_contract
        )
        
        # Handler de validações
        self.lora.register_handler(
            "validation",
            self._handle_validation
        )
        
        # Handler de sincronização
        self.lora.register_handler(
            "sync",
            self._handle_sync
        )
        
    def _handle_transaction(self, tx_data: Dict):
        """Processa transação recebida"""
        # Valida e adiciona ao mempool
        if self.event_handler.handle_event(
            EventType.TRANSACTION,
            tx_data
        ):
            # Se online, propaga para blockchain
            if self.blockchain.is_online():
                self.mempool.add_transaction(tx_data)
            else:
                # Se offline, armazena para sync posterior
                self.state_manager.add_pending_transaction(tx_data)
                
    def _handle_block(self, block_data: Dict):
        """Processa bloco recebido"""
        # Valida e adiciona à blockchain
        if self.event_handler.handle_event(
            EventType.BLOCK,
            block_data
        ):
            # Se online, adiciona direto
            if self.blockchain.is_online():
                self.blockchain.add_block(
                    block=Block.from_dict(block_data),
                    executor_address=block_data["node_id"],
                    network_addresses=block_data.get("validators", [])
                )
            else:
                # Se offline, armazena para sync posterior
                self.state_manager.add_pending_block(block_data)
                
    def _handle_contract(self, contract_data: Dict):
        """Processa contrato recebido"""
        # Valida e adiciona ao state manager
        if self.event_handler.handle_event(
            EventType.CONTRACT,
            contract_data
        ):
            # Se online, adiciona à blockchain
            if self.blockchain.is_online():
                self.blockchain.add_contract(contract_data)
            else:
                # Se offline, armazena para sync posterior
                self.state_manager.add_pending_contract(contract_data)
                
    def _handle_validation(self, validation_data: Dict):
        """Processa validação recebida"""
        # Adiciona ao state manager
        if self.event_handler.handle_event(
            EventType.VALIDATION,
            validation_data
        ):
            self.state_manager.add_validation(validation_data)
            
    def _handle_sync(self, sync_data: Dict):
        """Processa dados de sincronização"""
        # Atualiza estado
        if self.event_handler.handle_event(
            EventType.SYNC,
            sync_data
        ):
            self.state_manager.handle_sync(sync_data)
            
    def _sync_loop(self):
        """Loop de sincronização"""
        while self.running:
            try:
                # Verifica se está online
                if self.blockchain.is_online():
                    # Processa transações pendentes
                    pending_txs = self.state_manager.get_pending_transactions()
                    for tx in pending_txs:
                        self.mempool.add_transaction(tx)
                        
                    # Processa blocos pendentes
                    pending_blocks = self.state_manager.get_pending_blocks()
                    for block_data in pending_blocks:
                        self.blockchain.add_block(
                            block=Block.from_dict(block_data),
                            executor_address=block_data["node_id"],
                            network_addresses=block_data.get("validators", [])
                        )
                        
                    # Processa contratos pendentes
                    pending_contracts = self.state_manager.get_pending_contracts()
                    for contract in pending_contracts:
                        self.blockchain.add_contract(contract)
                        
                    # Limpa estados processados
                    self.state_manager.cleanup()
                    
                # Aguarda próximo ciclo
                time.sleep(self.config.SYNC_INTERVAL)
                
            except Exception as e:
                logger.error(f"Erro no loop de sync: {e}")
                time.sleep(10)
                
    def get_node_status(self, node_id: str) -> Optional[Dict]:
        """Retorna status do nó"""
        return self.mesh_manager.get_node_status(node_id)
        
    def get_pending_transactions(self) -> List[Dict]:
        """Retorna transações pendentes"""
        return self.state_manager.get_pending_transactions()
        
    def get_pending_blocks(self) -> List[Dict]:
        """Retorna blocos pendentes"""
        return self.state_manager.get_pending_blocks()
        
    def get_pending_contracts(self) -> List[Dict]:
        """Retorna contratos pendentes"""
        return self.state_manager.get_pending_contracts()
        
    def get_pending_validations(self) -> List[Dict]:
        """Retorna validações pendentes"""
        return self.state_manager.get_pending_validations()
        
    def get_network_status(self) -> Dict:
        """Retorna status da rede mesh"""
        return {
            "online": self.blockchain.is_online(),
            "lora_enabled": self.config.LORA_ENABLED,
            "lora_connected": self.lora.is_connected,
            "pending_txs": len(self.get_pending_transactions()),
            "pending_blocks": len(self.get_pending_blocks()),
            "pending_contracts": len(self.get_pending_contracts()),
            "pending_validations": len(self.get_pending_validations())
        } 