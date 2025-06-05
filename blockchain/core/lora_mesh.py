"""
LogiChain LoRa Mesh
Handles LoRa-based mesh communication for offline operations
"""

import time
import json
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import threading
from queue import Queue

class LoRaMode(Enum):
    BROADCAST = "broadcast"
    DIRECT = "direct"
    MESH = "mesh"

@dataclass
class LoRaConfig:
    """LoRa communication configuration"""
    frequency: int      # MHz
    bandwidth: int      # kHz
    coding_rate: int   # 4/5-4/8
    spreading_factor: int
    tx_power: int      # dBm
    max_packet: int    # bytes

@dataclass
class LoRaMessage:
    """Message for LoRa transmission"""
    msg_type: str
    data: Dict
    timestamp: float
    source: str
    target: Optional[str] = None
    hop_count: int = 0

class LoraMesh:
    """Manages LoRa mesh communication"""
    
    def __init__(
        self,
        node_id: str,
        lora_config: Optional[LoRaConfig] = None
    ):
        self.node_id = node_id
        
        # Default LoRa config for mesh
        self.config = lora_config or LoRaConfig(
            frequency=915,    # 915 MHz
            bandwidth=125,    # 125 kHz
            coding_rate=5,    # 4/5
            spreading_factor=7,
            tx_power=14,      # 14 dBm
            max_packet=255    # 255 bytes max
        )
        
        # Message queues
        self.tx_queue = Queue()
        self.rx_queue = Queue()
        
        # Known mesh nodes
        self.mesh_nodes: Dict[str, float] = {}  # node_id -> last_seen
        
        # Start LoRa threads
        self._init_lora()
        
    def _init_lora(self):
        """Initialize LoRa communication"""
        # Start receiver thread
        self.rx_thread = threading.Thread(
            target=self._run_receiver,
            daemon=True
        )
        self.rx_thread.start()
        
        # Start transmitter thread
        self.tx_thread = threading.Thread(
            target=self._run_transmitter,
            daemon=True
        )
        self.tx_thread.start()
        
        # Start mesh maintenance thread
        self.mesh_thread = threading.Thread(
            target=self._run_mesh_maintenance,
            daemon=True
        )
        self.mesh_thread.start()
        
    def _run_receiver(self):
        """Run LoRa receiver"""
        while True:
            try:
                # Simulate LoRa reception
                # In real implementation, this would use actual LoRa hardware
                time.sleep(0.1)  # Simulate reception delay
                
            except Exception:
                continue
                
    def _run_transmitter(self):
        """Run LoRa transmitter"""
        while True:
            try:
                # Get next message from queue
                message = self.tx_queue.get()
                
                # Prepare packet
                packet = self._prepare_packet(message)
                
                if len(packet) > self.config.max_packet:
                    # Split into multiple packets if needed
                    chunks = self._split_packet(packet)
                    for chunk in chunks:
                        # Simulate LoRa transmission
                        # In real implementation, this would use actual LoRa hardware
                        time.sleep(0.2)  # Simulate transmission delay
                else:
                    # Simulate single packet transmission
                    time.sleep(0.2)
                    
            except Exception:
                continue
                
    def _run_mesh_maintenance(self):
        """Maintain mesh network"""
        while True:
            try:
                # Broadcast presence
                self.broadcast_message({
                    "type": "mesh_presence",
                    "node_id": self.node_id
                })
                
                # Clean old nodes
                current_time = time.time()
                expired = [
                    node_id
                    for node_id, last_seen in self.mesh_nodes.items()
                    if current_time - last_seen > 300  # 5 minutes timeout
                ]
                
                for node_id in expired:
                    del self.mesh_nodes[node_id]
                    
                # Wait before next maintenance
                time.sleep(60)  # 1 minute interval
                
            except Exception:
                time.sleep(60)
                continue
                
    def broadcast_message(self, data: Dict) -> bool:
        """Broadcast message to all mesh nodes"""
        try:
            message = LoRaMessage(
                msg_type="broadcast",
                data=data,
                timestamp=time.time(),
                source=self.node_id
            )
            
            self.tx_queue.put(message)
            return True
            
        except Exception:
            return False
            
    def send_direct_message(
        self,
        target: str,
        data: Dict
    ) -> bool:
        """Send message directly to specific node"""
        try:
            message = LoRaMessage(
                msg_type="direct",
                data=data,
                timestamp=time.time(),
                source=self.node_id,
                target=target
            )
            
            self.tx_queue.put(message)
            return True
            
        except Exception:
            return False
            
    def send_mesh_message(
        self,
        data: Dict,
        max_hops: int = 3
    ) -> bool:
        """Send message through mesh network"""
        try:
            message = LoRaMessage(
                msg_type="mesh",
                data=data,
                timestamp=time.time(),
                source=self.node_id,
                hop_count=0
            )
            
            self.tx_queue.put(message)
            return True
            
        except Exception:
            return False
            
    def _prepare_packet(self, message: LoRaMessage) -> bytes:
        """Prepare message for LoRa transmission"""
        try:
            # Convert message to dict
            packet_data = {
                "type": message.msg_type,
                "data": message.data,
                "timestamp": message.timestamp,
                "source": message.source,
                "target": message.target,
                "hop_count": message.hop_count
            }
            
            # Convert to bytes
            return json.dumps(packet_data).encode()
            
        except Exception:
            return b""
            
    def _split_packet(self, packet: bytes) -> List[bytes]:
        """Split large packet into LoRa-sized chunks"""
        chunks = []
        max_chunk = self.config.max_packet - 20  # Header overhead
        
        for i in range(0, len(packet), max_chunk):
            chunk = packet[i:i + max_chunk]
            chunks.append(chunk)
            
        return chunks
        
    def get_mesh_nodes(self) -> Dict[str, float]:
        """Get currently known mesh nodes"""
        return self.mesh_nodes.copy()
        
    def estimate_bandwidth(self) -> int:
        """Estimate available bandwidth in bytes/second"""
        # Basic LoRa bandwidth estimation
        # SF7, 125kHz BW, CR 4/5
        symbol_rate = self.config.bandwidth / (2 ** self.config.spreading_factor)
        coding_rate = 4.0 / self.config.coding_rate
        
        bits_per_second = symbol_rate * self.config.spreading_factor * coding_rate
        bytes_per_second = int(bits_per_second / 8)
        
        return bytes_per_second 