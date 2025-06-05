"""
Network node implementation
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import time
import logging
from ..core.block import Block
from ..consensus.hybrid_consensus import HybridConsensus
from ..security.crypto import KeyManager
from ..mining.hybrid_miner import HybridMiner, MiningConfig
from ..core.blockchain import Blockchain
from ..wallet.wallet import Wallet

logger = logging.getLogger(__name__)

@dataclass
class NodeConfig:
    """Node configuration"""
    node_id: str
    mining_enabled: bool = False
    mining_config: Optional[MiningConfig] = None

class Node:
    """Network node implementation"""
    
    def __init__(self, config: NodeConfig):
        self.node_id = config.node_id
        self.consensus = HybridConsensus()
        self.key_manager = KeyManager()
        self.peers = {}
        self.blocks = []
        
        if config.mining_enabled:
            self.miner = HybridMiner(config.mining_config)
        else:
            self.miner = None
        
    def connect_peer(self, peer_id: str, peer_info: Dict) -> bool:
        """Connect to a peer node"""
        if peer_id in self.peers:
            logger.warning(f"Already connected to peer: {peer_id}")
            return False
            
        self.peers[peer_id] = peer_info
        logger.info(f"Connected to peer: {peer_id}")
        return True
        
    def disconnect_peer(self, peer_id: str) -> bool:
        """Disconnect from a peer node"""
        if peer_id not in self.peers:
            logger.warning(f"Not connected to peer: {peer_id}")
            return False
            
        del self.peers[peer_id]
        logger.info(f"Disconnected from peer: {peer_id}")
        return True
        
    def broadcast_block(self, block: Block) -> bool:
        """Broadcast block to all peers"""
        if not self.peers:
            logger.warning("No peers connected")
            return False
            
        # Sign block
        signature = self.key_manager.sign_message(block.hash.encode())
        
        # Broadcast to peers
        for peer_id in self.peers:
            try:
                self._send_block_to_peer(peer_id, block, signature)
            except Exception as e:
                logger.error(f"Failed to send block to peer {peer_id}: {e}")
                
        return True
        
    def _send_block_to_peer(self, peer_id: str, block: Block, signature: bytes):
        """Send block to specific peer"""
        if peer_id not in self.peers:
            raise ValueError(f"Unknown peer: {peer_id}")
            
        # This would use actual network communication
        # For now just log it
        logger.info(f"Sending block {block.hash} to peer {peer_id}")
        
    def receive_block(self, block: Block, sender_id: str, signature: bytes) -> bool:
        """Handle received block from peer"""
        if sender_id not in self.peers:
            logger.warning(f"Block received from unknown peer: {sender_id}")
            return False
            
        # Verify signature
        if not self.key_manager.verify_signature(
            block.hash.encode(),
            signature,
            self.peers[sender_id]['public_key']
        ):
            logger.warning(f"Invalid block signature from peer: {sender_id}")
            return False
            
        # Add to consensus
        if self.consensus.propose_block(block, sender_id):
            self.blocks.append(block)
            return True
            
        return False
        
    def get_peer_info(self, peer_id: str) -> Optional[Dict]:
        """Get information about a peer"""
        return self.peers.get(peer_id)
        
    def get_connected_peers(self) -> List[str]:
        """Get list of connected peer IDs"""
        return list(self.peers.keys())
        
    def get_block_history(self) -> List[Block]:
        """Get list of received blocks"""
        return self.blocks.copy()
        
    def is_peer_connected(self, peer_id: str) -> bool:
        """Check if peer is connected"""
        return peer_id in self.peers 