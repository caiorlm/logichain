"""
LogiChain LoRa Manager
Gerencia comunicação LoRa para operação offline
"""

import time
import json
import logging
import threading
from typing import Dict, Optional, List, Callable
from serial import Serial
from ..core.blockchain import Blockchain
from ..security import SecurityManager

logger = logging.getLogger(__name__)

class LoRaManager:
    """Gerencia comunicação LoRa"""
    
    def __init__(
        self,
        node_id: str,
        port: Optional[str] = None,
        frequency: int = 915000000,  # 915MHz
        bandwidth: int = 125000,  # 125kHz
        spreading_factor: int = 7,
        coding_rate: int = 5,
        power_level: int = 20,  # dBm
        sync_word: int = 0x12
    ):
        self.node_id = node_id
        self.port = port
        self.frequency = frequency
        self.bandwidth = bandwidth
        self.spreading_factor = spreading_factor
        self.coding_rate = coding_rate
        self.power_level = power_level
        self.sync_word = sync_word
        
        self.serial = None
        self.running = False
        self.security = SecurityManager()
        
        # Callbacks para processamento de mensagens
        self._message_handlers: Dict[str, List[Callable]] = {}
        
        # Lock para thread safety
        self._lock = threading.Lock()
        
    def start(self) -> bool:
        """Inicia comunicação LoRa"""
        try:
            if self.port:
                self.serial = Serial(
                    port=self.port,
                    baudrate=57600,
                    timeout=1
                )
                
                # Configura rádio
                self._configure_radio()
            
            self.running = True
            
            # Inicia thread de recebimento
            self._receive_thread = threading.Thread(
                target=self._receive_loop
            )
            self._receive_thread.daemon = True
            self._receive_thread.start()
            
            logger.info(f"LoRa iniciado: {self.node_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar LoRa: {e}")
            return False
            
    def stop(self):
        """Para comunicação LoRa"""
        self.running = False
        if self.serial:
            self.serial.close()
            
    def send_data(self, data: Dict) -> bool:
        """Envia dados via LoRa"""
        try:
            # Adiciona metadados
            message = {
                "node_id": self.node_id,
                "timestamp": time.time(),
                "data": data
            }
            
            # Assina mensagem
            message["signature"] = self.security.sign_data(message)
            
            # Serializa
            payload = json.dumps(message)
            
            with self._lock:
                if self.serial:
                    # Envia via serial
                    self.serial.write(payload.encode())
                else:
                    # Modo simulação
                    logger.info(f"Simulando envio: {payload}")
                    
                return True
                
        except Exception as e:
            logger.error(f"Erro ao enviar dados: {e}")
            return False
            
    def register_handler(
        self,
        message_type: str,
        handler: Callable
    ):
        """Registra handler para tipo de mensagem"""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
        
    def _configure_radio(self):
        """Configura parâmetros do rádio LoRa"""
        if not self.serial:
            return
            
        # Configura frequência
        self.serial.write(f"AT+FREQ={self.frequency}\r\n".encode())
        
        # Configura bandwidth
        self.serial.write(f"AT+BW={self.bandwidth}\r\n".encode())
        
        # Configura spreading factor
        self.serial.write(f"AT+SF={self.spreading_factor}\r\n".encode())
        
        # Configura coding rate
        self.serial.write(f"AT+CR={self.coding_rate}\r\n".encode())
        
        # Configura potência
        self.serial.write(f"AT+POWER={self.power_level}\r\n".encode())
        
        # Configura sync word
        self.serial.write(f"AT+SYNC={self.sync_word}\r\n".encode())
        
    def _receive_loop(self):
        """Loop de recebimento de mensagens"""
        while self.running:
            try:
                if self.serial:
                    # Lê da serial
                    if self.serial.in_waiting:
                        data = self.serial.readline().decode().strip()
                        self._handle_message(data)
                else:
                    # Modo simulação
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Erro no loop de recebimento: {e}")
                
    def _handle_message(self, raw_data: str):
        """Processa mensagem recebida"""
        try:
            # Decodifica JSON
            message = json.loads(raw_data)
            
            # Valida assinatura
            if not self.security.verify_signature(
                message,
                message.pop("signature", None)
            ):
                logger.warning("Assinatura inválida")
                return
                
            # Extrai dados
            node_id = message.get("node_id")
            timestamp = message.get("timestamp")
            data = message.get("data", {})
            
            # Determina tipo
            message_type = data.get("type", "unknown")
            
            # Chama handlers registrados
            handlers = self._message_handlers.get(message_type, [])
            for handler in handlers:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Erro no handler: {e}")
                    
        except json.JSONDecodeError:
            logger.error("Mensagem inválida")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            
    @property
    def is_connected(self) -> bool:
        """Verifica se está conectado"""
        return bool(self.serial and self.serial.is_open if self.serial else self.running) 