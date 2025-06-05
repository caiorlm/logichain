from typing import Dict, List, Optional
import hashlib
import json
from datetime import datetime

class CoordinateGrid:
    """Manages the grid of all possible coordinates and their associated data."""
    
    def __init__(self):
        self.grid: Dict[str, Dict] = {}
        self._initialize_grid()
        
    def _initialize_grid(self):
        """Initialize the grid with all possible integer coordinate combinations."""
        for lat in range(-90, 91):  # 181 valores
            for lng in range(-180, 181):  # 361 valores
                coord_hash = self._generate_coord_hash(lat, lng)
                self.grid[coord_hash] = {
                    "coord_hash": coord_hash,
                    "lat": lat,
                    "lng": lng,
                    "contracts": [],
                    "statistics": {
                        "total_contracts": 0,
                        "successful_deliveries": 0,
                        "average_delivery_time": 0,
                        "last_activity": None
                    }
                }
    
    def _generate_coord_hash(self, lat: int, lng: int) -> str:
        """Generate a unique hash for a coordinate pair."""
        coord_str = f"{lat},{lng}"
        return hashlib.sha256(coord_str.encode()).hexdigest()
    
    def get_coordinate(self, lat: int, lng: int) -> Optional[Dict]:
        """Get coordinate data by latitude and longitude."""
        coord_hash = self._generate_coord_hash(lat, lng)
        return self.grid.get(coord_hash)
    
    def add_contract(self, lat: int, lng: int, contract_data: Dict) -> bool:
        """Add a new contract to a coordinate."""
        coord_data = self.get_coordinate(lat, lng)
        if not coord_data:
            return False
            
        coord_data["contracts"].append(contract_data)
        coord_data["statistics"]["total_contracts"] += 1
        coord_data["statistics"]["last_activity"] = datetime.now().timestamp()
        return True
    
    def update_contract(self, lat: int, lng: int, contract_hash: str, updates: Dict) -> bool:
        """Update an existing contract at a coordinate."""
        coord_data = self.get_coordinate(lat, lng)
        if not coord_data:
            return False
            
        for contract in coord_data["contracts"]:
            if contract["contract_hash"] == contract_hash:
                contract.update(updates)
                if updates.get("status") == "COMPLETED":
                    self._update_statistics(coord_data, contract)
                return True
        return False
    
    def _update_statistics(self, coord_data: Dict, contract: Dict):
        """Update coordinate statistics when a contract is completed."""
        stats = coord_data["statistics"]
        stats["successful_deliveries"] += 1
        
        # Calculate delivery time
        start_time = contract["timestamps"]["initiated"]
        end_time = contract["timestamps"]["completed"]
        delivery_time = end_time - start_time
        
        # Update average delivery time
        current_avg = stats["average_delivery_time"]
        total_deliveries = stats["successful_deliveries"]
        stats["average_delivery_time"] = (
            (current_avg * (total_deliveries - 1) + delivery_time) / total_deliveries
        )
        
        stats["last_activity"] = end_time
    
    def get_contracts_by_status(self, lat: int, lng: int, status: str) -> List[Dict]:
        """Get all contracts with a specific status at a coordinate."""
        coord_data = self.get_coordinate(lat, lng)
        if not coord_data:
            return []
            
        return [
            contract for contract in coord_data["contracts"]
            if contract["status"] == status
        ]
    
    def to_dict(self) -> Dict:
        """Convert the entire grid to a dictionary for storage."""
        return self.grid
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CoordinateGrid':
        """Create a CoordinateGrid instance from stored data."""
        grid = cls()
        grid.grid = data
        return grid 