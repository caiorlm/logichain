"""
Módulo de coordenadas geográficas
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict

@dataclass
class Coordinates:
    """Representa coordenadas geográficas"""
    latitude: float
    longitude: float
    timestamp: Optional[float] = None
    
    def to_tuple(self) -> Tuple[float, float]:
        """Converte para tupla (lat, lng)"""
        return (self.latitude, self.longitude)
        
    @staticmethod
    def from_tuple(coords: Tuple[float, float], timestamp: Optional[float] = None) -> 'Coordinates':
        """Cria coordenadas a partir de tupla"""
        return Coordinates(
            latitude=coords[0],
            longitude=coords[1],
            timestamp=timestamp
        )
        
    def is_valid(self) -> bool:
        """Verifica se coordenadas são válidas"""
        return (
            -90 <= self.latitude <= 90 and
            -180 <= self.longitude <= 180
        )
        
    def __str__(self) -> str:
        return f"({self.latitude}, {self.longitude})"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Coordinates':
        """Create from dictionary"""
        return cls(
            latitude=data["latitude"],
            longitude=data["longitude"]
        ) 