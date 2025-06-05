"""
Implementação de regiões geográficas para blockchain
"""

import hashlib
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import geohash

@dataclass
class Region:
    """
    Região geográfica para tokens laterais
    Usa geohash para indexação espacial
    """
    geohash: str  # Geohash da região
    center_coords: Tuple[float, float]  # Coordenadas centrais
    bounds: Tuple[float, float, float, float]  # min_lat, min_lon, max_lat, max_lon
    hash: Optional[str] = None  # Hash única da região
    parent_hash: Optional[str] = None  # Hash da região pai (hierarquia)
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
            
    def calculate_hash(self) -> str:
        """
        Calcula hash única da região
        Usa geohash e bounds para garantir unicidade
        """
        region_data = {
            'geohash': self.geohash,
            'center_coords': self.center_coords,
            'bounds': self.bounds,
            'parent_hash': self.parent_hash
        }
        region_string = json.dumps(region_data, sort_keys=True)
        return hashlib.sha256(region_string.encode()).hexdigest()

class RegionManager:
    """
    Gerenciador de regiões geográficas
    Mantém índice espacial e hierarquia de regiões
    """
    
    def __init__(self, precision: int = 6):
        """
        Args:
            precision: Precisão do geohash (padrão 6 = ~1.2km²)
        """
        self.precision = precision
        self.regions: Dict[str, Region] = {}  # hash -> Region
        self.spatial_index: Dict[str, str] = {}  # geohash -> hash
        
    def create_region(
        self,
        coords: Tuple[float, float],
        parent_hash: Optional[str] = None
    ) -> Region:
        """
        Cria nova região a partir de coordenadas
        
        Args:
            coords: (latitude, longitude)
            parent_hash: Hash da região pai (opcional)
        """
        # Gera geohash
        lat, lon = coords
        gh = geohash.encode(lat, lon, self.precision)
        
        # Calcula bounds
        bounds = geohash.decode_exactly(gh)
        center = (bounds[0], bounds[1])
        bounds = (bounds[2], bounds[3], bounds[4], bounds[5])
        
        # Cria região
        region = Region(
            geohash=gh,
            center_coords=center,
            bounds=bounds,
            parent_hash=parent_hash
        )
        
        # Registra nos índices
        self.regions[region.hash] = region
        self.spatial_index[gh] = region.hash
        
        return region
        
    def get_region(
        self,
        coords: Optional[Tuple[float, float]] = None,
        region_hash: Optional[str] = None
    ) -> Optional[Region]:
        """
        Retorna região por coordenadas ou hash
        """
        if coords:
            lat, lon = coords
            gh = geohash.encode(lat, lon, self.precision)
            region_hash = self.spatial_index.get(gh)
            
        return self.regions.get(region_hash)
        
    def get_nearby_regions(
        self,
        coords: Tuple[float, float],
        radius: float = 5.0
    ) -> List[Region]:
        """
        Retorna regiões próximas às coordenadas
        
        Args:
            coords: (latitude, longitude)
            radius: Raio em km
        """
        lat, lon = coords
        
        # Calcula box aproximada para o raio
        lat_offset = radius / 111.0  # 1 grau ~= 111km
        lon_offset = radius / (111.0 * abs(lat))
        
        min_lat = lat - lat_offset
        max_lat = lat + lat_offset
        min_lon = lon - lon_offset
        max_lon = lon + lon_offset
        
        # Encontra geohashes na box
        nearby = []
        for gh in geohash.expand(geohash.encode(lat, lon, self.precision)):
            region_hash = self.spatial_index.get(gh)
            if region_hash:
                region = self.regions[region_hash]
                if (min_lat <= region.center_coords[0] <= max_lat and
                    min_lon <= region.center_coords[1] <= max_lon):
                    nearby.append(region)
                    
        return nearby
        
    def get_parent_chain(self, region: Region) -> List[Region]:
        """
        Retorna cadeia de regiões pai até a raiz
        """
        chain = []
        current = region
        
        while current.parent_hash:
            parent = self.regions.get(current.parent_hash)
            if not parent:
                break
            chain.append(parent)
            current = parent
            
        return chain
        
    def calculate_conversion_rate(
        self,
        from_region: Region,
        to_region: Optional[Region] = None
    ) -> float:
        """
        Calcula taxa de conversão entre tokens de regiões
        
        Args:
            from_region: Região de origem
            to_region: Região de destino (None = token central)
            
        Returns:
            Taxa de conversão (1 token origem = X tokens destino)
        """
        # Se destino é token central, usa distância até raiz
        if not to_region:
            distance = len(self.get_parent_chain(from_region))
            # Taxa diminui com distância da raiz
            return 1.0 / (2 ** distance)
            
        # Se entre regiões, usa distância entre elas
        from_chain = self.get_parent_chain(from_region)
        to_chain = self.get_parent_chain(to_region)
        
        # Encontra ancestral comum
        common_ancestor = None
        for ancestor in from_chain:
            if ancestor in to_chain:
                common_ancestor = ancestor
                break
                
        if not common_ancestor:
            return 0.0  # Não podem trocar tokens
            
        # Taxa baseada na distância até ancestral comum
        from_distance = from_chain.index(common_ancestor)
        to_distance = to_chain.index(common_ancestor)
        
        return 1.0 / (2 ** (from_distance + to_distance))
        
    def export_region_metrics(self) -> Dict:
        """
        Exporta métricas das regiões
        """
        return {
            'total_regions': len(self.regions),
            'regions_by_level': self._count_regions_by_level(),
            'conversion_rates': self._calculate_all_conversion_rates()
        }
        
    def _count_regions_by_level(self) -> Dict[int, int]:
        """Conta regiões por nível na hierarquia"""
        counts = {}
        for region in self.regions.values():
            level = len(self.get_parent_chain(region))
            counts[level] = counts.get(level, 0) + 1
        return counts
        
    def _calculate_all_conversion_rates(self) -> Dict[str, float]:
        """Calcula taxas de conversão para token central"""
        rates = {}
        for region in self.regions.values():
            rates[region.hash] = self.calculate_conversion_rate(region)
        return rates 