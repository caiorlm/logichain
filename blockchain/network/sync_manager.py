import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .gossip_protocol import GossipProtocol, MessageType, GossipMessage
from ..dag.dag_manager import DAGManager, DAGNode

logger = logging.getLogger(__name__)

class SyncState(Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    VALIDATING = "validating"
    ERROR = "error"

@dataclass
class SyncSession:
    peer_id: str
    start_time: float
    last_activity: float
    missing_blocks: Set[str]
    received_blocks: Dict[str, DAGNode]
    state: SyncState
    retries: int = 0
    
class SyncManager:
    def __init__(
        self,
        node_id: str,
        dag_manager: DAGManager,
        gossip: GossipProtocol,
        sync_interval: int = 300,  # 5 minutos
        max_retries: int = 3,
        timeout: int = 30  # 30 segundos
    ):
        self.node_id = node_id
        self.dag_manager = dag_manager
        self.gossip = gossip
        self.sync_interval = sync_interval
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.active_sessions: Dict[str, SyncSession] = {}
        self.sync_state = SyncState.IDLE
        self._running = False
        
    async def start(self):
        """Inicia o gerenciador de sincronização"""
        if self._running:
            return
            
        self._running = True
        asyncio.create_task(self._periodic_sync())
        asyncio.create_task(self._monitor_sessions())
        
    async def stop(self):
        """Para o gerenciador de sincronização"""
        self._running = False
        
    async def _periodic_sync(self):
        """Executa sincronização periódica"""
        while self._running:
            try:
                await self.sync_with_network()
            except Exception as e:
                logger.error(f"Periodic sync failed: {e}")
            await asyncio.sleep(self.sync_interval)
            
    async def sync_with_network(self):
        """Sincroniza com a rede"""
        if self.sync_state != SyncState.IDLE:
            logger.warning("Sync already in progress")
            return
            
        self.sync_state = SyncState.SYNCING
        try:
            # Solicita tips dos peers
            tips_request = self.gossip.create_message(
                MessageType.SYNC_REQUEST,
                {"request_type": "get_tips"}
            )
            await self.gossip.broadcast(tips_request)
            
            # Aguarda respostas
            await asyncio.sleep(5)  # Tempo para respostas
            
            # Processa respostas e identifica blocos faltantes
            missing_blocks = await self._identify_missing_blocks()
            
            if missing_blocks:
                await self._request_missing_blocks(missing_blocks)
                
        except Exception as e:
            logger.error(f"Network sync failed: {e}")
            self.sync_state = SyncState.ERROR
        finally:
            self.sync_state = SyncState.IDLE
            
    async def _identify_missing_blocks(self) -> Set[str]:
        """Identifica blocos faltantes comparando com peers"""
        missing = set()
        local_tips = {tip.node_id for tip in self.dag_manager.get_tips()}
        
        for session in self.active_sessions.values():
            for block_id in session.received_blocks:
                if block_id not in local_tips:
                    missing.add(block_id)
                    
        return missing
        
    async def _request_missing_blocks(self, missing_blocks: Set[str]):
        """Solicita blocos faltantes dos peers"""
        if not missing_blocks:
            return
            
        # Cria sessões de sync para cada peer
        for peer_id in self.gossip.peers:
            session = SyncSession(
                peer_id=peer_id,
                start_time=datetime.utcnow().timestamp(),
                last_activity=datetime.utcnow().timestamp(),
                missing_blocks=missing_blocks.copy(),
                received_blocks={},
                state=SyncState.SYNCING
            )
            self.active_sessions[peer_id] = session
            
            # Envia solicitação
            request = self.gossip.create_message(
                MessageType.SYNC_REQUEST,
                {
                    "missing_blocks": list(missing_blocks),
                    "session_id": f"{self.node_id}_{peer_id}_{session.start_time}"
                }
            )
            await self.gossip.broadcast(request, require_ack=True)
            
    async def handle_sync_response(self, message: GossipMessage, sender: str):
        """Processa resposta de sincronização"""
        if sender not in self.active_sessions:
            logger.warning(f"Received sync response from unknown peer: {sender}")
            return
            
        session = self.active_sessions[sender]
        session.last_activity = datetime.utcnow().timestamp()
        
        # Processa blocos recebidos
        blocks_data = message.payload.get("blocks", {})
        for block_id, block_data in blocks_data.items():
            if block_id in session.missing_blocks:
                # Cria nó DAG
                node = DAGNode(
                    node_id=block_id,
                    node_type=block_data["type"],
                    parents=block_data["parents"],
                    timestamp=block_data["timestamp"],
                    data=block_data["data"],
                    signature=block_data["signature"]
                )
                
                # Valida e adiciona ao DAG
                if self.dag_manager.add_node(node):
                    session.received_blocks[block_id] = node
                    session.missing_blocks.remove(block_id)
                    
        # Verifica se completou
        if not session.missing_blocks:
            session.state = SyncState.IDLE
            await self._complete_session(sender)
        else:
            # Tenta novamente se necessário
            if session.retries < self.max_retries:
                session.retries += 1
                await self._retry_missing_blocks(session)
            else:
                logger.warning(f"Sync failed with peer {sender} after {self.max_retries} retries")
                await self._complete_session(sender)
                
    async def _retry_missing_blocks(self, session: SyncSession):
        """Tenta novamente blocos faltantes"""
        request = self.gossip.create_message(
            MessageType.SYNC_REQUEST,
            {
                "missing_blocks": list(session.missing_blocks),
                "session_id": f"{self.node_id}_{session.peer_id}_{session.start_time}",
                "retry": session.retries
            }
        )
        await self.gossip.broadcast(request, require_ack=True)
        
    async def _complete_session(self, peer_id: str):
        """Finaliza uma sessão de sincronização"""
        if peer_id in self.active_sessions:
            session = self.active_sessions[peer_id]
            
            # Envia ACK final
            ack = self.gossip.create_message(
                MessageType.ACK,
                {
                    "session_id": f"{self.node_id}_{peer_id}_{session.start_time}",
                    "received_blocks": list(session.received_blocks.keys())
                }
            )
            await self.gossip.broadcast(ack, require_ack=True)
            
            del self.active_sessions[peer_id]
            
    async def _monitor_sessions(self):
        """Monitora sessões ativas para timeout"""
        while self._running:
            now = datetime.utcnow().timestamp()
            
            for peer_id, session in list(self.active_sessions.items()):
                # Verifica timeout
                if now - session.last_activity > self.timeout:
                    if session.retries < self.max_retries:
                        # Tenta novamente
                        session.retries += 1
                        await self._retry_missing_blocks(session)
                    else:
                        # Desiste após máximo de tentativas
                        logger.warning(f"Session with {peer_id} timed out")
                        await self._complete_session(peer_id)
                        
            await asyncio.sleep(1)  # Checa a cada segundo
            
    def get_sync_status(self) -> Dict:
        """Retorna status atual da sincronização"""
        return {
            "state": self.sync_state.value,
            "active_sessions": len(self.active_sessions),
            "total_missing_blocks": sum(
                len(s.missing_blocks) for s in self.active_sessions.values()
            ),
            "total_received_blocks": sum(
                len(s.received_blocks) for s in self.active_sessions.values()
            )
        } 