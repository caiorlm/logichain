import asyncio
import hashlib
import json
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class MessageType(Enum):
    BLOCK = "block"
    TRANSACTION = "transaction"
    PEER_DISCOVERY = "peer_discovery"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    FALLBACK_REQUEST = "fallback_request"
    FALLBACK_RESPONSE = "fallback_response"
    ACK = "ack"

@dataclass
class GossipMessage:
    type: MessageType
    payload: dict
    sender: str
    timestamp: float
    message_id: str
    ttl: int = 3
    signature: Optional[str] = None
    
class GossipProtocol:
    def __init__(self, node_id: str, initial_peers: List[str] = None):
        self.node_id = node_id
        self.peers: Set[str] = set(initial_peers or [])
        self.seen_messages: Dict[str, float] = {}
        self.pending_acks: Dict[str, Set[str]] = {}
        self.message_cache: Dict[str, GossipMessage] = {}
        self.fallback_nodes: Set[str] = set()
        self._running = False
        self.sync_in_progress = False
        
    async def start(self):
        """Inicia o protocolo Gossip"""
        if self._running:
            return
            
        self._running = True
        asyncio.create_task(self._cleanup_seen_messages())
        asyncio.create_task(self._handle_pending_acks())
        
    async def stop(self):
        """Para o protocolo Gossip"""
        self._running = False
        
    def create_message(self, msg_type: MessageType, payload: dict) -> GossipMessage:
        """Cria uma nova mensagem Gossip"""
        timestamp = datetime.utcnow().timestamp()
        message_id = self._generate_message_id(payload, timestamp)
        
        return GossipMessage(
            type=msg_type,
            payload=payload,
            sender=self.node_id,
            timestamp=timestamp,
            message_id=message_id
        )
        
    async def broadcast(self, message: GossipMessage, require_ack: bool = True):
        """Transmite uma mensagem para a rede"""
        if not self._running:
            raise RuntimeError("Gossip protocol not running")
            
        # Registra a mensagem como vista
        self.seen_messages[message.message_id] = message.timestamp
        self.message_cache[message.message_id] = message
        
        if require_ack:
            self.pending_acks[message.message_id] = set(self.peers)
            
        # Transmite para todos os peers
        tasks = []
        for peer in self.peers:
            task = asyncio.create_task(self._send_to_peer(peer, message))
            tasks.append(task)
            
        # Aguarda todas as transmissões
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Se precisar de ACK, aguarda confirmações
        if require_ack:
            await self._wait_for_acks(message.message_id)
            
    async def _send_to_peer(self, peer: str, message: GossipMessage):
        """Envia uma mensagem para um peer específico"""
        try:
            # Aqui seria a implementação real do envio
            # Usando o socket ou conexão apropriada
            pass
            
        except Exception as e:
            logger.error(f"Failed to send to peer {peer}: {e}")
            if message.type in [MessageType.BLOCK, MessageType.TRANSACTION]:
                await self._handle_transmission_failure(message, peer)
                
    async def _handle_transmission_failure(self, message: GossipMessage, failed_peer: str):
        """Lida com falhas de transmissão usando fallback"""
        if not self.fallback_nodes:
            logger.error("No fallback nodes available")
            return
            
        # Cria mensagem de fallback
        fallback_msg = self.create_message(
            MessageType.FALLBACK_REQUEST,
            {
                "original_message_id": message.message_id,
                "failed_peer": failed_peer,
                "retry_count": 0
            }
        )
        
        # Envia para nós de fallback
        for node in self.fallback_nodes:
            try:
                await self._send_to_peer(node, fallback_msg)
            except Exception as e:
                logger.error(f"Fallback transmission failed to {node}: {e}")
                
    async def handle_message(self, message: GossipMessage, sender: str):
        """Processa uma mensagem recebida"""
        # Verifica se já viu a mensagem
        if message.message_id in self.seen_messages:
            return
            
        # Registra a mensagem
        self.seen_messages[message.message_id] = message.timestamp
        self.message_cache[message.message_id] = message
        
        # Processa baseado no tipo
        if message.type == MessageType.SYNC_REQUEST:
            await self._handle_sync_request(message, sender)
        elif message.type == MessageType.FALLBACK_REQUEST:
            await self._handle_fallback_request(message, sender)
        elif message.type == MessageType.ACK:
            await self._handle_ack(message)
        else:
            # Propaga para outros peers se TTL > 0
            if message.ttl > 0:
                message.ttl -= 1
                await self.broadcast(message, require_ack=False)
                
        # Envia ACK
        ack_msg = self.create_message(
            MessageType.ACK,
            {"original_message_id": message.message_id}
        )
        await self._send_to_peer(sender, ack_msg)
        
    async def _handle_sync_request(self, message: GossipMessage, sender: str):
        """Processa pedido de sincronização"""
        if self.sync_in_progress:
            return
            
        self.sync_in_progress = True
        try:
            missing_blocks = message.payload.get("missing_blocks", [])
            response_data = {
                "blocks": {},
                "request_id": message.message_id
            }
            
            # Recupera os blocos solicitados
            for block_hash in missing_blocks:
                if block_hash in self.message_cache:
                    response_data["blocks"][block_hash] = self.message_cache[block_hash].payload
                    
            # Envia resposta
            response = self.create_message(
                MessageType.SYNC_RESPONSE,
                response_data
            )
            await self._send_to_peer(sender, response)
            
        finally:
            self.sync_in_progress = False
            
    async def _handle_fallback_request(self, message: GossipMessage, sender: str):
        """Processa pedido de fallback"""
        original_msg_id = message.payload["original_message_id"]
        failed_peer = message.payload["failed_peer"]
        
        if original_msg_id in self.message_cache:
            original_msg = self.message_cache[original_msg_id]
            try:
                # Tenta retransmitir para o peer que falhou
                await self._send_to_peer(failed_peer, original_msg)
            except Exception as e:
                logger.error(f"Fallback transmission failed: {e}")
                
    async def _handle_ack(self, message: GossipMessage):
        """Processa confirmação de recebimento"""
        original_msg_id = message.payload["original_message_id"]
        if original_msg_id in self.pending_acks:
            self.pending_acks[original_msg_id].remove(message.sender)
            
    async def _wait_for_acks(self, message_id: str, timeout: float = 5.0):
        """Aguarda confirmações de recebimento"""
        start_time = datetime.utcnow()
        while (datetime.utcnow() - start_time) < timedelta(seconds=timeout):
            if not self.pending_acks.get(message_id):
                return True
            await asyncio.sleep(0.1)
            
        # Timeout - inicia processo de fallback
        missing_acks = self.pending_acks.get(message_id, set())
        if missing_acks and message_id in self.message_cache:
            original_msg = self.message_cache[message_id]
            for peer in missing_acks:
                await self._handle_transmission_failure(original_msg, peer)
                
        return False
        
    async def _cleanup_seen_messages(self):
        """Limpa mensagens antigas do cache"""
        while self._running:
            now = datetime.utcnow().timestamp()
            expired = [
                msg_id for msg_id, timestamp in self.seen_messages.items()
                if now - timestamp > 3600  # 1 hora
            ]
            for msg_id in expired:
                del self.seen_messages[msg_id]
                self.message_cache.pop(msg_id, None)
            await asyncio.sleep(300)  # Limpa a cada 5 minutos
            
    async def _handle_pending_acks(self):
        """Monitora e lida com ACKs pendentes"""
        while self._running:
            now = datetime.utcnow().timestamp()
            for msg_id, peers in list(self.pending_acks.items()):
                if not peers:  # Todos confirmaram
                    del self.pending_acks[msg_id]
                elif msg_id in self.message_cache:
                    msg_timestamp = self.message_cache[msg_id].timestamp
                    if now - msg_timestamp > 30:  # 30 segundos timeout
                        # Inicia fallback para peers que não confirmaram
                        original_msg = self.message_cache[msg_id]
                        for peer in peers:
                            await self._handle_transmission_failure(original_msg, peer)
                        del self.pending_acks[msg_id]
            await asyncio.sleep(1)
            
    def _generate_message_id(self, payload: dict, timestamp: float) -> str:
        """Gera ID único para a mensagem"""
        data = f"{json.dumps(payload)}{timestamp}{self.node_id}"
        return hashlib.sha256(data.encode()).hexdigest()
        
    def register_fallback_node(self, node_id: str):
        """Registra um nó como fallback"""
        self.fallback_nodes.add(node_id)
        
    def unregister_fallback_node(self, node_id: str):
        """Remove um nó da lista de fallback"""
        self.fallback_nodes.discard(node_id) 