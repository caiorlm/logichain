"""
LogiChain - Sistema de blockchain para logística
"""

__version__ = "0.1.0"

from .network.nat_traversal import NATTraversal, NATInfo, NATType

__all__ = [
    'NATTraversal',
    'NATInfo',
    'NATType'
]

import logging
import asyncio
from typing import Optional
from .storage.init_db import init_db
from .core.block import Block
from .core.transaction import Transaction, TransactionPool
from .wallet.wallet import Wallet
from .security.security_manager import SecurityManager
from .network.p2p_network import P2PNetwork
from .consensus.hybrid_consensus import HybridConsensus
from .tokenomics import TokenConfig
from .network.gossip_protocol import GossipProtocol, MessageType, GossipMessage
from .network.sync_manager import SyncManager, SyncState, SyncSession
from .dag.dag_manager import DAGManager, DAGNode, NodeType
from .monitoring.metrics_collector import MetricsCollector
from .core.blockchain import Blockchain

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LogiChain:
    """
    Classe principal da LogiChain
    """
    
    _instance: Optional['LogiChain'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize LogiChain"""
        try:
            # Initialize components
            self.network = P2PNetwork()
            self.consensus = HybridConsensus(node_id="main-node")
            self.blockchain = Blockchain(
                db_path="data/blockchain/chain.db",
                node_id="main-node"
            )
            
            logger.info("LogiChain inicializada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar LogiChain: {str(e)}")
            raise
            
    def get_balance(self, address: str) -> float:
        """Get balance for an address"""
        return self.blockchain.get_balance(address)
        
    def get_blocks(self) -> list:
        """Get all blocks"""
        return self.blockchain.blocks
        
    def get_latest_block(self):
        """Get latest block"""
        return self.blockchain.get_latest_block()
        
    def add_block(self, block) -> bool:
        """Add a new block"""
        return self.blockchain.add_block(block)
    
    async def start(self):
        """Inicia todos os serviços da blockchain"""
        try:
            # Iniciar rede P2P
            await self.network.start()
            
            # Iniciar consenso
            await self.consensus.start()
            
            # Sincronizar com a rede
            await self.network.sync()
            
            logger.info("Todos os serviços iniciados com sucesso")
        except Exception as e:
            logger.error(f"Erro ao iniciar serviços: {e}")
            raise
            
    def run(self):
        """Run the blockchain in the current thread"""
        try:
            # Run the event loop
            self.loop.run_until_complete(self.start())
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
        except Exception as e:
            logger.error(f"Error running blockchain: {e}")
            self.stop()
            raise
            
    def stop(self):
        """Para todos os serviços da blockchain"""
        try:
            # Parar consenso
            if hasattr(self, 'consensus'):
                self.consensus.stop()
            
            # Parar rede P2P
            if hasattr(self, 'network'):
                self.network.stop()
            
            # Fechar conexão com banco de dados
            if hasattr(self, 'db_session'):
                self.db_session.close()
            
            # Stop event loop
            if hasattr(self, 'loop'):
                self.loop.stop()
            
            logger.info("Todos os serviços parados com sucesso")
        except Exception as e:
            logger.error(f"Erro ao parar serviços: {e}")
            # Don't raise here to ensure clean shutdown

# Initialize global instance
blockchain = LogiChain()

"""
LogiChain Blockchain Package
"""

__version__ = "0.1.0" 