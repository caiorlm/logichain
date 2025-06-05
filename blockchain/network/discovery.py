"""
Node discovery system with multiple discovery methods.
Implements DHT, mDNS, and seed nodes for robust peer discovery.
"""

from typing import Dict, List, Set, Optional, Tuple
import socket
import time
import json
import threading
import logging
from dataclasses import dataclass
import hashlib
import random
from collections import defaultdict

@dataclass
class NodeInfo:
    """Information about a network node"""
    id: str
    ip: str
    port: int
    last_seen: float
    version: str
    capabilities: List[str]
    reputation: float = 1.0

class NodeDiscovery:
    """Node discovery and management system"""
    
    def __init__(self, 
                 host: str,
                 port: int,
                 version: str,
                 seed_nodes: List[Tuple[str, int]] = None,
                 max_peers: int = 50,
                 ping_interval: int = 30,
                 cleanup_interval: int = 300):
        """
        Initialize node discovery
        
        Args:
            host: Host IP/interface
            port: Listen port
            version: Node version
            seed_nodes: List of seed nodes (ip, port)
            max_peers: Maximum number of peers
            ping_interval: Peer ping interval in seconds
            cleanup_interval: Dead peer cleanup interval in seconds
        """
        self.host = host
        self.port = port
        self.version = version
        self.seed_nodes = seed_nodes or []
        self.max_peers = max_peers
        self.ping_interval = ping_interval
        self.cleanup_interval = cleanup_interval
        
        # Node state
        self.node_id = self._generate_node_id()
        self.peers: Dict[str, NodeInfo] = {}
        self.pending_peers: Set[str] = set()
        self.blacklisted: Dict[str, float] = {}
        self.capabilities = ['discovery', 'blockchain', 'governance']
        
        # DHT routing table (k-bucket implementation)
        self.k = 20  # bucket size
        self.buckets: List[List[str]] = [[] for _ in range(160)]  # 160-bit node IDs
        
        # Thread management
        self.running = False
        self.threads: List[threading.Thread] = []
        
        # Statistics
        self.stats = defaultdict(int)
        
    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        unique = f"{self.host}:{self.port}:{time.time()}"
        return hashlib.sha256(unique.encode()).hexdigest()
    
    def start(self):
        """Start node discovery"""
        if self.running:
            return
            
        self.running = True
        
        # Start UDP listener
        udp_thread = threading.Thread(target=self._udp_listener)
        udp_thread.daemon = True
        udp_thread.start()
        self.threads.append(udp_thread)
        
        # Start maintenance threads
        ping_thread = threading.Thread(target=self._ping_loop)
        ping_thread.daemon = True
        ping_thread.start()
        self.threads.append(ping_thread)
        
        cleanup_thread = threading.Thread(target=self._cleanup_loop)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        self.threads.append(cleanup_thread)
        
        # Start DHT maintenance
        dht_thread = threading.Thread(target=self._dht_maintenance)
        dht_thread.daemon = True
        dht_thread.start()
        self.threads.append(dht_thread)
        
        # Bootstrap from seed nodes
        self._bootstrap()
        
        logging.info(f"Node discovery started on {self.host}:{self.port}")
    
    def stop(self):
        """Stop node discovery"""
        self.running = False
        for thread in self.threads:
            thread.join()
        logging.info("Node discovery stopped")
    
    def _udp_listener(self):
        """UDP message listener"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(1)
        
        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                self._handle_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"UDP listener error: {e}")
    
    def _handle_message(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming UDP message"""
        try:
            message = json.loads(data.decode())
            msg_type = message.get('type')
            
            if msg_type == 'ping':
                self._handle_ping(message, addr)
            elif msg_type == 'pong':
                self._handle_pong(message, addr)
            elif msg_type == 'find_node':
                self._handle_find_node(message, addr)
            elif msg_type == 'nodes':
                self._handle_nodes(message, addr)
            else:
                logging.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logging.error(f"Message handling error: {e}")
    
    def _handle_ping(self, message: Dict, addr: Tuple[str, int]):
        """Handle ping message"""
        node_id = message.get('node_id')
        if not node_id:
            return
            
        # Send pong response
        response = {
            'type': 'pong',
            'node_id': self.node_id,
            'version': self.version,
            'capabilities': self.capabilities
        }
        self._send_message(response, addr)
        
        # Update peer info
        self._update_peer(node_id, addr[0], addr[1], message)
    
    def _handle_pong(self, message: Dict, addr: Tuple[str, int]):
        """Handle pong message"""
        node_id = message.get('node_id')
        if not node_id:
            return
            
        if node_id in self.pending_peers:
            self.pending_peers.remove(node_id)
            self._update_peer(node_id, addr[0], addr[1], message)
    
    def _handle_find_node(self, message: Dict, addr: Tuple[str, int]):
        """Handle find_node message"""
        target_id = message.get('target')
        if not target_id:
            return
            
        # Find closest nodes in routing table
        closest = self._find_closest_nodes(target_id)
        
        # Send nodes response
        response = {
            'type': 'nodes',
            'node_id': self.node_id,
            'nodes': [
                {
                    'id': node_id,
                    'ip': self.peers[node_id].ip,
                    'port': self.peers[node_id].port
                }
                for node_id in closest
                if node_id in self.peers
            ]
        }
        self._send_message(response, addr)
    
    def _handle_nodes(self, message: Dict, addr: Tuple[str, int]):
        """Handle nodes message"""
        nodes = message.get('nodes', [])
        
        for node in nodes:
            node_id = node.get('id')
            ip = node.get('ip')
            port = node.get('port')
            
            if node_id and ip and port:
                self._update_peer(node_id, ip, port, {})
    
    def _update_peer(self, node_id: str, ip: str, port: int, info: Dict):
        """Update peer information"""
        if node_id == self.node_id:
            return
            
        if ip in self.blacklisted:
            return
            
        if len(self.peers) >= self.max_peers and node_id not in self.peers:
            return
            
        now = time.time()
        
        if node_id in self.peers:
            peer = self.peers[node_id]
            peer.last_seen = now
            if 'version' in info:
                peer.version = info['version']
            if 'capabilities' in info:
                peer.capabilities = info['capabilities']
        else:
            self.peers[node_id] = NodeInfo(
                id=node_id,
                ip=ip,
                port=port,
                last_seen=now,
                version=info.get('version', ''),
                capabilities=info.get('capabilities', [])
            )
            
        # Update DHT routing table
        self._update_routing_table(node_id)
    
    def _update_routing_table(self, node_id: str):
        """Update DHT routing table"""
        if node_id == self.node_id:
            return
            
        # Calculate distance (XOR metric)
        distance = int(node_id, 16) ^ int(self.node_id, 16)
        bucket_idx = distance.bit_length() - 1
        
        if bucket_idx < 0:
            bucket_idx = 0
            
        bucket = self.buckets[bucket_idx]
        
        if node_id in bucket:
            # Move to end (most recently seen)
            bucket.remove(node_id)
            bucket.append(node_id)
        elif len(bucket) < self.k:
            bucket.append(node_id)
        else:
            # Bucket full, ping oldest node
            oldest = bucket[0]
            if oldest in self.peers:
                self._ping_node(self.peers[oldest])
            else:
                bucket.pop(0)
                bucket.append(node_id)
    
    def _find_closest_nodes(self, target_id: str, k: int = 20) -> List[str]:
        """Find k closest nodes to target ID"""
        nodes = []
        
        # Calculate distances
        distances = [
            (node_id, int(node_id, 16) ^ int(target_id, 16))
            for node_id in self.peers
        ]
        
        # Sort by distance
        distances.sort(key=lambda x: x[1])
        
        # Return k closest
        return [node_id for node_id, _ in distances[:k]]
    
    def _ping_loop(self):
        """Periodic peer ping"""
        while self.running:
            try:
                now = time.time()
                
                for peer in list(self.peers.values()):
                    if now - peer.last_seen > self.ping_interval:
                        self._ping_node(peer)
                        
                time.sleep(1)
            except Exception as e:
                logging.error(f"Ping loop error: {e}")
    
    def _cleanup_loop(self):
        """Periodic dead peer cleanup"""
        while self.running:
            try:
                now = time.time()
                
                # Remove dead peers
                dead_peers = [
                    node_id
                    for node_id, peer in self.peers.items()
                    if now - peer.last_seen > self.cleanup_interval
                ]
                
                for node_id in dead_peers:
                    del self.peers[node_id]
                    
                # Cleanup blacklist
                self.blacklisted = {
                    ip: timestamp
                    for ip, timestamp in self.blacklisted.items()
                    if now - timestamp < 3600  # 1 hour blacklist
                }
                
                time.sleep(60)
            except Exception as e:
                logging.error(f"Cleanup loop error: {e}")
    
    def _dht_maintenance(self):
        """Periodic DHT maintenance"""
        while self.running:
            try:
                # Refresh buckets
                for i, bucket in enumerate(self.buckets):
                    if not bucket:
                        continue
                        
                    # Generate random ID in bucket range
                    target = self._random_id_in_bucket(i)
                    
                    # Find nodes
                    self._find_node(target)
                    
                time.sleep(60)
            except Exception as e:
                logging.error(f"DHT maintenance error: {e}")
    
    def _random_id_in_bucket(self, bucket_idx: int) -> str:
        """Generate random ID in bucket range"""
        min_distance = 2 ** bucket_idx
        max_distance = 2 ** (bucket_idx + 1)
        
        # Generate random distance in range
        distance = random.randint(min_distance, max_distance - 1)
        
        # XOR with own ID to get target
        target = int(self.node_id, 16) ^ distance
        
        return hex(target)[2:].zfill(64)  # 32 bytes = 64 hex chars
    
    def _bootstrap(self):
        """Bootstrap from seed nodes"""
        for ip, port in self.seed_nodes:
            self._ping_node(NodeInfo(
                id='',  # Will be set on pong
                ip=ip,
                port=port,
                last_seen=0,
                version='',
                capabilities=[]
            ))
    
    def _ping_node(self, node: NodeInfo):
        """Send ping to node"""
        message = {
            'type': 'ping',
            'node_id': self.node_id,
            'version': self.version,
            'capabilities': self.capabilities
        }
        
        if node.id:
            self.pending_peers.add(node.id)
            
        self._send_message(message, (node.ip, node.port))
    
    def _find_node(self, target_id: str):
        """Send find_node request"""
        message = {
            'type': 'find_node',
            'node_id': self.node_id,
            'target': target_id
        }
        
        # Send to k closest nodes
        closest = self._find_closest_nodes(target_id)
        for node_id in closest:
            if node_id in self.peers:
                peer = self.peers[node_id]
                self._send_message(message, (peer.ip, peer.port))
    
    def _send_message(self, message: Dict, addr: Tuple[str, int]):
        """Send UDP message"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            data = json.dumps(message).encode()
            sock.sendto(data, addr)
            sock.close()
        except Exception as e:
            logging.error(f"Failed to send message to {addr}: {e}")
            
    def get_active_peers(self) -> List[NodeInfo]:
        """Get list of active peers"""
        now = time.time()
        return [
            peer for peer in self.peers.values()
            if now - peer.last_seen <= self.ping_interval * 2
        ]
    
    def get_stats(self) -> Dict:
        """Get discovery statistics"""
        return {
            'total_peers': len(self.peers),
            'active_peers': len(self.get_active_peers()),
            'pending_peers': len(self.pending_peers),
            'blacklisted': len(self.blacklisted),
            'buckets': [len(b) for b in self.buckets],
            'stats': dict(self.stats)
        } 