"""
Bitcoin Core-like storage system implementation
"""

import os
import json
import logging
import hashlib
import threading
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChainDB:
    """
    Bitcoin Core-like storage system using files
    
    Structure:
    /blocks/
        - blk00000.dat  # Block data files
        - blk00001.dat
        - ...
    /chainstate/
        - CURRENT       # Current active database version
        - MANIFEST     # List of database files
        - LOG         # Database log
        /blocks/      # Block index
        /coins/      # UTXO set
        /wallets/    # Wallet data
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.blocks_dir = self.data_dir / "blocks"
        self.chainstate_dir = self.data_dir / "chainstate"
        self.current_block_file = 0
        self.lock = threading.Lock()
        
        # Create directory structure
        self._init_directories()
        
    def _init_directories(self):
        """Initialize directory structure"""
        # Create main directories
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.chainstate_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.chainstate_dir / "blocks").mkdir(exist_ok=True)
        (self.chainstate_dir / "coins").mkdir(exist_ok=True)
        (self.chainstate_dir / "wallets").mkdir(exist_ok=True)
        
        # Initialize manifest if not exists
        manifest_file = self.chainstate_dir / "MANIFEST"
        if not manifest_file.exists():
            manifest_file.write_text("version=1\n")
            
    def _get_block_filename(self, number: int) -> str:
        """Get block data filename"""
        return f"blk{number:05d}.dat"
        
    def _get_current_block_file(self) -> Path:
        """Get current block data file"""
        filename = self._get_block_filename(self.current_block_file)
        return self.blocks_dir / filename
        
    def store_block(self, block_data: Dict) -> bool:
        """Store a block"""
        try:
            with self.lock:
                # Convert block to bytes
                block_bytes = json.dumps(block_data).encode()
                
                # Get current file
                current_file = self._get_current_block_file()
                
                # Check if we need a new file (100MB limit)
                if current_file.exists() and current_file.stat().st_size > 100_000_000:
                    self.current_block_file += 1
                    current_file = self._get_current_block_file()
                    
                # Store block
                with open(current_file, 'ab') as f:
                    # Write block size
                    f.write(len(block_bytes).to_bytes(4, 'little'))
                    # Write block data
                    f.write(block_bytes)
                    
                # Update block index
                self._update_block_index(block_data)
                
                return True
                
        except Exception as e:
            logger.error(f"Error storing block: {e}")
            return False
            
    def _update_block_index(self, block_data: Dict):
        """Update block index"""
        try:
            index_file = self.chainstate_dir / "blocks" / f"{block_data['hash']}.json"
            index_data = {
                'hash': block_data['hash'],
                'prev_hash': block_data['prev_hash'],
                'height': block_data.get('height', 0),
                'file': self.current_block_file,
                'timestamp': block_data['timestamp']
            }
            index_file.write_text(json.dumps(index_data))
            
        except Exception as e:
            logger.error(f"Error updating block index: {e}")
            
    def get_block(self, block_hash: str) -> Optional[Dict]:
        """Get block by hash"""
        try:
            # Get block location from index
            index_file = self.chainstate_dir / "blocks" / f"{block_hash}.json"
            if not index_file.exists():
                return None
                
            index_data = json.loads(index_file.read_text())
            block_file = self.blocks_dir / self._get_block_filename(index_data['file'])
            
            # Read block from file
            with open(block_file, 'rb') as f:
                while True:
                    # Read block size
                    size_bytes = f.read(4)
                    if not size_bytes:
                        break
                        
                    size = int.from_bytes(size_bytes, 'little')
                    block_bytes = f.read(size)
                    block = json.loads(block_bytes.decode())
                    
                    if block['hash'] == block_hash:
                        return block
                        
            return None
            
        except Exception as e:
            logger.error(f"Error getting block: {e}")
            return None
            
    def store_transaction(self, tx_data: Dict) -> bool:
        """Store a transaction"""
        try:
            tx_file = self.chainstate_dir / "coins" / f"{tx_data['hash']}.json"
            tx_file.write_text(json.dumps(tx_data))
            return True
            
        except Exception as e:
            logger.error(f"Error storing transaction: {e}")
            return False
            
    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction by hash"""
        try:
            tx_file = self.chainstate_dir / "coins" / f"{tx_hash}.json"
            if not tx_file.exists():
                return None
                
            return json.loads(tx_file.read_text())
            
        except Exception as e:
            logger.error(f"Error getting transaction: {e}")
            return None
            
    def store_wallet(self, wallet_data: Dict) -> bool:
        """Store wallet data"""
        try:
            wallet_file = self.chainstate_dir / "wallets" / f"{wallet_data['address']}.json"
            wallet_file.write_text(json.dumps(wallet_data))
            return True
            
        except Exception as e:
            logger.error(f"Error storing wallet: {e}")
            return False
            
    def get_wallet(self, address: str) -> Optional[Dict]:
        """Get wallet by address"""
        try:
            wallet_file = self.chainstate_dir / "wallets" / f"{address}.json"
            if not wallet_file.exists():
                return None
                
            return json.loads(wallet_file.read_text())
            
        except Exception as e:
            logger.error(f"Error getting wallet: {e}")
            return None
            
    def get_wallet_balance(self, address: str) -> float:
        """Get wallet balance"""
        try:
            # Get all transactions
            coins_dir = self.chainstate_dir / "coins"
            balance = 0.0
            
            for tx_file in coins_dir.glob("*.json"):
                tx_data = json.loads(tx_file.read_text())
                
                # Add incoming
                if tx_data['to_address'] == address:
                    balance += float(tx_data['amount'])
                    
                # Subtract outgoing
                if tx_data['from_address'] == address and tx_data['from_address'] != '0' * 64:
                    balance -= float(tx_data['amount'])
                    
            return balance
            
        except Exception as e:
            logger.error(f"Error getting wallet balance: {e}")
            return 0.0
            
    def get_latest_blocks(self, count: int = 10) -> List[Dict]:
        """Get latest blocks"""
        try:
            blocks = []
            blocks_dir = self.chainstate_dir / "blocks"
            
            # Get all block index files
            index_files = sorted(
                blocks_dir.glob("*.json"),
                key=lambda x: json.loads(x.read_text())['timestamp'],
                reverse=True
            )
            
            # Get specified number of latest blocks
            for index_file in index_files[:count]:
                index_data = json.loads(index_file.read_text())
                block = self.get_block(index_data['hash'])
                if block:
                    blocks.append(block)
                    
            return blocks
            
        except Exception as e:
            logger.error(f"Error getting latest blocks: {e}")
            return []
            
    def get_pending_transactions(self) -> List[Dict]:
        """Get pending (unconfirmed) transactions"""
        try:
            pending = []
            coins_dir = self.chainstate_dir / "coins"
            
            for tx_file in coins_dir.glob("*.json"):
                tx_data = json.loads(tx_file.read_text())
                if not tx_data.get('block_hash'):
                    pending.append(tx_data)
                    
            return pending
            
        except Exception as e:
            logger.error(f"Error getting pending transactions: {e}")
            return []
            
    def get_all_wallets(self) -> List[Dict]:
        """Get all wallets"""
        try:
            wallets = []
            wallets_dir = self.chainstate_dir / "wallets"
            
            for wallet_file in wallets_dir.glob("*.json"):
                wallet_data = json.loads(wallet_file.read_text())
                wallets.append(wallet_data)
                
            return wallets
            
        except Exception as e:
            logger.error(f"Error getting wallets: {e}")
            return []
            
    def verify_chain(self) -> Tuple[bool, str]:
        """Verify blockchain integrity"""
        try:
            blocks_dir = self.chainstate_dir / "blocks"
            
            # Get all blocks sorted by height
            index_files = sorted(
                blocks_dir.glob("*.json"),
                key=lambda x: json.loads(x.read_text())['height']
            )
            
            prev_hash = "0" * 64  # Genesis block prev_hash
            
            for index_file in index_files:
                index_data = json.loads(index_file.read_text())
                block = self.get_block(index_data['hash'])
                
                if not block:
                    return False, f"Block not found: {index_data['hash']}"
                    
                # Verify block link
                if block['prev_hash'] != prev_hash:
                    return False, f"Invalid block link at height {index_data['height']}"
                    
                prev_hash = block['hash']
                
            return True, "Chain verification successful"
            
        except Exception as e:
            logger.error(f"Error verifying chain: {e}")
            return False, str(e)
            
    def cleanup(self):
        """Clean up database"""
        try:
            # Remove all directories
            shutil.rmtree(self.blocks_dir)
            shutil.rmtree(self.chainstate_dir)
            
            # Reinitialize
            self._init_directories()
            
        except Exception as e:
            logger.error(f"Error cleaning up database: {e}") 