import socket
import asyncio
import stun
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class NATType(Enum):
    UNKNOWN = "Unknown"
    OPEN_INTERNET = "Open Internet"
    FULL_CONE = "Full Cone"
    RESTRICTED_CONE = "Restricted Cone"
    PORT_RESTRICTED = "Port Restricted"
    SYMMETRIC = "Symmetric"
    BLOCKED = "Blocked"

@dataclass
class NATInfo:
    nat_type: NATType
    external_ip: str
    external_port: int
    local_ip: str
    local_port: int
    stun_server: str

class NATTraversal:
    def __init__(self, stun_servers: List[str] = None):
        self.stun_servers = stun_servers or [
            'stun.l.google.com:19302',
            'stun1.l.google.com:19302',
            'stun2.l.google.com:19302'
        ]
        self.nat_info: Optional[NATInfo] = None
        self.hole_punch_ports: List[int] = []
        self.peers: Dict[str, NATInfo] = {}
        self._running = False
        self._punch_sockets: Dict[str, socket.socket] = {}
        
    async def start(self):
        """Inicia o serviço de NAT Traversal"""
        if self._running:
            return
        
        self._running = True
        await self._discover_nat_type()
        await self._start_hole_punching()
        
    async def stop(self):
        """Para o serviço de NAT Traversal"""
        self._running = False
        for sock in self._punch_sockets.values():
            sock.close()
        self._punch_sockets.clear()
        
    async def _discover_nat_type(self) -> NATInfo:
        """Descobre o tipo de NAT e informações externas"""
        for stun_server in self.stun_servers:
            try:
                host, port = stun_server.split(':')
                nat_type, external_ip, external_port = stun.get_ip_info(
                    source_ip="0.0.0.0",
                    source_port=0,
                    stun_host=host,
                    stun_port=int(port)
                )
                
                local_ip = socket.gethostbyname(socket.gethostname())
                local_port = external_port  # Pode ser diferente em alguns casos
                
                self.nat_info = NATInfo(
                    nat_type=NATType(nat_type),
                    external_ip=external_ip,
                    external_port=external_port,
                    local_ip=local_ip,
                    local_port=local_port,
                    stun_server=stun_server
                )
                return self.nat_info
                
            except Exception as e:
                logger.error(f"STUN request failed for {stun_server}: {e}")
                continue
                
        raise Exception("Failed to discover NAT type using all STUN servers")
        
    async def _start_hole_punching(self):
        """Inicia o processo de hole punching"""
        if not self.nat_info:
            raise Exception("NAT info not discovered")
            
        base_port = self.nat_info.external_port
        for offset in range(5):  # Tenta 5 portas diferentes
            port = base_port + offset
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', port))
            sock.setblocking(False)
            self._punch_sockets[str(port)] = sock
            self.hole_punch_ports.append(port)
            
        asyncio.create_task(self._maintain_holes())
        
    async def _maintain_holes(self):
        """Mantém os holes abertos enviando keep-alives"""
        while self._running:
            for port, sock in self._punch_sockets.items():
                try:
                    # Envia keep-alive para cada peer conhecido
                    for peer_info in self.peers.values():
                        sock.sendto(b'keep-alive', (peer_info.external_ip, peer_info.external_port))
                except Exception as e:
                    logger.error(f"Keep-alive failed for port {port}: {e}")
            await asyncio.sleep(30)  # Keep-alive a cada 30 segundos
            
    async def register_peer(self, peer_id: str, peer_info: NATInfo):
        """Registra um novo peer para hole punching"""
        self.peers[peer_id] = peer_info
        
    async def connect_to_peer(self, peer_id: str) -> Optional[socket.socket]:
        """Tenta estabelecer conexão com um peer específico"""
        if peer_id not in self.peers:
            raise ValueError(f"Unknown peer {peer_id}")
            
        peer_info = self.peers[peer_id]
        
        # Tenta todas as portas disponíveis
        for port in self.hole_punch_ports:
            sock = self._punch_sockets[str(port)]
            try:
                # Envia pacote de inicialização
                sock.sendto(b'init', (peer_info.external_ip, peer_info.external_port))
                
                # Espera resposta
                data, addr = await self._async_recvfrom(sock)
                if data == b'init-ack':
                    logger.info(f"Connection established with {peer_id} on port {port}")
                    return sock
                    
            except Exception as e:
                logger.error(f"Connection attempt failed on port {port}: {e}")
                
        return None
        
    async def _async_recvfrom(self, sock: socket.socket, timeout: float = 5.0) -> Tuple[bytes, Tuple[str, int]]:
        """Wrapper assíncrono para socket.recvfrom"""
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        def callback():
            try:
                data, addr = sock.recvfrom(1024)
                future.set_result((data, addr))
            except Exception as e:
                future.set_exception(e)
                
        loop.add_reader(sock.fileno(), callback)
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            loop.remove_reader(sock.fileno()) 