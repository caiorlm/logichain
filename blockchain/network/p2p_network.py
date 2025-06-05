"""
P2P Network implementation with full node capabilities
"""

import asyncio
import json
import logging
import socket
import time
from typing import Dict, List, Optional, Set, Tuple
import sqlite3
from datetime import datetime
from .config import *
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.wallet import Wallet
from ..consensus.pow_consensus import PoWConsensus

logger = logging.getLogger(__name__)

class P2PNetwork:
    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.node_id = f"node_{int(time.time())}"
        
        # Network state
        self.peers: Dict[str, "PeerConnection"] = {}
        self.known_nodes: Set[Tuple[str, int]] = set(BOOTSTRAP_NODES)
        self.server = None
        self.running = False
        
        # Blockchain state
        self.consensus = PoWConsensus()
        self.mempool: List[Transaction] = []
        self.sync_in_progress = False
        
        # Initialize database
        self._init_database()
        
        logger.info(f"P2P Network initialized - Node ID: {self.node_id}")
        
    def _init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    previous_hash TEXT,
                    timestamp REAL,
                    nonce INTEGER,
                    difficulty INTEGER,
                    miner_address TEXT,
                    reward REAL
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    block_hash TEXT,
                    from_address TEXT,
                    to_address TEXT,
                    amount REAL,
                    fee REAL,
                    timestamp REAL,
                    FOREIGN KEY (block_hash) REFERENCES blocks(hash)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    address TEXT PRIMARY KEY,
                    port INTEGER,
                    last_seen REAL,
                    reputation INTEGER
                );
            """)
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
            
    async def start(self):
        """Start P2P network server"""
        if self.running:
            return
            
        self.running = True
        
        # Start server
        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port
        )
        
        logger.info(f"P2P Network listening on {self.host}:{self.port}")
        
        # Start background tasks
        asyncio.create_task(self._discovery_loop())
        asyncio.create_task(self._sync_loop())
        asyncio.create_task(self._mempool_cleanup_loop())
        
        await self.server.serve_forever()
        
    async def stop(self):
        """Stop P2P network"""
        if not self.running:
            return
            
        self.running = False
        
        # Close all peer connections
        for peer in self.peers.values():
            await peer.close()
            
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        logger.info("P2P Network stopped")
        
    async def broadcast_block(self, block: Block):
        """Broadcast a block to all peers"""
        if not self.consensus.validate_block(block):
            logger.warning(f"Invalid block {block.hash}, not broadcasting")
            return
            
        # Save to database
        self._save_block(block)
        
        # Broadcast to peers
        message = {
            "type": "new_block",
            "block": block.to_dict()
        }
        
        await self._broadcast(message)
        logger.info(f"Broadcasted block {block.hash}")
        
    async def broadcast_transaction(self, transaction: Transaction):
        """Broadcast a transaction to all peers"""
        if not self.consensus.validate_transaction(transaction):
            logger.warning(f"Invalid transaction {transaction.hash}, not broadcasting")
            return
            
        # Add to mempool
        if transaction.hash not in [tx.hash for tx in self.mempool]:
            self.mempool.append(transaction)
            
        # Broadcast to peers
        message = {
            "type": "new_transaction",
            "transaction": transaction.to_dict()
        }
        
        await self._broadcast(message)
        logger.info(f"Broadcasted transaction {transaction.hash}")
        
    async def _handle_connection(self, reader, writer):
        """Handle incoming peer connection"""
        peer = PeerConnection(reader, writer, self)
        try:
            # Perform handshake
            if not await peer.handshake():
                writer.close()
                await writer.wait_closed()
                return
                
            # Add to peers
            self.peers[peer.id] = peer
            logger.info(f"New peer connected: {peer.id}")
            
            # Handle messages
            while self.running:
                message = await peer.receive_message()
                if message:
                    await self._handle_message(message, peer)
                else:
                    break
                    
        except Exception as e:
            logger.error(f"Error handling peer connection: {e}")
        finally:
            # Clean up
            if peer.id in self.peers:
                del self.peers[peer.id]
            writer.close()
            await writer.wait_closed()
            
    async def _handle_message(self, message: dict, peer: "PeerConnection"):
        """Handle received peer message"""
        try:
            msg_type = message.get("type")
            
            if msg_type == "new_block":
                block = Block.from_dict(message["block"])
                if self.consensus.validate_block(block):
                    await self.broadcast_block(block)
                    
            elif msg_type == "new_transaction":
                transaction = Transaction.from_dict(message["transaction"])
                if self.consensus.validate_transaction(transaction):
                    await self.broadcast_transaction(transaction)
                    
            elif msg_type == "get_blocks":
                # Send requested blocks
                start_hash = message.get("start_hash")
                blocks = self._get_blocks_after(start_hash)
                response = {
                    "type": "blocks",
                    "blocks": [block.to_dict() for block in blocks]
                }
                await peer.send_message(response)
                
            elif msg_type == "get_peers":
                # Share known peers
                response = {
                    "type": "peers",
                    "peers": list(self.known_nodes)
                }
                await peer.send_message(response)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            
    def _save_block(self, block: Block):
        """Save block to database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Save block
            cursor.execute("""
                INSERT OR REPLACE INTO blocks
                (hash, previous_hash, timestamp, nonce, difficulty, miner_address, reward)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                block.hash,
                block.previous_hash,
                block.timestamp,
                block.nonce,
                block.difficulty,
                block.miner_address,
                BLOCK_REWARD
            ))
            
            # Save transactions
            for tx in block.transactions:
                cursor.execute("""
                    INSERT OR REPLACE INTO transactions
                    (tx_hash, block_hash, from_address, to_address, amount, fee, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx.hash,
                    block.hash,
                    tx.from_address,
                    tx.to_address,
                    tx.amount,
                    tx.fee,
                    tx.timestamp
                ))
                
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving block to database: {e}")
            
    def _get_blocks_after(self, start_hash: str) -> List[Block]:
        """Get blocks after given hash"""
        blocks = []
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Find block height
            cursor.execute("""
                WITH RECURSIVE chain AS (
                    SELECT hash, previous_hash, 0 as height
                    FROM blocks
                    WHERE previous_hash IS NULL  -- Genesis block
                    UNION ALL
                    SELECT b.hash, b.previous_hash, c.height + 1
                    FROM blocks b
                    JOIN chain c ON b.previous_hash = c.hash
                )
                SELECT height FROM chain WHERE hash = ?
            """, (start_hash,))
            
            result = cursor.fetchone()
            if result:
                start_height = result[0]
                
                # Get blocks after this height
                cursor.execute("""
                    WITH RECURSIVE chain AS (
                        SELECT hash, previous_hash, 0 as height
                        FROM blocks
                        WHERE previous_hash IS NULL
                        UNION ALL
                        SELECT b.hash, b.previous_hash, c.height + 1
                        FROM blocks b
                        JOIN chain c ON b.previous_hash = c.hash
                    )
                    SELECT b.* FROM blocks b
                    JOIN chain c ON b.hash = c.hash
                    WHERE c.height > ?
                    ORDER BY c.height
                """, (start_height,))
                
                for row in cursor.fetchall():
                    block = Block.from_db_row(row)
                    blocks.append(block)
                    
            conn.close()
            
        except Exception as e:
            logger.error(f"Error getting blocks: {e}")
            
        return blocks
        
    async def _discovery_loop(self):
        """Periodic peer discovery"""
        while self.running:
            try:
                # Ask peers for their peers
                message = {"type": "get_peers"}
                await self._broadcast(message)
                
                # Connect to known nodes
                for node in self.known_nodes - set(self.peers.keys()):
                    try:
                        reader, writer = await asyncio.open_connection(
                            node[0],
                            node[1]
                        )
                        await self._handle_connection(reader, writer)
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                
            await asyncio.sleep(PING_INTERVAL)
            
    async def _sync_loop(self):
        """Periodic blockchain sync"""
        while self.running:
            if not self.sync_in_progress and len(self.peers) >= MIN_PEERS_FOR_CONSENSUS:
                try:
                    self.sync_in_progress = True
                    
                    # Get latest block
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT hash FROM blocks
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    conn.close()
                    
                    if result:
                        latest_hash = result[0]
                        
                        # Request blocks after our latest
                        message = {
                            "type": "get_blocks",
                            "start_hash": latest_hash
                        }
                        await self._broadcast(message)
                        
                except Exception as e:
                    logger.error(f"Error in sync loop: {e}")
                finally:
                    self.sync_in_progress = False
                    
            await asyncio.sleep(SYNC_INTERVAL)
            
    async def _mempool_cleanup_loop(self):
        """Periodic mempool cleanup"""
        while self.running:
            try:
                current_time = time.time()
                # Remove transactions older than 1 hour
                self.mempool = [
                    tx for tx in self.mempool
                    if current_time - tx.timestamp < 3600
                ]
            except Exception as e:
                logger.error(f"Error in mempool cleanup: {e}")
                
            await asyncio.sleep(60)
            
    async def _broadcast(self, message: dict):
        """Broadcast message to all peers"""
        for peer in list(self.peers.values()):
            try:
                await peer.send_message(message)
            except:
                # Remove failed peer
                if peer.id in self.peers:
                    del self.peers[peer.id]
                    
class PeerConnection:
    """Represents a connection to a peer"""
    
    def __init__(self, reader, writer, network):
        self.reader = reader
        self.writer = writer
        self.network = network
        self.id = None
        
    async def handshake(self) -> bool:
        """Perform initial handshake"""
        try:
            # Send our version info
            message = {
                "type": "version",
                "version": PROTOCOL_VERSION,
                "node_id": self.network.node_id
            }
            await self.send_message(message)
            
            # Receive their version
            response = await self.receive_message()
            if not response or response.get("type") != "version":
                return False
                
            self.id = response.get("node_id")
            return bool(self.id)
            
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False
            
    async def send_message(self, message: dict):
        """Send message to peer"""
        try:
            data = json.dumps(message).encode()
            self.writer.write(len(data).to_bytes(4, "big"))
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
            
    async def receive_message(self) -> Optional[dict]:
        """Receive message from peer"""
        try:
            # Read message length
            length_bytes = await self.reader.read(4)
            if not length_bytes:
                return None
                
            length = int.from_bytes(length_bytes, "big")
            
            # Read message data
            data = await self.reader.read(length)
            if not data:
                return None
                
            return json.loads(data.decode())
            
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None
            
    async def close(self):
        """Close the connection"""
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass 