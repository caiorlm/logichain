"""
Enhanced P2P synchronization system for LogiChain
"""

import asyncio
import logging
import json
import time
from typing import List, Dict, Set, Optional
from datetime import datetime
from models import Block, Transaction
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class P2PSync:
    def __init__(self, host: str = "localhost", port: int = 5000):
        self.host = host
        self.port = port
        self.db = DatabaseManager()
        self.peers: Set[str] = set()
        self.syncing = False
        self.last_sync = 0
        
    async def start_sync(self):
        """Start periodic sync with peers"""
        while True:
            try:
                if not self.syncing and time.time() - self.last_sync > 60:
                    await self.sync_with_peers()
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Sync error: {e}")
                await asyncio.sleep(30)
                
    async def sync_with_peers(self):
        """Synchronize chain state with peers"""
        try:
            self.syncing = True
            
            # Get local chain state
            local_height = await self.get_chain_height()
            local_head = await self.get_chain_head()
            
            # Get peer chain states
            peer_states = await self.get_peer_states()
            if not peer_states:
                logger.warning("No peers available for sync")
                return
                
            # Find best chain
            best_chain = max(
                peer_states,
                key=lambda x: (x['height'], x['total_difficulty'])
            )
            
            if best_chain['height'] <= local_height:
                logger.info("Local chain is up to date")
                return
                
            # Sync blocks from best peer
            await self.sync_blocks_from_peer(
                best_chain['peer'],
                local_height + 1,
                best_chain['height']
            )
            
            logger.info(f"Chain synchronized to height {best_chain['height']}")
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            
        finally:
            self.syncing = False
            self.last_sync = time.time()
            
    async def get_chain_height(self) -> int:
        """Get local chain height"""
        try:
            latest = self.db.get_latest_block()
            return latest.index if latest else 0
        except Exception as e:
            logger.error(f"Error getting chain height: {e}")
            return 0
            
    async def get_chain_head(self) -> Optional[str]:
        """Get local chain head hash"""
        try:
            latest = self.db.get_latest_block()
            return latest.hash if latest else None
        except Exception as e:
            logger.error(f"Error getting chain head: {e}")
            return None
            
    async def get_peer_states(self) -> List[Dict]:
        """Get chain states from all peers"""
        states = []
        
        for peer in self.peers:
            try:
                # Get peer chain state
                reader, writer = await asyncio.open_connection(
                    peer.split(':')[0],
                    int(peer.split(':')[1])
                )
                
                # Send state request
                writer.write(json.dumps({
                    'type': 'get_state'
                }).encode())
                await writer.drain()
                
                # Get response
                data = await reader.read(1024)
                state = json.loads(data.decode())
                
                states.append({
                    'peer': peer,
                    'height': state['height'],
                    'head': state['head'],
                    'total_difficulty': state['total_difficulty']
                })
                
                writer.close()
                await writer.wait_closed()
                
            except Exception as e:
                logger.error(f"Error getting state from {peer}: {e}")
                
        return states
        
    async def sync_blocks_from_peer(
        self,
        peer: str,
        start_height: int,
        end_height: int,
        batch_size: int = 100
    ):
        """Sync blocks from peer in batches"""
        try:
            current_height = start_height
            
            while current_height <= end_height:
                batch_end = min(current_height + batch_size, end_height)
                
                # Get block batch from peer
                reader, writer = await asyncio.open_connection(
                    peer.split(':')[0],
                    int(peer.split(':')[1])
                )
                
                # Send block request
                writer.write(json.dumps({
                    'type': 'get_blocks',
                    'start': current_height,
                    'end': batch_end
                }).encode())
                await writer.drain()
                
                # Get and process blocks
                data = await reader.read(8192)
                blocks_data = json.loads(data.decode())
                
                for block_data in blocks_data['blocks']:
                    # Validate and save block
                    block = Block.from_dict(block_data)
                    if not self.db.save_block(block, atomic=True):
                        raise Exception(f"Failed to save block {block.hash}")
                        
                    # Verify mining reward
                    if not await self.verify_block_reward(block):
                        raise Exception(f"Invalid mining reward in block {block.hash}")
                        
                logger.info(f"Synced blocks {current_height} to {batch_end}")
                current_height = batch_end + 1
                
                writer.close()
                await writer.wait_closed()
                
        except Exception as e:
            logger.error(f"Block sync failed: {e}")
            raise
            
    async def verify_block_reward(self, block: Block) -> bool:
        """Verify mining reward transaction in block"""
        try:
            # Find mining reward transaction
            reward_tx = next(
                (tx for tx in block.transactions
                 if tx.tx_type == 'mining_reward' and
                 tx.from_address == '0' * 64),
                None
            )
            
            if not reward_tx:
                logger.error(f"No mining reward in block {block.hash}")
                return False
                
            # Verify reward amount
            expected_reward = 50.0  # Implement proper reward calculation
            if reward_tx.amount != expected_reward:
                logger.error(f"Invalid reward amount in block {block.hash}")
                return False
                
            # Verify recipient is block miner
            if reward_tx.to_address != block.miner_address:
                logger.error(f"Invalid reward recipient in block {block.hash}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Reward verification failed: {e}")
            return False
            
    async def broadcast_block(self, block: Block):
        """Broadcast new block to peers"""
        for peer in self.peers:
            try:
                reader, writer = await asyncio.open_connection(
                    peer.split(':')[0],
                    int(peer.split(':')[1])
                )
                
                # Send block
                writer.write(json.dumps({
                    'type': 'new_block',
                    'block': block.to_dict()
                }).encode())
                await writer.drain()
                
                writer.close()
                await writer.wait_closed()
                
            except Exception as e:
                logger.error(f"Failed to broadcast to {peer}: {e}")
                
    def add_peer(self, host: str, port: int):
        """Add new peer"""
        peer = f"{host}:{port}"
        self.peers.add(peer)
        logger.info(f"Added peer: {peer}")
        
    def remove_peer(self, host: str, port: int):
        """Remove peer"""
        peer = f"{host}:{port}"
        self.peers.discard(peer)
        logger.info(f"Removed peer: {peer}")

async def main():
    """Main sync function"""
    sync = P2PSync()
    
    # Add some test peers
    sync.add_peer("peer1.logichain.net", 5000)
    sync.add_peer("peer2.logichain.net", 5000)
    
    # Start sync
    await sync.start_sync()

if __name__ == "__main__":
    asyncio.run(main()) 