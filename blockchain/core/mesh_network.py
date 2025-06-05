"""
LogiChain Mesh Network
Handles peer-to-peer communication in both online and offline modes
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

class NetworkMode(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    HYBRID = "hybrid"

@dataclass
class PeerState:
    """State information for a peer"""
    peer_id: str
    address: str
    port: int
    mode: NetworkMode
    last_seen: float
    block_height: int
    snapshot_timestamp: float
    
@dataclass
class MeshSnapshot:
    """Represents a network snapshot"""
    timestamp: float
    block_height: int
    transactions: List[Dict]
    contracts: Dict[str, Dict]
    peer_states: Dict[str, PeerState]
    hash: str

class MeshNetwork:
    """Manages peer-to-peer mesh networking"""
    
    def __init__(
        self,
        node_id: str,
        port: int,
        initial_peers: List[Tuple[str, int]] = None,
        offline_port: int = None,
        mesh_sync_interval: int = 60
    ):
        self.node_id = node_id
        self.port = port
        self.offline_port = offline_port or (port + 1)
        self.mesh_sync_interval = mesh_sync_interval
        
        # Network state
        self.mode = NetworkMode.ONLINE
        self.peers: Dict[str, PeerState] = {}
        self.offline_peers: Dict[str, PeerState] = {}
        self.snapshots: Dict[str, MeshSnapshot] = {}
        self.latest_snapshot: Optional[MeshSnapshot] = None
        
        # Initialize networking
        self._init_network(initial_peers)
        
    def _init_network(self, initial_peers: List[Tuple[str, int]]):
        """Initialize network connections"""
        # Start online listener
        self.online_thread = threading.Thread(
            target=self._run_online_listener,
            daemon=True
        )
        self.online_thread.start()
        
        # Start offline listener
        self.offline_thread = threading.Thread(
            target=self._run_offline_listener,
            daemon=True
        )
        self.offline_thread.start()
        
        # Connect to initial peers
        if initial_peers:
            for addr, port in initial_peers:
                self.connect_peer(addr, port)
                
    def _run_online_listener(self):
        """Run TCP listener for online mode"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", self.port))
        sock.listen(10)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                client, addr = sock.accept()
                executor.submit(self._handle_online_connection, client, addr)
                
    def _run_offline_listener(self):
        """Run UDP listener for offline mesh"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.offline_port))
        
        while True:
            data, addr = sock.recvfrom(65535)
            self._handle_offline_message(data, addr)
            
    def connect_peer(self, address: str, port: int) -> bool:
        """Connect to a new peer"""
        try:
            # Try online connection first
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((address, port))
            
            # Send handshake
            handshake = {
                "node_id": self.node_id,
                "mode": self.mode.value,
                "block_height": self.latest_snapshot.block_height if self.latest_snapshot else 0,
                "snapshot_timestamp": self.latest_snapshot.timestamp if self.latest_snapshot else 0
            }
            sock.send(json.dumps(handshake).encode())
            
            # Add to peers
            peer_state = PeerState(
                peer_id=handshake["node_id"],
                address=address,
                port=port,
                mode=NetworkMode.ONLINE,
                last_seen=time.time(),
                block_height=handshake["block_height"],
                snapshot_timestamp=handshake["snapshot_timestamp"]
            )
            self.peers[peer_state.peer_id] = peer_state
            
            return True
            
        except Exception:
            # Failed online, try offline mode
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(b"mesh_discovery", (address, self.offline_port))
                
                # Add to offline peers
                peer_state = PeerState(
                    peer_id=f"offline_{address}:{self.offline_port}",
                    address=address,
                    port=self.offline_port,
                    mode=NetworkMode.OFFLINE,
                    last_seen=time.time(),
                    block_height=0,
                    snapshot_timestamp=0
                )
                self.offline_peers[peer_state.peer_id] = peer_state
                
                return True
                
            except Exception:
                return False
                
    async def broadcast_transaction(
        self,
        transaction: Dict,
        mode: NetworkMode = None
    ) -> bool:
        """Broadcast transaction to network"""
        try:
            # Determine broadcast mode
            if mode is None:
                mode = self.mode
                
            # Prepare message
            message = {
                "type": "transaction",
                "data": transaction,
                "timestamp": time.time(),
                "node_id": self.node_id
            }
            encoded = json.dumps(message).encode()
            
            # Broadcast based on mode
            if mode in (NetworkMode.ONLINE, NetworkMode.HYBRID):
                # Send to online peers
                for peer in self.peers.values():
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((peer.address, peer.port))
                        sock.send(encoded)
                    except Exception:
                        continue
                        
            if mode in (NetworkMode.OFFLINE, NetworkMode.HYBRID):
                # Send to offline peers
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                for peer in self.offline_peers.values():
                    try:
                        sock.sendto(encoded, (peer.address, peer.port))
                    except Exception:
                        continue
                        
            return True
            
        except Exception:
            return False
            
    async def sync_snapshots(self) -> bool:
        """Synchronize snapshots with peers"""
        try:
            # Get latest snapshots from all peers
            all_snapshots = []
            
            # Get from online peers
            for peer in self.peers.values():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((peer.address, peer.port))
                    
                    # Request snapshot
                    request = {
                        "type": "get_snapshot",
                        "node_id": self.node_id
                    }
                    sock.send(json.dumps(request).encode())
                    
                    # Receive snapshot
                    data = sock.recv(1048576)  # 1MB max
                    snapshot = json.loads(data.decode())
                    all_snapshots.append(snapshot)
                    
                except Exception:
                    continue
                    
            # Get from offline peers
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for peer in self.offline_peers.values():
                try:
                    # Request snapshot
                    request = {
                        "type": "get_snapshot",
                        "node_id": self.node_id
                    }
                    sock.sendto(json.dumps(request).encode(), (peer.address, peer.port))
                    
                    # Receive snapshot (with timeout)
                    sock.settimeout(5)
                    data, _ = sock.recvfrom(65535)
                    snapshot = json.loads(data.decode())
                    all_snapshots.append(snapshot)
                    
                except Exception:
                    continue
                    
            # Find most recent valid snapshot
            if all_snapshots:
                newest = max(all_snapshots, key=lambda s: s["timestamp"])
                
                # Validate snapshot
                if self._validate_snapshot(newest):
                    self.latest_snapshot = MeshSnapshot(**newest)
                    self.snapshots[self.latest_snapshot.hash] = self.latest_snapshot
                    return True
                    
            return False
            
        except Exception:
            return False
            
    def _validate_snapshot(self, snapshot: Dict) -> bool:
        """Validate snapshot integrity"""
        try:
            # Check required fields
            required = {"timestamp", "block_height", "transactions", "contracts", "peer_states", "hash"}
            if not all(f in snapshot for f in required):
                return False
                
            # Validate timestamp
            if snapshot["timestamp"] > time.time():
                return False
                
            # Validate hash
            # TODO: Implement proper hash validation
                
            return True
            
        except Exception:
            return False
            
    def get_network_state(self) -> Tuple[NetworkMode, Dict]:
        """Get current network state"""
        try:
            # Count peers by mode
            online_count = len(self.peers)
            offline_count = len(self.offline_peers)
            
            # Determine overall mode
            if online_count > 0 and offline_count == 0:
                mode = NetworkMode.ONLINE
            elif online_count == 0 and offline_count > 0:
                mode = NetworkMode.OFFLINE
            else:
                mode = NetworkMode.HYBRID
                
            # Get state details
            state = {
                "online_peers": len(self.peers),
                "offline_peers": len(self.offline_peers),
                "latest_block_height": self.latest_snapshot.block_height if self.latest_snapshot else 0,
                "latest_snapshot_time": self.latest_snapshot.timestamp if self.latest_snapshot else 0
            }
            
            return mode, state
            
        except Exception:
            return NetworkMode.OFFLINE, {} 