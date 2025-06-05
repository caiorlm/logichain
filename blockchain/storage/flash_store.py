import json
import time
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

class FlashStore:
    def __init__(self, base_path: str = "data/blocks"):
        self.path = Path(base_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.backup_path = Path(f"{base_path}_backup")
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
    def save_block(self, block: Dict) -> bool:
        """Save block to storage with backup"""
        try:
            # Create block filename
            block_file = self.path / f"{block['index']:06d}.json"
            
            # Add metadata
            block['stored_at'] = int(time.time())
            block['storage_hash'] = self._calculate_block_hash(block)
            
            # Save primary copy
            block_file.write_text(json.dumps(block, indent=2))
            
            # Save backup copy
            backup_file = self.backup_path / f"{block['index']:06d}.json"
            shutil.copy2(block_file, backup_file)
            
            return True
        except Exception as e:
            print(f"Error saving block: {e}")
            return False
            
    def load_block(self, index: int) -> Optional[Dict]:
        """Load specific block by index"""
        try:
            block_file = self.path / f"{index:06d}.json"
            if not block_file.exists():
                # Try backup
                block_file = self.backup_path / f"{index:06d}.json"
                
            if block_file.exists():
                block = json.loads(block_file.read_text())
                if self._verify_block_hash(block):
                    return block
        except Exception as e:
            print(f"Error loading block {index}: {e}")
        return None
        
    def load_all_blocks(self) -> List[Dict]:
        """Load all blocks in order"""
        blocks = []
        for block_file in sorted(self.path.glob("*.json")):
            try:
                block = json.loads(block_file.read_text())
                if self._verify_block_hash(block):
                    blocks.append(block)
            except Exception as e:
                print(f"Error loading {block_file}: {e}")
                
        return blocks
        
    def get_latest_block(self) -> Optional[Dict]:
        """Get most recent block"""
        try:
            latest = max(self.path.glob("*.json"), key=lambda p: int(p.stem))
            block = json.loads(latest.read_text())
            if self._verify_block_hash(block):
                return block
        except Exception as e:
            print(f"Error getting latest block: {e}")
        return None
        
    def create_backup(self) -> bool:
        """Create full backup of blockchain"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.backup_path / f"backup_{timestamp}"
            backup_dir.mkdir(parents=True)
            
            for block_file in self.path.glob("*.json"):
                shutil.copy2(block_file, backup_dir)
                
            return True
        except Exception as e:
            print(f"Backup failed: {e}")
            return False
            
    def verify_chain(self) -> bool:
        """Verify entire blockchain integrity"""
        blocks = self.load_all_blocks()
        
        for i in range(len(blocks)):
            # Verify block hash
            if not self._verify_block_hash(blocks[i]):
                return False
                
            # Verify chain linkage
            if i > 0:
                if blocks[i]['previous_hash'] != blocks[i-1]['storage_hash']:
                    return False
                    
        return True
        
    def _calculate_block_hash(self, block: Dict) -> str:
        """Calculate hash of block contents"""
        # Remove storage metadata before hashing
        block_copy = block.copy()
        block_copy.pop('stored_at', None)
        block_copy.pop('storage_hash', None)
        
        block_str = json.dumps(block_copy, sort_keys=True)
        return hashlib.sha256(block_str.encode()).hexdigest()
        
    def _verify_block_hash(self, block: Dict) -> bool:
        """Verify block hash matches contents"""
        if 'storage_hash' not in block:
            return False
            
        stored_hash = block['storage_hash']
        calculated_hash = self._calculate_block_hash(block)
        
        return stored_hash == calculated_hash 