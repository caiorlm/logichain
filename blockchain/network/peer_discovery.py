"""
LogiChain P2P Discovery System
Implements secure peer discovery and management
"""

import socket
import json
import time
import threading
import logging
from typing import Dict, List, Optional, Set
import sqlite3
import hashlib
import ecdsa
from dataclasses import dataclass
from ..config import NETWORK

@dataclass
class PeerInfo:
    """Information about a peer node"""
    node_id: str
    ip: str
    port: int
    last_seen: float
    version: str
    is_active: bool = True
    
class PeerDiscovery:
    """Manages P2P network discovery and connections"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = NETWORK["P2P_PORT"],
        db_path: str = "peers.db",
        max_peers: int = NETWORK["MAX_PEERS"]
    ):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.max_peers = max_peers
        
        # Initialize peer storage
        self._init_db()
        
        # Active connections
        self.peers: Dict[str, PeerInfo] = {}
        self.blacklist: Set[str] = set()
        
        # Cryptographic keys for secure messaging
        self._init_keys()
        
        # Network state
        self.is_running = False
        self.server_socket = None
        
        # Start background tasks
        self.discovery_thread = None
        self.ping_thread = None
        
    def _init_db(self):
        """Initialize SQLite database for peer persistence"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    node_id TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    last_seen REAL NOT NULL,
                    version TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    ip TEXT PRIMARY KEY,
                    reason TEXT,
                    timestamp REAL
                )
            """)
            
    def _init_keys(self):
        """Initialize ECDSA keys for secure messaging"""
        self.signing_key = ecdsa.SigningKey.generate(
            curve=ecdsa.SECP256k1
        )
        self.verifying_key = self.signing_key.get_verifying_key()
        self.node_id = hashlib.sha256(
            self.verifying_key.to_string()
        ).hexdigest()
        
    def start(self):
        """Start P2P discovery and connection management"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # Start server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Start background threads
        self.discovery_thread = threading.Thread(
            target=self._discovery_loop
        )
        self.ping_thread = threading.Thread(
            target=self._ping_loop
        )
        
        self.discovery_thread.start()
        self.ping_thread.start()
        
        # Load bootstrap nodes
        self._load_bootstrap_nodes()
        
    def stop(self):
        """Stop P2P discovery and close connections"""
        self.is_running = False
        
        # Close all peer connections
        for peer_id in list(self.peers.keys()):
            self.disconnect_peer(peer_id)
            
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
            
        # Wait for threads
        if self.discovery_thread:
            self.discovery_thread.join()
        if self.ping_thread:
            self.ping_thread.join()
            
    def _discovery_loop(self):
        """Main discovery loop"""
        while self.is_running:
            try:
                # Accept new connections
                client_socket, address = self.server_socket.accept()
                
                # Handle connection in new thread
                threading.Thread(
                    target=self._handle_connection,
                    args=(client_socket, address)
                ).start()
                
            except Exception as e:
                if self.is_running:
                    logging.error(f"Discovery error: {str(e)}")
                    
            time.sleep(1)
            
    def _ping_loop(self):
        """Ping active peers periodically"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Check each peer
                for peer_id, peer in list(self.peers.items()):
                    if current_time - peer.last_seen > NETWORK["PEER_PING_INTERVAL"]:
                        if not self._ping_peer(peer):
                            self.disconnect_peer(peer_id)
                            
            except Exception as e:
                logging.error(f"Ping error: {str(e)}")
                
            time.sleep(NETWORK["PEER_PING_INTERVAL"])
            
    def _handle_connection(self, client_socket: socket.socket, address: tuple):
        """Handle new peer connection"""
        try:
            # Receive handshake
            data = self._receive_message(client_socket)
            if not data or "node_id" not in data:
                raise ValueError("Invalid handshake")
                
            # Verify signature
            if not self._verify_signature(data):
                raise ValueError("Invalid signature")
                
            # Create peer info
            peer = PeerInfo(
                node_id=data["node_id"],
                ip=address[0],
                port=data["port"],
                last_seen=time.time(),
                version=data["version"]
            )
            
            # Add peer if not blacklisted
            if peer.ip not in self.blacklist:
                self._add_peer(peer)
                
            # Send peer list
            self._send_peer_list(client_socket)
            
        except Exception as e:
            logging.error(f"Connection error: {str(e)}")
            
        finally:
            client_socket.close()
            
    def _add_peer(self, peer: PeerInfo):
        """Add new peer to active connections"""
        if len(self.peers) >= self.max_peers:
            return False
            
        self.peers[peer.node_id] = peer
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO peers
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    peer.node_id,
                    peer.ip,
                    peer.port,
                    peer.last_seen,
                    peer.version,
                    peer.is_active
                )
            )
            
        return True
        
    def disconnect_peer(self, peer_id: str):
        """Disconnect and remove peer"""
        if peer_id in self.peers:
            peer = self.peers[peer_id]
            
            # Update database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE peers SET is_active = ? WHERE node_id = ?",
                    (False, peer_id)
                )
                
            del self.peers[peer_id]
            
    def _ping_peer(self, peer: PeerInfo) -> bool:
        """Send ping message to peer"""
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((peer.ip, peer.port))
            
            # Send ping
            message = {
                "type": "ping",
                "node_id": self.node_id,
                "timestamp": time.time()
            }
            self._send_message(sock, message)
            
            # Wait for pong
            data = self._receive_message(sock)
            if not data or data.get("type") != "pong":
                return False
                
            # Update last seen
            peer.last_seen = time.time()
            return True
            
        except Exception:
            return False
            
        finally:
            sock.close()
            
    def _load_bootstrap_nodes(self):
        """Load initial bootstrap nodes"""
        for node in NETWORK["BOOTSTRAP_NODES"]:
            try:
                host, port = node.split(":")
                peer = PeerInfo(
                    node_id="bootstrap",
                    ip=host,
                    port=int(port),
                    last_seen=time.time(),
                    version=NETWORK["VERSION"]
                )
                self._add_peer(peer)
            except Exception as e:
                logging.error(f"Bootstrap error: {str(e)}")
                
    def _send_message(self, sock: socket.socket, message: Dict):
        """Send signed message to peer"""
        # Add signature
        message["signature"] = self.signing_key.sign(
            json.dumps(message).encode()
        ).hex()
        
        # Send message
        data = json.dumps(message).encode()
        sock.sendall(len(data).to_bytes(4, "big"))
        sock.sendall(data)
        
    def _receive_message(self, sock: socket.socket) -> Optional[Dict]:
        """Receive and verify signed message"""
        try:
            # Get message length
            length = int.from_bytes(sock.recv(4), "big")
            
            # Receive data
            data = sock.recv(length)
            message = json.loads(data.decode())
            
            # Verify signature if present
            if "signature" in message:
                if not self._verify_signature(message):
                    return None
                    
            return message
            
        except Exception:
            return None
            
    def _verify_signature(self, message: Dict) -> bool:
        """Verify message signature"""
        try:
            signature = bytes.fromhex(message.pop("signature"))
            message_data = json.dumps(message).encode()
            
            # Get peer's public key
            if message["node_id"] in self.peers:
                peer = self.peers[message["node_id"]]
                verifying_key = ecdsa.VerifyingKey.from_string(
                    bytes.fromhex(peer.node_id),
                    curve=ecdsa.SECP256k1
                )
                
                # Verify signature
                return verifying_key.verify(signature, message_data)
                
            return False
            
        except Exception:
            return False
            
    def get_active_peers(self) -> List[PeerInfo]:
        """Get list of active peers"""
        return list(self.peers.values())
        
    def get_peer_count(self) -> int:
        """Get number of active peers"""
        return len(self.peers)
        
    def is_peer_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted"""
        return ip in self.blacklist 