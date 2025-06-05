"""
Módulo de oracle de preços
"""

from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import threading
import statistics
import logging

from ..security import SecurityConfig

class PriceOracle:
    """Oracle de preços"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        """Inicializa oracle"""
        self.config = config or SecurityConfig()
        
        # Estado
        self.prices: Dict[str, float] = {}
        self.price_feeds: Dict[str, Dict[str, float]] = {}
        self.last_update: Dict[str, datetime] = {}
        self.trusted_feeds: Set[str] = set()
        
        # Lock
        self.lock = threading.RLock()
        
    async def get_price(self, pair: str) -> float:
        """Retorna preço de um par"""
        with self.lock:
            # Verifica se preço existe
            if pair not in self.prices:
                raise ValueError(f"Par não encontrado: {pair}")
                
            # Verifica se preço está atualizado
            if self._is_price_stale(pair):
                await self._update_price(pair)
                
            return self.prices[pair]
            
    async def add_price_feed(
        self,
        feed_id: str,
        pair: str,
        price: float
    ) -> bool:
        """Adiciona feed de preço"""
        with self.lock:
            # Verifica se feed é confiável
            if feed_id not in self.trusted_feeds:
                return False
                
            # Adiciona preço
            if pair not in self.price_feeds:
                self.price_feeds[pair] = {}
            self.price_feeds[pair][feed_id] = price
            
            # Atualiza preço agregado
            await self._update_price(pair)
            
            return True
            
    def add_trusted_feed(self, feed_id: str):
        """Adiciona feed confiável"""
        with self.lock:
            self.trusted_feeds.add(feed_id)
            
    def remove_trusted_feed(self, feed_id: str):
        """Remove feed confiável"""
        with self.lock:
            self.trusted_feeds.remove(feed_id)
            
            # Remove preços do feed
            for pair in self.price_feeds:
                if feed_id in self.price_feeds[pair]:
                    del self.price_feeds[pair][feed_id]
                    
    async def _update_price(self, pair: str):
        """Atualiza preço agregado"""
        with self.lock:
            if pair not in self.price_feeds:
                return
                
            # Obtém preços dos feeds
            prices = list(self.price_feeds[pair].values())
            
            # Verifica número mínimo de feeds
            if len(prices) < self.config.min_price_feeds:
                raise ValueError(
                    f"Feeds insuficientes para {pair}: "
                    f"{len(prices)} < {self.config.min_price_feeds}"
                )
                
            # Calcula mediana
            median = statistics.median(prices)
            
            # Verifica desvio máximo
            if pair in self.prices:
                old_price = self.prices[pair]
                deviation = abs(median - old_price) / old_price
                if deviation > self.config.max_price_deviation:
                    logging.warning(
                        f"Desvio de preço muito alto para {pair}: "
                        f"{deviation:.2%}"
                    )
                    return
                    
            # Atualiza preço
            self.prices[pair] = median
            self.last_update[pair] = datetime.now()
            
    def _is_price_stale(self, pair: str) -> bool:
        """Verifica se preço está desatualizado"""
        if pair not in self.last_update:
            return True
            
        age = datetime.now() - self.last_update[pair]
        return age.total_seconds() > self.config.price_update_interval
        
    def get_feed_count(self, pair: str) -> int:
        """Retorna número de feeds para um par"""
        return len(self.price_feeds.get(pair, {}))
        
    def get_trusted_feeds(self) -> Set[str]:
        """Retorna feeds confiáveis"""
        return self.trusted_feeds.copy()
        
    def get_pairs(self) -> List[str]:
        """Retorna pares disponíveis"""
        return list(self.prices.keys())
        
    def shutdown(self):
        """Desliga o oracle"""
        with self.lock:
            self.prices.clear()
            self.price_feeds.clear()
            self.last_update.clear()
            self.trusted_feeds.clear()

__all__ = ["PriceOracle"] 