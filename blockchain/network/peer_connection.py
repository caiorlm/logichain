"""
Classe que gerencia conexão com um peer
"""

import asyncio
import ssl
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

class PeerConnection:
    """Gerencia conexão com um peer"""
    
    def __init__(
        self,
        ip: str,
        port: int,
        ssl_context: Optional[ssl.SSLContext] = None,
        peer_id: Optional[str] = None
    ):
        """Inicializa conexão"""
        self.ip = ip
        self.port = port
        self.ssl_context = ssl_context
        self.peer_id = peer_id or f"{ip}:{port}"
        
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.last_seen = datetime.now()
        self.is_connected = False
        
    async def connect(self):
        """Estabelece conexão"""
        try:
            if self.ssl_context:
                self.reader, self.writer = await asyncio.open_connection(
                    self.ip,
                    self.port,
                    ssl=self.ssl_context
                )
            else:
                self.reader, self.writer = await asyncio.open_connection(
                    self.ip,
                    self.port
                )
                
            self.is_connected = True
            self.last_seen = datetime.now()
            
        except Exception as e:
            logging.error(f"Failed to connect to {self.peer_id}: {e}")
            raise
            
    async def disconnect(self):
        """Fecha conexão"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            
        self.reader = None
        self.writer = None
        self.is_connected = False
        
    async def send_data(self, data: bytes):
        """Envia dados"""
        if not self.is_connected:
            raise ConnectionError("Not connected")
            
        try:
            self.writer.write(data)
            await self.writer.drain()
            self.last_seen = datetime.now()
            
        except Exception as e:
            logging.error(f"Failed to send data to {self.peer_id}: {e}")
            await self.disconnect()
            raise
            
    async def receive_data(self, max_size: int = 1024 * 1024) -> bytes:
        """Recebe dados"""
        if not self.is_connected:
            raise ConnectionError("Not connected")
            
        try:
            data = await self.reader.read(max_size)
            if not data:
                raise ConnectionError("Connection closed")
                
            self.last_seen = datetime.now()
            return data
            
        except Exception as e:
            logging.error(f"Failed to receive data from {self.peer_id}: {e}")
            await self.disconnect()
            raise
            
    async def send_json(self, obj: Dict[str, Any]):
        """Envia objeto JSON"""
        data = json.dumps(obj).encode()
        await self.send_data(data)
        
    async def receive_json(self) -> Dict[str, Any]:
        """Recebe objeto JSON"""
        data = await self.receive_data()
        return json.loads(data)
        
    async def send_transaction(self, tx_data: bytes):
        """Envia transação"""
        message = {
            "type": "transaction",
            "data": tx_data.hex()
        }
        await self.send_json(message)
        
    async def send_block(self, block_data: bytes):
        """Envia bloco"""
        message = {
            "type": "block",
            "data": block_data.hex()
        }
        await self.send_json(message)
        
    def is_secure(self) -> bool:
        """Verifica se conexão é segura"""
        return bool(self.ssl_context)
        
    def is_authenticated(self) -> bool:
        """Verifica se peer está autenticado"""
        return bool(self.peer_id)
        
    @property
    def id(self) -> str:
        """ID único da conexão"""
        return self.peer_id 