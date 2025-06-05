"""
Real-time blockchain monitoring system
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
import websockets
from dataclasses import dataclass, asdict
from ..core.database_manager import DatabaseManager
from ..core.models import Block, Transaction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ChainMetrics:
    """Chain metrics data"""
    height: int
    total_blocks: int
    total_transactions: int
    pending_transactions: int
    active_miners: int
    network_hashrate: float
    average_block_time: float
    chain_difficulty: int
    last_block_time: float
    
@dataclass
class NetworkMetrics:
    """Network metrics data"""
    connected_peers: int
    active_nodes: int
    network_latency: float
    sync_status: str
    version_distribution: Dict[str, int]
    
@dataclass
class MiningMetrics:
    """Mining metrics data"""
    total_miners: int
    active_miners: int
    total_rewards: float
    average_reward: float
    reward_distribution: Dict[str, float]
    hashrate_distribution: Dict[str, float]

class ChainMonitor:
    def __init__(self, websocket_port: int = 8765):
        self.db = DatabaseManager()
        self.websocket_port = websocket_port
        self.clients = set()
        self.monitoring = False
        
    async def start_monitoring(self):
        """Start monitoring system"""
        self.monitoring = True
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_client,
            "localhost",
            self.websocket_port
        )
        
        # Start metrics collection
        asyncio.create_task(self.collect_metrics())
        
        logger.info(f"Monitoring system started on port {self.websocket_port}")
        await server.wait_closed()
        
    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        try:
            self.clients.add(websocket)
            logger.info(f"Client connected: {websocket.remote_address}")
            
            while True:
                message = await websocket.recv()
                await self.process_client_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {websocket.remote_address}")
        finally:
            self.clients.remove(websocket)
            
    async def collect_metrics(self):
        """Collect and broadcast metrics periodically"""
        while self.monitoring:
            try:
                # Collect metrics
                chain_metrics = await self.get_chain_metrics()
                network_metrics = await self.get_network_metrics()
                mining_metrics = await self.get_mining_metrics()
                
                # Create metrics package
                metrics = {
                    'timestamp': datetime.now().isoformat(),
                    'chain': asdict(chain_metrics),
                    'network': asdict(network_metrics),
                    'mining': asdict(mining_metrics)
                }
                
                # Broadcast to all clients
                if self.clients:
                    await asyncio.gather(*[
                        client.send(json.dumps(metrics))
                        for client in self.clients
                    ])
                    
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(10)
                
    async def get_chain_metrics(self) -> ChainMetrics:
        """Get current chain metrics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get basic chain stats
                cursor.execute("""
                    SELECT COUNT(*), MAX(timestamp)
                    FROM blocks
                """)
                total_blocks, last_block_time = cursor.fetchone()
                
                # Get transaction stats
                cursor.execute("SELECT COUNT(*) FROM transactions")
                total_transactions = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM transactions
                    WHERE status = 'pending'
                """)
                pending_transactions = cursor.fetchone()[0]
                
                # Get mining stats
                cursor.execute("""
                    SELECT COUNT(DISTINCT miner_address)
                    FROM blocks
                    WHERE timestamp > ?
                """, (time.time() - 3600,))  # Active in last hour
                active_miners = cursor.fetchone()[0]
                
                # Calculate average block time
                cursor.execute("""
                    SELECT AVG(t2.timestamp - t1.timestamp) as avg_time
                    FROM blocks t1
                    JOIN blocks t2 ON t1.index = t2.index - 1
                    WHERE t2.timestamp > ?
                """, (time.time() - 3600,))
                avg_block_time = cursor.fetchone()[0] or 0
                
                # Calculate network hashrate
                cursor.execute("""
                    SELECT difficulty
                    FROM blocks
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                current_difficulty = cursor.fetchone()[0]
                
                # Estimate hashrate from difficulty and block time
                network_hashrate = (
                    current_difficulty * (2**32)
                ) / max(avg_block_time, 1)
                
                return ChainMetrics(
                    height=total_blocks,
                    total_blocks=total_blocks,
                    total_transactions=total_transactions,
                    pending_transactions=pending_transactions,
                    active_miners=active_miners,
                    network_hashrate=network_hashrate,
                    average_block_time=avg_block_time,
                    chain_difficulty=current_difficulty,
                    last_block_time=last_block_time
                )
                
        except Exception as e:
            logger.error(f"Error getting chain metrics: {e}")
            return ChainMetrics(0, 0, 0, 0, 0, 0.0, 0.0, 0, 0.0)
            
    async def get_network_metrics(self) -> NetworkMetrics:
        """Get current network metrics"""
        try:
            # Get network stats from P2P system
            from ..network.p2p_network import P2PNetwork
            network = P2PNetwork()
            peers = network.get_peers()
            
            # Calculate version distribution
            versions = {}
            for peer in peers:
                versions[peer.version] = versions.get(peer.version, 0) + 1
                
            # Calculate average network latency
            latencies = []
            for peer in peers:
                try:
                    start = time.time()
                    reader, writer = await asyncio.open_connection(
                        peer.host,
                        peer.port
                    )
                    writer.close()
                    await writer.wait_closed()
                    latencies.append(time.time() - start)
                except:
                    continue
                    
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            return NetworkMetrics(
                connected_peers=len(peers),
                active_nodes=len([p for p in peers if p.is_mining]),
                network_latency=avg_latency,
                sync_status="synced" if network.is_synced() else "syncing",
                version_distribution=versions
            )
            
        except Exception as e:
            logger.error(f"Error getting network metrics: {e}")
            return NetworkMetrics(0, 0, 0.0, "unknown", {})
            
    async def get_mining_metrics(self) -> MiningMetrics:
        """Get current mining metrics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get mining stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT miner_address) as total_miners,
                        COUNT(DISTINCT CASE 
                            WHEN timestamp > ? THEN miner_address 
                            END) as active_miners,
                        SUM(mining_reward) as total_rewards,
                        AVG(mining_reward) as avg_reward
                    FROM blocks
                    WHERE timestamp > ?
                """, (time.time() - 3600, time.time() - 86400))
                
                stats = cursor.fetchone()
                
                # Get reward distribution
                cursor.execute("""
                    SELECT miner_address, SUM(mining_reward) as rewards
                    FROM blocks
                    WHERE timestamp > ?
                    GROUP BY miner_address
                    ORDER BY rewards DESC
                    LIMIT 10
                """, (time.time() - 86400,))
                
                rewards = {
                    row[0]: row[1]
                    for row in cursor.fetchall()
                }
                
                # Calculate hashrate distribution
                cursor.execute("""
                    SELECT miner_address, COUNT(*) as blocks,
                           AVG(difficulty) as avg_difficulty
                    FROM blocks
                    WHERE timestamp > ?
                    GROUP BY miner_address
                    ORDER BY blocks DESC
                    LIMIT 10
                """, (time.time() - 3600,))
                
                hashrates = {}
                for row in cursor.fetchall():
                    miner, blocks, difficulty = row
                    # Estimate hashrate from blocks found and difficulty
                    hashrate = (blocks * difficulty * (2**32)) / 3600
                    hashrates[miner] = hashrate
                    
                return MiningMetrics(
                    total_miners=stats[0],
                    active_miners=stats[1],
                    total_rewards=stats[2],
                    average_reward=stats[3],
                    reward_distribution=rewards,
                    hashrate_distribution=hashrates
                )
                
        except Exception as e:
            logger.error(f"Error getting mining metrics: {e}")
            return MiningMetrics(0, 0, 0.0, 0.0, {}, {})
            
    async def process_client_message(self, websocket, message):
        """Process messages from monitoring clients"""
        try:
            data = json.loads(message)
            
            if data['type'] == 'get_metrics':
                # Send immediate metrics update
                metrics = {
                    'chain': asdict(await self.get_chain_metrics()),
                    'network': asdict(await self.get_network_metrics()),
                    'mining': asdict(await self.get_mining_metrics())
                }
                await websocket.send(json.dumps(metrics))
                
            elif data['type'] == 'subscribe':
                # Client wants real-time updates
                # Already handled by adding to self.clients
                await websocket.send(json.dumps({
                    'status': 'subscribed'
                }))
                
        except Exception as e:
            logger.error(f"Error processing client message: {e}")
            await websocket.send(json.dumps({
                'error': str(e)
            }))

async def main():
    """Main monitoring function"""
    monitor = ChainMonitor()
    await monitor.start_monitoring()

if __name__ == "__main__":
    asyncio.run(main()) 