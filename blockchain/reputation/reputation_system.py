"""
Multi-layer reputation system for LogiChain
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

class ReputationType(Enum):
    POOL = "pool"
    DRIVER = "driver"
    ESTABLISHMENT = "establishment"

@dataclass
class ReputationScore:
    current_score: float  # 0.0 to 1.0
    level: int           # 1 to 5
    total_actions: int
    last_update: datetime
    history: List[Dict]

class PoolReputation:
    """Reputation system for mining/delivery pools"""
    
    # Níveis de Pool
    POOL_LEVELS = {
        1: {"name": "New Pool", "min_score": 0.0, "min_time": 0},
        2: {"name": "Stable Pool", "min_score": 0.6, "min_time": 30},  # 30 dias
        3: {"name": "Trusted Pool", "min_score": 0.75, "min_time": 90},  # 3 meses
        4: {"name": "Elite Pool", "min_score": 0.85, "min_time": 180},  # 6 meses
        5: {"name": "Master Pool", "min_score": 0.95, "min_time": 365}   # 1 ano
    }
    
    def __init__(self):
        self.pools: Dict[str, ReputationScore] = {}
        
    def update_pool_reputation(
        self,
        pool_id: str,
        blocks_mined: int,
        uptime_percentage: float,
        successful_payments: int,
        total_payments: int
    ) -> float:
        """
        Atualiza reputação do pool baseado em:
        - Tempo ativo
        - Blocos minerados
        - Uptime
        - Pagamentos corretos
        """
        if pool_id not in self.pools:
            self.pools[pool_id] = ReputationScore(
                current_score=0.5,  # Score inicial
                level=1,
                total_actions=0,
                last_update=datetime.now(),
                history=[]
            )
            
        pool = self.pools[pool_id]
        
        # Fatores de reputação
        uptime_factor = uptime_percentage / 100.0
        payment_reliability = successful_payments / max(1, total_payments)
        mining_activity = min(1.0, blocks_mined / 1000)  # Normalizado para 1000 blocos
        
        # Calcula novo score
        new_score = (
            uptime_factor * 0.4 +           # 40% uptime
            payment_reliability * 0.4 +      # 40% pagamentos
            mining_activity * 0.2            # 20% atividade
        )
        
        # Atualiza histórico
        pool.history.append({
            "timestamp": datetime.now(),
            "old_score": pool.current_score,
            "new_score": new_score,
            "blocks_mined": blocks_mined,
            "uptime": uptime_percentage,
            "payments": payment_reliability
        })
        
        # Atualiza score e nível
        pool.current_score = new_score
        pool.total_actions += blocks_mined
        pool.last_update = datetime.now()
        
        # Atualiza nível
        self._update_pool_level(pool_id)
        
        return new_score
        
    def _update_pool_level(self, pool_id: str):
        """Atualiza nível do pool baseado em score e tempo"""
        pool = self.pools[pool_id]
        days_active = (datetime.now() - pool.last_update).days
        
        for level in range(5, 0, -1):
            requirements = self.POOL_LEVELS[level]
            if (pool.current_score >= requirements["min_score"] and
                days_active >= requirements["min_time"]):
                pool.level = level
                break

class DriverReputation:
    """Reputation system for drivers"""
    
    # Níveis de Driver
    DRIVER_LEVELS = {
        1: {"name": "Driver Level 1", "min_score": 0.0, "deliveries": 0},
        2: {"name": "Driver Level 2", "min_score": 0.6, "deliveries": 50},
        3: {"name": "Driver Level 3", "min_score": 0.75, "deliveries": 200},
        4: {"name": "Driver Expert", "min_score": 0.85, "deliveries": 500},
        5: {"name": "Logistic Senior", "min_score": 0.95, "deliveries": 1000}
    }
    
    def __init__(self):
        self.drivers: Dict[str, ReputationScore] = {}
        
    def update_driver_reputation(
        self,
        driver_id: str,
        delivery_score: float,
        route_efficiency: float,
        pod_validity: float,
        customer_rating: float
    ) -> float:
        """
        Atualiza reputação do motorista baseado em:
        - Qualidade das entregas
        - Eficiência de rota
        - Validação de POD
        - Avaliação do cliente
        """
        if driver_id not in self.drivers:
            self.drivers[driver_id] = ReputationScore(
                current_score=0.5,
                level=1,
                total_actions=0,
                last_update=datetime.now(),
                history=[]
            )
            
        driver = self.drivers[driver_id]
        
        # Calcula novo score
        new_score = (
            delivery_score * 0.4 +      # 40% entrega
            route_efficiency * 0.2 +     # 20% eficiência
            pod_validity * 0.2 +         # 20% POD
            customer_rating * 0.2        # 20% avaliação
        )
        
        # Atualiza histórico
        driver.history.append({
            "timestamp": datetime.now(),
            "old_score": driver.current_score,
            "new_score": new_score,
            "delivery_score": delivery_score,
            "efficiency": route_efficiency,
            "pod_validity": pod_validity,
            "customer_rating": customer_rating
        })
        
        # Atualiza score e contadores
        driver.current_score = new_score
        driver.total_actions += 1
        driver.last_update = datetime.now()
        
        # Atualiza nível
        self._update_driver_level(driver_id)
        
        return new_score
        
    def _update_driver_level(self, driver_id: str):
        """Atualiza nível do motorista baseado em score e entregas"""
        driver = self.drivers[driver_id]
        
        for level in range(5, 0, -1):
            requirements = self.DRIVER_LEVELS[level]
            if (driver.current_score >= requirements["min_score"] and
                driver.total_actions >= requirements["deliveries"]):
                driver.level = level
                break

class EstablishmentReputation:
    """Reputation system for establishments"""
    
    # Níveis de Estabelecimento
    ESTABLISHMENT_LEVELS = {
        1: {"name": "New Business", "min_score": 0.0, "contracts": 0},
        2: {"name": "Regular Business", "min_score": 0.6, "contracts": 100},
        3: {"name": "Trusted Business", "min_score": 0.75, "contracts": 500},
        4: {"name": "Premium Business", "min_score": 0.85, "contracts": 1000},
        5: {"name": "Elite Business", "min_score": 0.95, "contracts": 5000}
    }
    
    def __init__(self):
        self.establishments: Dict[str, ReputationScore] = {}
        
    def update_establishment_reputation(
        self,
        establishment_id: str,
        contract_completion: float,
        payment_reliability: float,
        ecosystem_contribution: float,
        driver_ratings: float
    ) -> float:
        """
        Atualiza reputação do estabelecimento baseado em:
        - Conclusão de contratos
        - Confiabilidade de pagamentos
        - Contribuição ao ecossistema
        - Avaliações dos motoristas
        """
        if establishment_id not in self.establishments:
            self.establishments[establishment_id] = ReputationScore(
                current_score=0.5,
                level=1,
                total_actions=0,
                last_update=datetime.now(),
                history=[]
            )
            
        establishment = self.establishments[establishment_id]
        
        # Calcula novo score
        new_score = (
            contract_completion * 0.35 +     # 35% contratos
            payment_reliability * 0.35 +     # 35% pagamentos
            ecosystem_contribution * 0.15 +   # 15% ecossistema
            driver_ratings * 0.15            # 15% avaliações
        )
        
        # Atualiza histórico
        establishment.history.append({
            "timestamp": datetime.now(),
            "old_score": establishment.current_score,
            "new_score": new_score,
            "contract_completion": contract_completion,
            "payment_reliability": payment_reliability,
            "ecosystem_contribution": ecosystem_contribution,
            "driver_ratings": driver_ratings
        })
        
        # Atualiza score e contadores
        establishment.current_score = new_score
        establishment.total_actions += 1
        establishment.last_update = datetime.now()
        
        # Atualiza nível
        self._update_establishment_level(establishment_id)
        
        return new_score
        
    def _update_establishment_level(self, establishment_id: str):
        """Atualiza nível do estabelecimento baseado em score e contratos"""
        establishment = self.establishments[establishment_id]
        
        for level in range(5, 0, -1):
            requirements = self.ESTABLISHMENT_LEVELS[level]
            if (establishment.current_score >= requirements["min_score"] and
                establishment.total_actions >= requirements["contracts"]):
                establishment.level = level
                break

class ReputationManager:
    """Gerenciador central de reputação"""
    
    def __init__(self):
        self.pool_reputation = PoolReputation()
        self.driver_reputation = DriverReputation()
        self.establishment_reputation = EstablishmentReputation()
        
    def get_reputation(
        self,
        entity_id: str,
        entity_type: ReputationType
    ) -> Optional[ReputationScore]:
        """Retorna reputação de qualquer entidade"""
        if entity_type == ReputationType.POOL:
            return self.pool_reputation.pools.get(entity_id)
        elif entity_type == ReputationType.DRIVER:
            return self.driver_reputation.drivers.get(entity_id)
        elif entity_type == ReputationType.ESTABLISHMENT:
            return self.establishment_reputation.establishments.get(entity_id)
        return None
        
    def get_level_requirements(
        self,
        entity_type: ReputationType,
        level: int
    ) -> Dict:
        """Retorna requisitos para um nível específico"""
        if entity_type == ReputationType.POOL:
            return self.pool_reputation.POOL_LEVELS.get(level, {})
        elif entity_type == ReputationType.DRIVER:
            return self.driver_reputation.DRIVER_LEVELS.get(level, {})
        elif entity_type == ReputationType.ESTABLISHMENT:
            return self.establishment_reputation.ESTABLISHMENT_LEVELS.get(level, {})
        return {} 