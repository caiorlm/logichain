"""
LogiChain Mesh Network Visualizer
Handles WebSocket communication for mesh visualization
"""

import json
import asyncio
import logging
import websockets
from typing import Dict, Set, Optional
from dataclasses import dataclass, asdict
from .hybrid_manager import HybridMeshManager, NodeStatus
from .mesh_logger import MeshLogger

logger = logging.getLogger(__name__)

@dataclass
class NetworkStats:
    """Network statistics"""
    total: int = 0
    bridges: int = 0
    online: int = 0
    offline: int = 0

class MeshVisualizer:
    """Mesh network visualizer"""
    
    def __init__(
        self,
        hybrid_manager: HybridMeshManager,
        mesh_logger: MeshLogger,
        host: str = "localhost",
        port: int = 8765
    ):
        self.hybrid_manager = hybrid_manager
        self.mesh_logger = mesh_logger
        self.host = host
        self.port = port
        
        # WebSocket state
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server: Optional[websockets.WebSocketServer] = None
        
        # Network state
        self.edges: Dict[str, Dict] = {}
        self.stats = NetworkStats()
        
        # Register event handlers
        self.mesh_logger.register_handler(self._handle_event)
        
    async def start(self):
        """Start WebSocket server"""
        try:
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port
            )
            
            logger.info(f"Mesh visualizer started on ws://{self.host}:{self.port}")
            
            # Start background tasks
            asyncio.create_task(self._update_loop())
            
        except Exception as e:
            logger.error(f"Failed to start visualizer: {str(e)}")
            
    async def stop(self):
        """Stop WebSocket server"""
        try:
            if self.server:
                self.server.close()
                await self.server.wait_closed()
                
            logger.info("Mesh visualizer stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop visualizer: {str(e)}")
            
    async def _handle_client(
        self,
        websocket: websockets.WebSocketServerProtocol,
        path: str
    ):
        """Handle WebSocket client connection"""
        try:
            # Add client
            self.clients.add(websocket)
            
            # Send initial state
            await self._send_initial_state(websocket)
            
            # Handle messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(websocket, data)
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid message: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
            
        finally:
            # Remove client
            self.clients.remove(websocket)
            
    async def _handle_message(
        self,
        websocket: websockets.WebSocketServerProtocol,
        data: Dict
    ):
        """Handle client message"""
        try:
            message_type = data.get("type")
            
            if message_type == "get_node":
                node_id = data.get("node_id")
                if node_id:
                    await self._send_node(websocket, node_id)
                    
            elif message_type == "get_events":
                limit = data.get("limit", 100)
                events = self.mesh_logger.get_recent_events(limit=limit)
                await self._send_events(websocket, events)
                
        except Exception as e:
            logger.error(f"Failed to handle message: {str(e)}")
            
    async def _send_initial_state(
        self,
        websocket: websockets.WebSocketServerProtocol
    ):
        """Send initial state to client"""
        try:
            # Send nodes
            for node in self.hybrid_manager.nodes.values():
                await self._send_node(websocket, node.node_id)
                
            # Send edges
            for edge in self.edges.values():
                await websocket.send(json.dumps({
                    "type": "edge_update",
                    "edge": edge
                }))
                
            # Send stats
            await self._send_stats(websocket)
            
            # Send recent events
            events = self.mesh_logger.get_recent_events(limit=100)
            await self._send_events(websocket, events)
            
        except Exception as e:
            logger.error(f"Failed to send initial state: {str(e)}")
            
    async def _send_node(
        self,
        websocket: websockets.WebSocketServerProtocol,
        node_id: str
    ):
        """Send node update to client"""
        try:
            node = self.hybrid_manager.nodes.get(node_id)
            if node:
                await websocket.send(json.dumps({
                    "type": "node_update",
                    "node": {
                        "node_id": node.node_id,
                        "status": node.status.value,
                        "is_bridge": node.node_id in self.hybrid_manager.bridge_nodes,
                        "last_seen": node.last_seen,
                        "stake": node.stake,
                        "location": node.location
                    }
                }))
                
        except Exception as e:
            logger.error(f"Failed to send node: {str(e)}")
            
    async def _send_stats(
        self,
        websocket: Optional[websockets.WebSocketServerProtocol] = None
    ):
        """Send network statistics"""
        try:
            # Calculate stats
            self.stats.total = len(self.hybrid_manager.nodes)
            self.stats.bridges = len(self.hybrid_manager.bridge_nodes)
            self.stats.online = sum(
                1 for node in self.hybrid_manager.nodes.values()
                if node.status in (NodeStatus.ONLINE, NodeStatus.BRIDGE)
            )
            self.stats.offline = sum(
                1 for node in self.hybrid_manager.nodes.values()
                if node.status == NodeStatus.OFFLINE
            )
            
            # Create message
            message = json.dumps({
                "type": "stats_update",
                "stats": asdict(self.stats)
            })
            
            # Send to specific client or broadcast
            if websocket:
                await websocket.send(message)
            else:
                await self._broadcast(message)
                
        except Exception as e:
            logger.error(f"Failed to send stats: {str(e)}")
            
    async def _send_events(
        self,
        websocket: websockets.WebSocketServerProtocol,
        events: list
    ):
        """Send events to client"""
        try:
            for event in events:
                await websocket.send(json.dumps({
                    "type": "event",
                    "event": event
                }))
                
        except Exception as e:
            logger.error(f"Failed to send events: {str(e)}")
            
    async def _broadcast(self, message: str):
        """Broadcast message to all clients"""
        if not self.clients:
            return
            
        disconnected = set()
        
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
                
        # Remove disconnected clients
        self.clients -= disconnected
        
    def _handle_event(self, event: Dict):
        """Handle mesh logger event"""
        if not self.clients:
            return
            
        # Create message
        message = json.dumps({
            "type": "event",
            "event": event
        })
        
        # Broadcast event
        asyncio.create_task(self._broadcast(message))
        
        # Update edges for node events
        if event["type"] == "node_event":
            self._update_edges(event["node_id"])
            
    def _update_edges(self, node_id: str):
        """Update network edges"""
        try:
            node = self.hybrid_manager.nodes.get(node_id)
            if not node:
                return
                
            # Remove old edges
            old_edges = [
                edge_id
                for edge_id, edge in self.edges.items()
                if edge["from"] == node_id or edge["to"] == node_id
            ]
            
            for edge_id in old_edges:
                del self.edges[edge_id]
                
            # Add new edges
            if node.status in (NodeStatus.ONLINE, NodeStatus.BRIDGE):
                for other_id, other in self.hybrid_manager.nodes.items():
                    if other_id != node_id and other.status in (NodeStatus.ONLINE, NodeStatus.BRIDGE):
                        edge_id = f"{node_id}-{other_id}"
                        self.edges[edge_id] = {
                            "id": edge_id,
                            "from": node_id,
                            "to": other_id,
                            "is_bridge": node_id in self.hybrid_manager.bridge_nodes
                        }
                        
            # Broadcast edge updates
            for edge in self.edges.values():
                message = json.dumps({
                    "type": "edge_update",
                    "edge": edge
                })
                asyncio.create_task(self._broadcast(message))
                
        except Exception as e:
            logger.error(f"Failed to update edges: {str(e)}")
            
    async def _update_loop(self):
        """Background update loop"""
        while True:
            try:
                # Update stats
                await self._send_stats()
                
                # Sleep
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Update loop error: {str(e)}")
                await asyncio.sleep(1) 