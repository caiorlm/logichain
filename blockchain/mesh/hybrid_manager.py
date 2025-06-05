"""
LogiChain Hybrid Mesh Manager
Manages both online and offline mesh communication
"""

import time
import json
import logging
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from ..core.blockchain import Blockchain
from .config_offline_mesh import OfflineMeshConfig
from .lora import LoRaManager, MessageType
from .sync_manager import SyncManager
from .mesh_logger import MeshLogger

logger = logging.getLogger(__name__)

class NodeStatus(Enum):
    """Node connection status"""
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    BRIDGE = "bridge"

@dataclass
class MeshNode:
    """Mesh network node"""
    node_id: str
    status: NodeStatus
    last_seen: int
    stake: float
    location: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "stake": self.stake,
            "location": self.location
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MeshNode":
        """Create from dictionary"""
        return cls(
            node_id=data["node_id"],
            status=NodeStatus(data["status"]),
            last_seen=data["last_seen"],
            stake=data["stake"],
            location=data["location"]
        )

class HybridMeshManager:
    """Hybrid mesh network manager"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        lora: LoRaManager,
        config: OfflineMeshConfig
    ):
        self.blockchain = blockchain
        self.lora = lora
        self.config = config
        self.running = False
        
        # Node state
        self.nodes: Dict[str, MeshNode] = {}
        self.bridge_nodes: Set[str] = set()
        self.pending_sync: Set[str] = set()
        
        # Initialize managers
        self.sync_manager = SyncManager(blockchain, self)
        self.mesh_logger = MeshLogger()
        
        # Message handlers
        self.message_handlers = {
            MessageType.HANDSHAKE: self._handle_handshake,
            MessageType.CONTRACT: self._handle_contract,
            MessageType.VALIDATION: self._handle_validation,
            MessageType.SYNC: self.sync_manager._handle_sync_message
        }
        
        # Locks
        self._node_lock = threading.Lock()
        self._sync_lock = threading.Lock()
        
    def start(self) -> bool:
        """Start hybrid manager"""
        try:
            # Register message handler
            self.lora.register_handler(self._handle_message)
            
            # Start sync manager
            self.sync_manager.start()
            
            # Start background tasks
            self.running = True
            threading.Thread(
                target=self._discovery_loop,
                daemon=True
            ).start()
            threading.Thread(
                target=self._cleanup_loop,
                daemon=True
            ).start()
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="startup",
                status="success",
                details={
                    "is_bridge": self.config.is_bridge,
                    "is_online": self.blockchain.is_online()
                }
            )
            
            logger.info("Hybrid mesh manager started")
            return True
            
        except Exception as e:
            error_msg = f"Failed to start manager: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="startup_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
            self.stop()
            return False
            
    def stop(self):
        """Stop hybrid manager"""
        try:
            self.running = False
            self.sync_manager.stop()
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="shutdown",
                status="success"
            )
            
            logger.info("Hybrid mesh manager stopped")
            
        except Exception as e:
            error_msg = f"Error stopping manager: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="shutdown_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def get_nodes(self) -> List[Dict]:
        """Get all known nodes"""
        return [node.to_dict() for node in self.nodes.values()]
        
    def get_bridge_nodes(self) -> List[Dict]:
        """Get bridge nodes"""
        return [
            node.to_dict()
            for node_id, node in self.nodes.items()
            if node_id in self.bridge_nodes
        ]
        
    def broadcast_contract(self, contract_data: Dict) -> bool:
        """Broadcast contract to mesh network"""
        try:
            # Send contract message
            self.lora.send_message(
                type=MessageType.CONTRACT,
                data=contract_data
            )
            
            self.mesh_logger.log_contract_event(
                contract_id=contract_data["contract_id"],
                event_type="broadcast",
                status="success",
                node_id=self.blockchain.node_id
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to broadcast contract: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="contract_broadcast_failed",
                message=error_msg,
                node_id=self.blockchain.node_id,
                details={"contract_id": contract_data.get("contract_id")}
            )
            
            return False
            
    def broadcast_validation(self, validation_data: Dict) -> bool:
        """Broadcast contract validation"""
        try:
            # Send validation message
            self.lora.send_message(
                type=MessageType.VALIDATION,
                data=validation_data
            )
            
            self.mesh_logger.log_validation_event(
                contract_id=validation_data["contract_id"],
                validator_id=self.blockchain.node_id,
                status="success",
                details=validation_data
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to broadcast validation: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="validation_broadcast_failed",
                message=error_msg,
                node_id=self.blockchain.node_id,
                details={"contract_id": validation_data.get("contract_id")}
            )
            
            return False
            
    def _handle_message(self, message: Dict):
        """Handle received message"""
        try:
            # Get message type
            msg_type = MessageType(message["type"])
            
            # Get handler
            handler = self.message_handlers.get(msg_type)
            if not handler:
                logger.warning(f"No handler for message type: {msg_type}")
                return
                
            # Handle message
            handler(message)
            
        except Exception as e:
            error_msg = f"Failed to handle message: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="message_handling_failed",
                message=error_msg,
                node_id=self.blockchain.node_id,
                details={"message_type": message.get("type")}
            )
            
    def _handle_handshake(self, message: Dict):
        """Handle handshake message"""
        try:
            data = message["data"]
            node_id = data["node_id"]
            
            with self._node_lock:
                # Create or update node
                node = self.nodes.get(node_id)
                if not node:
                    node = MeshNode(
                        node_id=node_id,
                        status=NodeStatus.UNKNOWN,
                        last_seen=int(time.time()),
                        stake=data.get("stake", 0.0),
                        location=data.get("location")
                    )
                    self.nodes[node_id] = node
                    
                    self.mesh_logger.log_node_event(
                        node_id=node_id,
                        event_type="new_node",
                        status="discovered",
                        details=data
                    )
                else:
                    node.last_seen = int(time.time())
                    node.stake = data.get("stake", node.stake)
                    node.location = data.get("location", node.location)
                    
                # Update status
                if data.get("is_bridge"):
                    node.status = NodeStatus.BRIDGE
                    self.bridge_nodes.add(node_id)
                elif data.get("is_online"):
                    node.status = NodeStatus.ONLINE
                else:
                    node.status = NodeStatus.OFFLINE
                    
                self.mesh_logger.log_node_event(
                    node_id=node_id,
                    event_type="status_update",
                    status=node.status.value,
                    details={"is_bridge": data.get("is_bridge")}
                )
                    
                # Request sync if needed
                if node.status in (NodeStatus.ONLINE, NodeStatus.BRIDGE):
                    self.sync_manager.request_sync(node_id)
                    
        except Exception as e:
            error_msg = f"Failed to handle handshake: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="handshake_failed",
                message=error_msg,
                node_id=message.get("sender")
            )
            
    def _handle_contract(self, message: Dict):
        """Handle contract message"""
        try:
            data = message["data"]
            
            # Validate and add contract
            if self.blockchain.validate_contract(data):
                self.blockchain.add_contract(data)
                
                self.mesh_logger.log_contract_event(
                    contract_id=data["contract_id"],
                    event_type="received",
                    status="success",
                    node_id=message.get("sender")
                )
                
                # Forward to bridges
                self._forward_to_bridges(message)
                
        except Exception as e:
            error_msg = f"Failed to handle contract: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="contract_handling_failed",
                message=error_msg,
                node_id=message.get("sender"),
                details={"contract_id": data.get("contract_id")}
            )
            
    def _handle_validation(self, message: Dict):
        """Handle validation message"""
        try:
            data = message["data"]
            
            # Validate and add validation
            if self.blockchain.validate_pod(data):
                self.blockchain.add_pod(data)
                
                self.mesh_logger.log_validation_event(
                    contract_id=data["contract_id"],
                    validator_id=message.get("sender"),
                    status="success",
                    details=data
                )
                
                # Forward to bridges
                self._forward_to_bridges(message)
                
        except Exception as e:
            error_msg = f"Failed to handle validation: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="validation_handling_failed",
                message=error_msg,
                node_id=message.get("sender"),
                details={"contract_id": data.get("contract_id")}
            )
            
    def _discovery_loop(self):
        """Node discovery loop"""
        while self.running:
            try:
                # Send handshake
                self._send_handshake()
                
                # Sleep
                time.sleep(self.config.discovery_interval)
                
            except Exception as e:
                error_msg = f"Discovery error: {str(e)}"
                logger.error(error_msg)
                
                self.mesh_logger.log_error(
                    error_type="discovery_failed",
                    message=error_msg,
                    node_id=self.blockchain.node_id
                )
                
                time.sleep(5)
                
    def _cleanup_loop(self):
        """Node cleanup loop"""
        while self.running:
            try:
                now = int(time.time())
                
                with self._node_lock:
                    # Remove expired nodes
                    expired = []
                    for node_id, node in self.nodes.items():
                        if now - node.last_seen > self.config.node_timeout:
                            expired.append(node_id)
                            
                            self.mesh_logger.log_node_event(
                                node_id=node_id,
                                event_type="node_expired",
                                status="removed",
                                details={"last_seen": node.last_seen}
                            )
                            
                    # Cleanup
                    for node_id in expired:
                        del self.nodes[node_id]
                        self.bridge_nodes.discard(node_id)
                        
                # Sleep
                time.sleep(60)
                
            except Exception as e:
                error_msg = f"Cleanup error: {str(e)}"
                logger.error(error_msg)
                
                self.mesh_logger.log_error(
                    error_type="cleanup_failed",
                    message=error_msg,
                    node_id=self.blockchain.node_id
                )
                
                time.sleep(5)
                
    def _send_handshake(self):
        """Send handshake message"""
        try:
            # Create handshake data
            data = {
                "node_id": self.blockchain.node_id,
                "is_bridge": self.config.is_bridge,
                "is_online": self.blockchain.is_online(),
                "stake": self.blockchain.get_stake(),
                "location": self.config.location
            }
            
            # Send handshake
            self.lora.send_message(
                type=MessageType.HANDSHAKE,
                data=data
            )
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="handshake",
                status="sent",
                details=data
            )
            
        except Exception as e:
            error_msg = f"Failed to send handshake: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="handshake_send_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def _forward_to_bridges(self, message: Dict):
        """Forward message to bridge nodes"""
        try:
            # Only forward if we're not a bridge
            if not self.config.is_bridge:
                return
                
            # Forward to each bridge
            for bridge_id in self.bridge_nodes:
                if bridge_id != message.get("sender"):
                    self.lora.send_message(
                        type=MessageType(message["type"]),
                        data=message["data"],
                        recipient=bridge_id
                    )
                    
                    self.mesh_logger.log_node_event(
                        node_id=bridge_id,
                        event_type="message_forwarded",
                        status="success",
                        details={
                            "message_type": message["type"],
                            "sender": message.get("sender")
                        }
                    )
                    
        except Exception as e:
            error_msg = f"Failed to forward message: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="message_forward_failed",
                message=error_msg,
                node_id=self.blockchain.node_id,
                details={
                    "message_type": message.get("type"),
                    "recipient": bridge_id
                }
            ) 