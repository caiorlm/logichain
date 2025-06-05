"""
Node startup script with database persistence
"""

import os
import sys
import time
import logging
import threading
import argparse
from typing import Optional
from pathlib import Path

from p2p_network import P2PNetwork
from mining_manager import MiningManager
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Node:
    """Blockchain node with persistence"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5000,
        miner_address: Optional[str] = None,
        is_miner: bool = False,
        difficulty: int = 4
    ):
        self.host = host
        self.port = port
        self.is_miner = is_miner
        self.miner_address = miner_address
        self.difficulty = difficulty
        
        # Initialize components
        self.db = DatabaseManager()
        self.network = P2PNetwork(host, port)
        
        if self.is_miner and self.miner_address:
            self.mining_manager = MiningManager(
                miner_address=self.miner_address,
                difficulty=self.difficulty
            )
        else:
            self.mining_manager = None
            
        # Control flags
        self.stop_mining = threading.Event()
        
    def start(self):
        """Start node operation"""
        try:
            # Ensure data directory exists
            os.makedirs("data/blockchain", exist_ok=True)
            
            # Start P2P network
            logger.info(f"Starting P2P network on {self.host}:{self.port}")
            self.network.start()
            
            # Start mining if enabled
            if self.is_miner and self.mining_manager:
                logger.info("Starting mining operations...")
                mining_thread = threading.Thread(
                    target=self.mining_manager.start_mining,
                    args=(self.stop_mining,)
                )
                mining_thread.daemon = True
                mining_thread.start()
                
            # Keep main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
                
        except Exception as e:
            logger.error(f"Node startup error: {str(e)}")
            self.stop()
            
    def stop(self):
        """Stop node operation"""
        logger.info("Stopping node...")
        
        if self.is_miner:
            self.stop_mining.set()
            
        self.network.stop()
        
def main():
    parser = argparse.ArgumentParser(description="Start a blockchain node")
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host address to bind to"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on"
    )
    
    parser.add_argument(
        "--miner",
        action="store_true",
        help="Run as a mining node"
    )
    
    parser.add_argument(
        "--miner-address",
        type=str,
        help="Miner's wallet address"
    )
    
    parser.add_argument(
        "--difficulty",
        type=int,
        default=4,
        help="Mining difficulty"
    )
    
    args = parser.parse_args()
    
    # Validate miner configuration
    if args.miner and not args.miner_address:
        parser.error("Miner address is required for mining nodes")
        
    # Start node
    node = Node(
        host=args.host,
        port=args.port,
        miner_address=args.miner_address,
        is_miner=args.miner,
        difficulty=args.difficulty
    )
    
    node.start()
    
if __name__ == "__main__":
    main() 