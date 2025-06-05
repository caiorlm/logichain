"""
Implementação base da rede P2P
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class PeerInfo:
    host: str
    port: int
    node_type: str
    last_seen: float

class NetworkNode:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.peers: Dict[str, PeerInfo] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setup_logging()
        self.server = None
        self.is_running = False

    def setup_logging(self):
        """Configura logging básico"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    async def broadcast_message(self, message: Dict):
        """
        Envia mensagem para todos os peers
        """
        if not self.is_running:
            return

        message.update({
            'sender_host': self.host,
            'sender_port': self.port,
            'timestamp': asyncio.get_event_loop().time()
        })

        for peer in self.peers.values():
            try:
                reader, writer = await asyncio.open_connection(
                    peer.host, 
                    peer.port
                )
                
                writer.write(json.dumps(message).encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                
            except Exception as e:
                self.logger.error(f"Erro ao enviar para {peer.host}:{peer.port} - {e}")

    def add_peer(self, peer: PeerInfo):
        """
        Adiciona novo peer à rede
        """
        peer_id = f"{peer.host}:{peer.port}"
        self.peers[peer_id] = peer
        self.logger.info(f"Novo peer adicionado: {peer_id}")

    def remove_peer(self, host: str, port: int):
        """
        Remove peer da rede
        """
        peer_id = f"{host}:{port}"
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.logger.info(f"Peer removido: {peer_id}")

    async def handle_message(self, message: Dict):
        """
        Processa mensagem recebida
        Base para implementação específica em cada tipo de nó
        """
        if message.get('type') == 'peer_discovery':
            # Atualiza lista de peers
            peer = PeerInfo(
                host=message['sender_host'],
                port=message['sender_port'],
                node_type=message.get('node_type', 'unknown'),
                last_seen=message['timestamp']
            )
            self.add_peer(peer)

    async def start(self):
        """
        Inicia servidor de rede
        """
        if self.is_running:
            return

        self.is_running = True
        self.server = await asyncio.start_server(
            self.handle_connection, 
            self.host, 
            self.port
        )
        
        self.logger.info(f"Servidor iniciado em {self.host}:{self.port}")
        
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """
        Para o servidor de rede
        """
        if not self.is_running:
            return

        self.is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        
        self.logger.info(f"Servidor encerrado em {self.host}:{self.port}")

    async def handle_connection(self, reader, writer):
        """
        Processa conexão recebida
        """
        if not self.is_running:
            writer.close()
            await writer.wait_closed()
            return

        try:
            data = await reader.read()
            message = json.loads(data.decode())
            await self.handle_message(message)
            
        except Exception as e:
            self.logger.error(f"Erro ao processar conexão: {e}")
            
        finally:
            writer.close()
            await writer.wait_closed() 