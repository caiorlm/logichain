"""
Decentralized P2P Network Implementation
"""

import socket
import threading
import json
import time
import logging
import random
import asyncio
import hashlib
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, asdict
from models import Block, Transaction
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Network Constants
DEFAULT_PORT = 9567
PEER_SYNC_INTERVAL = 300  # 5 minutes
CHAIN_SYNC_INTERVAL = 600  # 10 minutes
MAX_PEERS = 50
BOOTSTRAP_NODES = [
    ("localhost", DEFAULT_PORT),  # Local testing
    # Add more bootstrap nodes here
]

@dataclass
class PeerInfo:
    """Peer information"""
    host: str
    port: int
    last_seen: float
    version: str = "1.0.0"
    blocks: int = 0
    is_mining: bool = False

class P2PNetwork:
    """Decentralized P2P Network implementation"""
    
    def __init__(self, host: str = "localhost", port: int = 5000):
        self.host = host
        self.port = port
        self.peers: Set[tuple] = set()  # (host, port)
        self.db = DatabaseManager()
        
        # Message queues
        self.block_queue = Queue()
        self.tx_queue = Queue()
        
        # Network state
        self.running = False
        self.server_socket = None
        
        # Processing threads
        self.server_thread = None
        self.block_processor = None
        self.tx_processor = None
        
    def start(self):
        """Start P2P network"""
        try:
            # Initialize server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            
            self.running = True
            
            # Start processing threads
            self.server_thread = threading.Thread(target=self._accept_connections)
            self.block_processor = threading.Thread(target=self._process_blocks)
            self.tx_processor = threading.Thread(target=self._process_transactions)
            
            self.server_thread.daemon = True
            self.block_processor.daemon = True
            self.tx_processor.daemon = True
            
            self.server_thread.start()
            self.block_processor.start()
            self.tx_processor.start()
            
            logger.info(f"P2P network started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start P2P network: {str(e)}")
            self.stop()
            
    def stop(self):
        """Stop P2P network"""
        self.running = False
        
        if self.server_socket:
            self.server_socket.close()
            
        # Clear queues
        while not self.block_queue.empty():
            self.block_queue.get()
        while not self.tx_queue.empty():
            self.tx_queue.get()
            
        logger.info("P2P network stopped")
        
    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Connection error: {str(e)}")
                    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle client connection"""
        try:
            while self.running:
                # Receive message
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                # Parse message
                message = json.loads(data.decode())
                message_type = message.get('type')
                
                if message_type == 'block':
                    self.block_queue.put(message['data'])
                elif message_type == 'transaction':
                    self.tx_queue.put(message['data'])
                elif message_type == 'peer':
                    self._handle_peer_message(message['data'])
                    
        except Exception as e:
            logger.error(f"Client handler error: {str(e)}")
            
        finally:
            client_socket.close()
            
    def _process_blocks(self):
        """Process received blocks"""
        while self.running:
            try:
                if self.block_queue.empty():
                    time.sleep(0.1)
                    continue
                    
                block_data = self.block_queue.get()
                
                # Convert to Block object
                block = Block(
                    index=block_data['index'],
                    timestamp=block_data['timestamp'],
                    transactions=[
                        Transaction(**tx_data)
                        for tx_data in block_data['transactions']
                    ],
                    previous_hash=block_data['previous_hash'],
                    difficulty=block_data['difficulty'],
                    nonce=block_data['nonce'],
                    miner_address=block_data['miner_address'],
                    mining_reward=block_data['mining_reward']
                )
                
                # Verify and save block
                if block.verify_transactions() and self.db.save_block(block):
                    logger.info(f"Processed block {block.index}")
                    
                    # Propagate to peers
                    self.broadcast_block(block)
                else:
                    logger.warning(f"Invalid block {block.index}")
                    
            except Exception as e:
                logger.error(f"Block processing error: {str(e)}")
                
    def _process_transactions(self):
        """Process received transactions"""
        while self.running:
            try:
                if self.tx_queue.empty():
                    time.sleep(0.1)
                    continue
                    
                tx_data = self.tx_queue.get()
                
                # Convert to Transaction object
                transaction = Transaction(**tx_data)
                
                # Save to mempool
                if self.db.save_transaction_to_mempool(transaction):
                    logger.info(f"Processed transaction {transaction.tx_hash}")
                    
                    # Propagate to peers
                    self.broadcast_transaction(transaction)
                else:
                    logger.warning(f"Invalid transaction {transaction.tx_hash}")
                    
            except Exception as e:
                logger.error(f"Transaction processing error: {str(e)}")
                
    def _handle_peer_message(self, peer_data: Dict):
        """Handle peer discovery message"""
        peer_host = peer_data.get('host')
        peer_port = peer_data.get('port')
        
        if peer_host and peer_port:
            self.add_peer(peer_host, peer_port)
            
    def add_peer(self, host: str, port: int):
        """Add new peer"""
        peer = (host, port)
        if peer not in self.peers and peer != (self.host, self.port):
            self.peers.add(peer)
            logger.info(f"Added peer {host}:{port}")
            
    def broadcast_block(self, block: Block):
        """Broadcast block to peers"""
        message = {
            'type': 'block',
            'data': block.to_dict()
        }
        self._broadcast_message(message)
        
    def broadcast_transaction(self, transaction: Transaction):
        """Broadcast transaction to peers"""
        message = {
            'type': 'transaction',
            'data': transaction.to_dict()
        }
        self._broadcast_message(message)
        
    def _broadcast_message(self, message: Dict):
        """Broadcast message to all peers"""
        message_data = json.dumps(message).encode()
        
        for peer in self.peers.copy():
            try:
                # Connect to peer
                peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                peer_socket.settimeout(5)
                peer_socket.connect(peer)
                
                # Send message
                peer_socket.send(message_data)
                peer_socket.close()
                
            except Exception as e:
                logger.warning(f"Failed to send to peer {peer}: {str(e)}")
                self.peers.remove(peer)
        
    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        unique = f"{self.host}:{self.port}:{time.time()}"
        return hashlib.sha256(unique.encode()).hexdigest()[:16]
        
    async def discover_peers(self):
        """Discover new peers"""
        while self.running:
            try:
                # Try bootstrap nodes first
                if not self.peers:
                    for host, port in BOOTSTRAP_NODES:
                        await self.connect_to_peer(host, port)
                        
                # Get peers from known peers
                for peer in list(self.peers):
                    try:
                        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        peer_socket.settimeout(5)
                        peer_socket.connect(peer)
                        
                        # Send get_peers request
                        message = {
                            'type': 'get_peers',
                            'node_id': self._generate_node_id()
                        }
                        peer_socket.send(json.dumps(message).encode())
                        
                        # Read response
                        data = peer_socket.recv(4096)
                        if data:
                            response = json.loads(data.decode())
                            new_peers = response.get('peers', [])
                            
                            # Connect to new peers
                            for new_peer in new_peers:
                                await self.connect_to_peer(
                                    new_peer['host'],
                                    new_peer['port']
                                )
                                
                    except Exception as e:
                        logger.error(f"Error getting peers from {peer}: {str(e)}")
                        
                    finally:
                        peer_socket.close()
                        
            except Exception as e:
                logger.error(f"Error in peer discovery: {str(e)}")
                
            await asyncio.sleep(PEER_SYNC_INTERVAL)
            
    async def sync_with_peers(self):
        """Synchronize blockchain with peers"""
        while self.running:
            try:
                # Get random peer
                if not self.peers:
                    await asyncio.sleep(60)
                    continue
                    
                peer = random.choice(list(self.peers))
                
                # Connect to peer
                peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                peer_socket.settimeout(5)
                peer_socket.connect(peer)
                
                # Get latest blocks
                message = {
                    'type': 'get_blocks',
                    'node_id': self._generate_node_id(),
                    'from_block': len(self.db.get_blocks())
                }
                peer_socket.send(json.dumps(message).encode())
                
                # Read response
                data = peer_socket.recv(8192)  # Larger buffer for blocks
                if data:
                    response = json.loads(data.decode())
                    new_blocks = response.get('blocks', [])
                    
                    # Process new blocks
                    for block_data in new_blocks:
                        block = Block.from_dict(block_data)
                        if block.hash not in self.db.get_blocks():
                            if block.is_valid():
                                # Add block to chain
                                self.db.add_block(block)
                                await self.broadcast_block(block)
                                
            except Exception as e:
                logger.error(f"Error syncing with peers: {str(e)}")
                
            finally:
                peer_socket.close()
                
            await asyncio.sleep(CHAIN_SYNC_INTERVAL)
            
    async def connect_to_peer(self, host: str, port: int):
        """Connect to a new peer"""
        if len(self.peers) >= MAX_PEERS:
            return
            
        peer = (host, port)
        if peer in self.peers:
            return
            
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.settimeout(5)
            peer_socket.connect((host, port))
            
            # Send hello message
            message = {
                'type': 'hello',
                'node_id': self._generate_node_id(),
                'version': "1.0.0",
                'blocks': len(self.db.get_blocks()),
                'port': self.port
            }
            peer_socket.send(json.dumps(message).encode())
            
            # Add to peer list
            self.peers.add(peer)
            logger.info(f"Connected to peer {host}:{port}")
            
        except Exception as e:
            logger.error(f"Error connecting to peer {host}:{port}: {str(e)}")
            
        finally:
            peer_socket.close()
            
    async def maintain_peers(self):
        """Maintain peer list and remove inactive peers"""
        while self.running:
            try:
                current_time = time.time()
                inactive_peers = []
                
                # Check each peer
                for peer in self.peers:
                    if current_time - peer[1] > PEER_SYNC_INTERVAL * 2:
                        inactive_peers.append(peer)
                        
                # Remove inactive peers
                for peer in inactive_peers:
                    self.peers.remove(peer)
                    logger.info(f"Removed inactive peer {peer}")
                    
            except Exception as e:
                logger.error(f"Error maintaining peers: {str(e)}")
                
            await asyncio.sleep(60)
            
    async def handle_hello(self, message: Dict, writer: asyncio.StreamWriter):
        """Handle hello message from peer"""
        peer_addr = writer.get_extra_info('peername')
        peer_id = f"{peer_addr[0]}:{message['port']}"
        
        self.peers.add((peer_addr[0], message['port']))
        
        # Send response
        response = {
            'type': 'hello_ack',
            'node_id': self._generate_node_id(),
            'blocks': len(self.db.get_blocks())
        }
        writer.write(json.dumps(response).encode())
        await writer.drain()
        
    async def handle_get_peers(self, writer: asyncio.StreamWriter):
        """Handle get_peers request"""
        peers_data = [
            {
                'host': peer[0],
                'port': peer[1],
                'version': "1.0.0",
                'blocks': len(self.db.get_blocks())
            }
            for peer in self.peers
        ]
        
        response = {
            'type': 'peers',
            'peers': peers_data
        }
        writer.write(json.dumps(response).encode())
        await writer.drain()
        
    async def handle_new_block(self, message: Dict):
        """Handle new block from peer"""
        try:
            block = Block.from_dict(message['block'])
            if block.hash not in self.db.get_blocks():
                if block.is_valid():
                    self.db.add_block(block)
                    await self.broadcast_block(block)
                    
        except Exception as e:
            logger.error(f"Error handling new block: {str(e)}")
            
    async def handle_new_transaction(self, message: Dict):
        """Handle new transaction from peer"""
        try:
            transaction = Transaction(**message['transaction'])
            if transaction.tx_hash not in self.db.get_transactions():
                if Block.verify_transaction_signature(transaction):
                    self.db.add_transaction(transaction)
                    await self.broadcast_transaction(transaction)
                    
        except Exception as e:
            logger.error(f"Error handling new transaction: {str(e)}")
            
    async def handle_get_blocks(self, message: Dict, writer: asyncio.StreamWriter):
        """Handle get_blocks request"""
        try:
            from_block = message['from_block']
            # TODO: Implement block retrieval from local chain
            blocks = []  # Get blocks from local chain
            
            response = {
                'type': 'blocks',
                'blocks': [block.to_dict() for block in blocks]
            }
            writer.write(json.dumps(response).encode())
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error handling get_blocks: {str(e)}") 