import time
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

class NodeStatus(Enum):
    ACTIVE = "ACTIVE"
    UNREACHABLE = "UNREACHABLE"
    DEAD_ZONE = "DEAD_ZONE"

@dataclass
class MeshNode:
    node_id: str
    last_seen: float
    hop_count: int
    status: NodeStatus
    neighbors: Set[str]

@dataclass
class HeartbeatMessage:
    node_id: str
    timestamp: float
    hop_count: int
    neighbors: List[str]
    signature: bytes

class LoRaMonitor:
    def __init__(self):
        self.heartbeat_interval = 300  # 5 minutes
        self.max_retries = 3
        self.retry_backoff = 2  # exponential backoff multiplier
        self.node_timeout = 900  # 15 minutes
        self.max_hop_count = 3
        
        self.nodes: Dict[str, MeshNode] = {}
        self.pending_acks: Dict[str, float] = {}
        self.dead_zones: Set[str] = set()
        
    async def start_monitoring(self):
        """Start monitoring tasks"""
        await asyncio.gather(
            self._heartbeat_task(),
            self._monitor_task(),
            self._cleanup_task()
        )
        
    async def _heartbeat_task(self):
        """Send periodic heartbeats"""
        while True:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                print(f"Heartbeat error: {e}")
                await asyncio.sleep(10)
                
    async def _monitor_task(self):
        """Monitor node status and handle retransmissions"""
        while True:
            try:
                await self._check_node_status()
                await self._handle_retransmissions()
                await asyncio.sleep(60)
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(10)
                
    async def _cleanup_task(self):
        """Clean up expired nodes and dead zones"""
        while True:
            try:
                self._cleanup_expired_nodes()
                await asyncio.sleep(300)
            except Exception as e:
                print(f"Cleanup error: {e}")
                await asyncio.sleep(10)
                
    async def _send_heartbeat(self):
        """Send heartbeat to mesh network"""
        # Implementation depends on LoRa hardware interface
        pass
        
    async def handle_heartbeat(self, message: HeartbeatMessage) -> bool:
        """Handle received heartbeat message"""
        try:
            # Verify signature
            if not self._verify_signature(message):
                return False
                
            # Update node status
            self.nodes[message.node_id] = MeshNode(
                node_id=message.node_id,
                last_seen=message.timestamp,
                hop_count=message.hop_count,
                status=NodeStatus.ACTIVE,
                neighbors=set(message.neighbors)
            )
            
            # Send ACK if direct neighbor
            if message.hop_count == 1:
                await self._send_ack(message.node_id)
                
            # Propagate heartbeat if within hop limit
            if message.hop_count < self.max_hop_count:
                await self._propagate_heartbeat(message)
                
            return True
            
        except Exception as e:
            print(f"Error handling heartbeat: {e}")
            return False
            
    async def _check_node_status(self):
        """Check status of all known nodes"""
        current_time = time.time()
        
        for node_id, node in self.nodes.items():
            time_since_last = current_time - node.last_seen
            
            if time_since_last > self.node_timeout:
                node.status = NodeStatus.UNREACHABLE
                
                # Check if in dead zone
                if self._is_in_dead_zone(node):
                    node.status = NodeStatus.DEAD_ZONE
                    self.dead_zones.add(node_id)
                    
    async def _handle_retransmissions(self):
        """Handle retransmissions for unacked messages"""
        current_time = time.time()
        
        for node_id, sent_time in list(self.pending_acks.items()):
            retry_count = 0
            while retry_count < self.max_retries:
                # Calculate backoff time
                backoff = self.retry_backoff ** retry_count
                if current_time - sent_time < backoff:
                    break
                    
                # Attempt retransmission
                success = await self._retransmit_to_node(node_id)
                if success:
                    del self.pending_acks[node_id]
                    break
                    
                retry_count += 1
                
            if retry_count >= self.max_retries:
                # Mark as unreachable after max retries
                if node_id in self.nodes:
                    self.nodes[node_id].status = NodeStatus.UNREACHABLE
                del self.pending_acks[node_id]
                
    def _cleanup_expired_nodes(self):
        """Remove expired nodes and update dead zones"""
        current_time = time.time()
        
        # Remove expired nodes
        expired = [
            nid for nid, node in self.nodes.items()
            if current_time - node.last_seen > self.node_timeout * 2
        ]
        for nid in expired:
            del self.nodes[nid]
            
        # Update dead zones
        self._update_dead_zones()
        
    def _is_in_dead_zone(self, node: MeshNode) -> bool:
        """Check if node is in a dead zone"""
        # Check if all neighbors are also unreachable
        return all(
            nid in self.nodes and
            self.nodes[nid].status != NodeStatus.ACTIVE
            for nid in node.neighbors
        )
        
    def _update_dead_zones(self):
        """Update dead zone map"""
        # Remove zones that have active nodes
        active_zones = [
            zone for zone in self.dead_zones
            if any(
                node.status == NodeStatus.ACTIVE
                for node in self.nodes.values()
                if zone in node.neighbors
            )
        ]
        
        for zone in active_zones:
            self.dead_zones.remove(zone)
            
    def get_network_status(self) -> Dict:
        """Get current network status"""
        return {
            "active_nodes": len([
                n for n in self.nodes.values()
                if n.status == NodeStatus.ACTIVE
            ]),
            "unreachable_nodes": len([
                n for n in self.nodes.values()
                if n.status == NodeStatus.UNREACHABLE
            ]),
            "dead_zones": len(self.dead_zones),
            "total_nodes": len(self.nodes)
        }
        
    def _verify_signature(self, message: HeartbeatMessage) -> bool:
        """Verify heartbeat signature"""
        # Implementation depends on crypto setup
        return True
        
    async def _send_ack(self, node_id: str):
        """Send ACK to node"""
        # Implementation depends on LoRa hardware interface
        pass
        
    async def _propagate_heartbeat(self, message: HeartbeatMessage):
        """Propagate heartbeat to other nodes"""
        # Implementation depends on LoRa hardware interface
        pass
        
    async def _retransmit_to_node(self, node_id: str) -> bool:
        """Attempt to retransmit to node"""
        # Implementation depends on LoRa hardware interface
        return False 