"""
Classe para manipulação de coordenadas geográficas
"""

from dataclasses import dataclass
from typing import Tuple, Dict

@dataclass
class Coordinates:
    """
    Representa um par de coordenadas (latitude, longitude)
    """
    latitude: float
    longitude: float

    def to_tuple(self) -> Tuple[float, float]:
        """
        Converte para tupla (lat, lon)
        """
        return (self.latitude, self.longitude)

    @staticmethod
    def from_tuple(coords: Tuple[float, float]) -> 'Coordinates':
        """
        Cria coordenadas a partir de tupla
        """
        return Coordinates(coords[0], coords[1])

    def __str__(self) -> str:
        return f"({self.latitude}, {self.longitude})"

    def to_dict(self) -> Dict[str, float]:
        """
        Converte para dicionário para serialização JSON
        """
        return {
            'latitude': self.latitude,
            'longitude': self.longitude
        }

    def __repr__(self) -> str:
        return str(self.to_tuple()) 