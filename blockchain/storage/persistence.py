import json
import os
from datetime import datetime
from typing import Dict, Optional

class BlockchainPersistence:
    def __init__(self, storage_dir: str = "./data"):
        self.storage_dir = storage_dir
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        """Ensure storage directory exists."""
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "grid"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "blockchain"), exist_ok=True)
    
    def _get_timestamp_str(self) -> str:
        """Get formatted timestamp for filenames."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def save_coordinate_grid(self, grid_data: Dict) -> bool:
        """Save coordinate grid to file."""
        try:
            timestamp = self._get_timestamp_str()
            filename = f"grid_snapshot_{timestamp}.json"
            filepath = os.path.join(self.storage_dir, "grid", filename)
            
            with open(filepath, 'w') as f:
                json.dump(grid_data, f, indent=2)
                
            # Update latest symlink
            latest_link = os.path.join(self.storage_dir, "grid", "latest.json")
            if os.path.exists(latest_link):
                os.remove(latest_link)
            os.symlink(filepath, latest_link)
            
            return True
            
        except Exception as e:
            print(f"Error saving grid: {e}")
            return False
    
    def load_coordinate_grid(self) -> Optional[Dict]:
        """Load latest coordinate grid."""
        try:
            filepath = os.path.join(self.storage_dir, "grid", "latest.json")
            if not os.path.exists(filepath):
                return None
                
            with open(filepath, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"Error loading grid: {e}")
            return None
    
    def save_blockchain_state(self, blockchain_data: Dict) -> bool:
        """Save complete blockchain state."""
        try:
            timestamp = self._get_timestamp_str()
            filename = f"blockchain_snapshot_{timestamp}.json"
            filepath = os.path.join(self.storage_dir, "blockchain", filename)
            
            with open(filepath, 'w') as f:
                json.dump(blockchain_data, f, indent=2)
                
            # Update latest symlink
            latest_link = os.path.join(self.storage_dir, "blockchain", "latest.json")
            if os.path.exists(latest_link):
                os.remove(latest_link)
            os.symlink(filepath, latest_link)
            
            return True
            
        except Exception as e:
            print(f"Error saving blockchain: {e}")
            return False
    
    def load_blockchain_state(self) -> Optional[Dict]:
        """Load latest blockchain state."""
        try:
            filepath = os.path.join(self.storage_dir, "blockchain", "latest.json")
            if not os.path.exists(filepath):
                return None
                
            with open(filepath, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"Error loading blockchain: {e}")
            return None
    
    def save_complete_state(self, blockchain, coordinate_grid) -> bool:
        """Save complete system state."""
        try:
            timestamp = self._get_timestamp_str()
            
            # Save individual components
            grid_success = self.save_coordinate_grid(coordinate_grid.to_dict())
            blockchain_success = self.save_blockchain_state({
                'chain': [block.to_dict() for block in blockchain.chain],
                'transaction_pool': [tx.to_dict() for tx in blockchain.transaction_pool.values()],
                'current_supply': blockchain.current_supply,
                'difficulty': blockchain.difficulty
            })
            
            # Save complete snapshot
            complete_data = {
                'timestamp': timestamp,
                'coordinate_grid': coordinate_grid.to_dict(),
                'blockchain': {
                    'chain': [block.to_dict() for block in blockchain.chain],
                    'transaction_pool': [tx.to_dict() for tx in blockchain.transaction_pool.values()],
                    'current_supply': blockchain.current_supply,
                    'difficulty': blockchain.difficulty
                }
            }
            
            filename = f"complete_snapshot_{timestamp}.json"
            filepath = os.path.join(self.storage_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(complete_data, f, indent=2)
                
            return grid_success and blockchain_success
            
        except Exception as e:
            print(f"Error saving complete state: {e}")
            return False
    
    def load_complete_state(self) -> Optional[Dict]:
        """Load latest complete system state."""
        try:
            # Get latest complete snapshot
            snapshots = [
                f for f in os.listdir(self.storage_dir)
                if f.startswith("complete_snapshot_")
            ]
            
            if not snapshots:
                return None
                
            latest_snapshot = max(snapshots)
            filepath = os.path.join(self.storage_dir, latest_snapshot)
            
            with open(filepath, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"Error loading complete state: {e}")
            return None
    
    def get_snapshot_list(self) -> Dict[str, list]:
        """Get list of all available snapshots."""
        try:
            return {
                'grid_snapshots': sorted([
                    f for f in os.listdir(os.path.join(self.storage_dir, "grid"))
                    if f.startswith("grid_snapshot_")
                ]),
                'blockchain_snapshots': sorted([
                    f for f in os.listdir(os.path.join(self.storage_dir, "blockchain"))
                    if f.startswith("blockchain_snapshot_")
                ]),
                'complete_snapshots': sorted([
                    f for f in os.listdir(self.storage_dir)
                    if f.startswith("complete_snapshot_")
                ])
            }
        except Exception as e:
            print(f"Error getting snapshot list: {e}")
            return {'grid_snapshots': [], 'blockchain_snapshots': [], 'complete_snapshots': []} 