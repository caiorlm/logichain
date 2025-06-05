from typing import Optional, List, Dict
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConsensusType(Enum):
    POW = "pow"
    BFT = "bft"
    HYBRID = "hybrid"

class ConsensusState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class ConsensusManager:
    def __init__(self, node_id: str, consensus_type: ConsensusType = ConsensusType.HYBRID):
        self.node_id = node_id
        self.consensus_type = consensus_type
        self.state = ConsensusState.IDLE
        self._running = False
        
    async def start(self):
        """Inicia o gerenciador de consenso"""
        if self._running:
            return
            
        self._running = True
        self.state = ConsensusState.RUNNING
        logger.info(f"Consensus manager started with type {self.consensus_type}")
        
    async def stop(self):
        """Para o gerenciador de consenso"""
        self._running = False
        self.state = ConsensusState.STOPPED
        logger.info("Consensus manager stopped")
        
    def get_state(self) -> ConsensusState:
        """Retorna estado atual do consenso"""
        return self.state 