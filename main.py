import asyncio
import argparse
import logging
import os
from dotenv import load_dotenv
from blockchain.security.secure_lora import SecureLoRaProtocol
from blockchain.security.proof_of_delivery import SecurePoD
from blockchain.core.block_validator import EnhancedBlockValidator
from blockchain.sync.network_sync import SecureSynchronizer
from blockchain.security.monitor import SecurityMonitor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlockchainNode:
    def __init__(self, mode: str):
        self.mode = mode.upper()
        self.running = False
        
        # Initialize components
        self.lora_protocol = SecureLoRaProtocol()
        self.pod_validator = SecurePoD()
        self.block_validator = EnhancedBlockValidator()
        self.synchronizer = SecureSynchronizer()
        self.security_monitor = SecurityMonitor()
        
        # Load configuration
        self.load_config()
        
    def load_config(self):
        """Load configuration from environment variables"""
        self.config = {
            "NETWORK_MODE": os.getenv("NETWORK_MODE", "ONLINE"),
            "LORA_FREQUENCY": int(os.getenv("LORA_FREQUENCY", "915000000")),
            "LORA_BANDWIDTH": int(os.getenv("LORA_BANDWIDTH", "125000")),
            "LORA_CODING_RATE": int(os.getenv("LORA_CODING_RATE", "5")),
            "LORA_SPREADING_FACTOR": int(os.getenv("LORA_SPREADING_FACTOR", "7")),
            "KEY_ROTATION_INTERVAL": int(os.getenv("KEY_ROTATION_INTERVAL", "3600")),
            "MIN_QUORUM_SIZE": int(os.getenv("MIN_QUORUM_SIZE", "3")),
            "MAX_BLOCK_SIZE_ONLINE": int(os.getenv("MAX_BLOCK_SIZE_ONLINE", "1048576")),
            "MAX_BLOCK_SIZE_OFFLINE": int(os.getenv("MAX_BLOCK_SIZE_OFFLINE", "1024")),
            "MAX_TX_COUNT_ONLINE": int(os.getenv("MAX_TX_COUNT_ONLINE", "1000")),
            "MAX_TX_COUNT_OFFLINE": int(os.getenv("MAX_TX_COUNT_OFFLINE", "10")),
            "METRICS_COLLECTION_INTERVAL": int(os.getenv("METRICS_COLLECTION_INTERVAL", "60")),
            "ALERT_HISTORY_SIZE": int(os.getenv("ALERT_HISTORY_SIZE", "1000"))
        }
        
    async def start(self):
        """Start the blockchain node"""
        try:
            logger.info(f"Starting blockchain node in {self.mode} mode")
            self.running = True
            
            # Start security monitoring
            monitor_task = asyncio.create_task(
                self.security_monitor.start()
            )
            
            # Start main processing loop
            process_task = asyncio.create_task(
                self.process_loop()
            )
            
            # Wait for tasks to complete
            await asyncio.gather(monitor_task, process_task)
            
        except Exception as e:
            logger.error(f"Error starting node: {str(e)}")
            raise
            
    async def stop(self):
        """Stop the blockchain node"""
        logger.info("Stopping blockchain node")
        self.running = False
        await self.security_monitor.stop()
        
    async def process_loop(self):
        """Main processing loop"""
        try:
            while self.running:
                if self.mode == "ONLINE":
                    await self.process_online()
                else:
                    await self.process_offline()
                    
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in processing loop: {str(e)}")
            await self.stop()
            
    async def process_online(self):
        """Process in online mode"""
        try:
            # Online mode processing:
            # 1. Validate incoming blocks
            # 2. Process transactions
            # 3. Maintain network state
            # 4. Synchronize with other nodes
            pass
            
        except Exception as e:
            logger.error(f"Error in online processing: {str(e)}")
            
    async def process_offline(self):
        """Process in offline mode"""
        try:
            # Offline mode processing:
            # 1. Handle LoRa communications
            # 2. Process local transactions
            # 3. Maintain local state
            # 4. Queue updates for online sync
            pass
            
        except Exception as e:
            logger.error(f"Error in offline processing: {str(e)}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Secure Dual-Mode Blockchain Node"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["online", "offline"],
        default="online",
        help="Operating mode (online/offline)"
    )
    args = parser.parse_args()
    
    try:
        # Create and start node
        node = BlockchainNode(args.mode)
        
        # Handle shutdown gracefully
        try:
            await node.start()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await node.stop()
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return 1
        
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        exit(1) 