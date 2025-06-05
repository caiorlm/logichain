"""
Definições de tipos compartilhados para evitar importações circulares
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class GeoPoint:
    """Ponto geográfico com timestamp"""
    latitude: Decimal
    longitude: Decimal
    timestamp: int
    accuracy: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "lat": str(self.latitude),
            "lng": str(self.longitude),
            "ts": self.timestamp,
            "acc": self.accuracy
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeoPoint':
        return cls(
            latitude=Decimal(data["lat"]),
            longitude=Decimal(data["lng"]),
            timestamp=data["ts"],
            accuracy=data.get("acc")
        )

@dataclass
class SecurityConstants:
    """Constantes de segurança"""
    HASH_ALGORITHM: str = "sha256"
    MIN_KEY_SIZE: int = 2048
    TOKEN_EXPIRY: int = 3600
    MAX_RETRIES: int = 3 