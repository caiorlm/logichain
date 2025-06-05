"""
Reward system to balance penalties in LogiChain
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .penalties import ViolationType, ViolationSeverity, Violation

class RewardSystem:
    """Manages rewards and reputation recovery"""
    
    # Bônus de reputação
    REPUTATION_BONUSES = {
        "perfect_delivery": 0.10,     # +10% por entrega perfeita
        "concatenated": 0.15,         # +15% por rota concatenada
        "positive_rating": 0.05,      # +5% por avaliação positiva
        "early_delivery": 0.08,       # +8% por entrega antecipada
        "efficient_route": 0.12       # +12% por rota otimizada
    }
    
    # Requisitos para recuperação
    RECOVERY_REQUIREMENTS = {
        ViolationSeverity.LIGHT: {
            "perfect_deliveries": 3,
            "days_clean": 7
        },
        ViolationSeverity.MEDIUM: {
            "perfect_deliveries": 5,
            "days_clean": 14
        },
        ViolationSeverity.SEVERE: {
            "perfect_deliveries": 10,
            "days_clean": 30
        }
    }
    
    def __init__(self):
        self.perfect_deliveries: Dict[str, List[datetime]] = {}  # driver_id -> delivery_dates
        self.positive_ratings: Dict[str, List[float]] = {}       # driver_id -> ratings
        self.recovery_progress: Dict[str, Dict] = {}             # driver_id -> progress
        
    def record_perfect_delivery(
        self,
        driver_id: str,
        delivery_data: Dict
    ) -> float:
        """
        Registra uma entrega perfeita e retorna bônus
        """
        if driver_id not in self.perfect_deliveries:
            self.perfect_deliveries[driver_id] = []
            
        self.perfect_deliveries[driver_id].append(datetime.now())
        
        # Calcula bônus total
        bonus = self.REPUTATION_BONUSES["perfect_delivery"]
        
        # Bônus adicional por concatenação
        if delivery_data.get("concatenated", False):
            bonus += self.REPUTATION_BONUSES["concatenated"]
            
        # Bônus por entrega antecipada
        if delivery_data.get("early_delivery", False):
            bonus += self.REPUTATION_BONUSES["early_delivery"]
            
        # Bônus por rota eficiente
        if delivery_data.get("efficient_route", False):
            bonus += self.REPUTATION_BONUSES["efficient_route"]
            
        return bonus
        
    def record_positive_rating(
        self,
        driver_id: str,
        rating: float
    ) -> float:
        """
        Registra avaliação positiva e retorna bônus
        """
        if driver_id not in self.positive_ratings:
            self.positive_ratings[driver_id] = []
            
        self.positive_ratings[driver_id].append(rating)
        
        # Bônus apenas para avaliações 4+ (escala 0-5)
        if rating >= 4.0:
            return self.REPUTATION_BONUSES["positive_rating"]
        return 0.0
        
    def check_recovery_eligibility(
        self,
        driver_id: str,
        violation: Violation
    ) -> bool:
        """
        Verifica se motorista está elegível para recuperação
        """
        if violation.severity == ViolationSeverity.CRITICAL:
            return False  # Não há recuperação de violações críticas
            
        requirements = self.RECOVERY_REQUIREMENTS[violation.severity]
        
        # Verifica entregas perfeitas recentes
        recent_perfect = len([
            d for d in self.perfect_deliveries.get(driver_id, [])
            if (datetime.now() - d).days <= requirements["days_clean"]
        ])
        
        if recent_perfect < requirements["perfect_deliveries"]:
            return False
            
        # Verifica período limpo
        recent_violations = [
            v for v in self.get_recent_violations(driver_id)
            if (datetime.now().timestamp() - v.timestamp) <= requirements["days_clean"] * 86400
        ]
        
        return len(recent_violations) == 0
        
    def calculate_recovery_bonus(
        self,
        driver_id: str,
        violation: Violation
    ) -> float:
        """
        Calcula bônus de recuperação baseado no histórico
        """
        if not self.check_recovery_eligibility(driver_id, violation):
            return 0.0
            
        # Base de recuperação
        base_recovery = abs(violation.severity.value) * 0.5  # 50% da penalidade
        
        # Bônus adicional por histórico positivo
        recent_ratings = [
            r for r in self.positive_ratings.get(driver_id, [])
            if r >= 4.0
        ]
        
        rating_bonus = len(recent_ratings) * 0.02  # +2% por avaliação positiva
        
        return min(base_recovery + rating_bonus, 1.0)  # Máximo 100%
        
    def get_recent_violations(
        self,
        driver_id: str,
        days: int = 30
    ) -> List[Violation]:
        """
        Retorna violações recentes do motorista
        """
        # Implementação depende do sistema de penalidades
        pass
        
    def update_recovery_progress(
        self,
        driver_id: str,
        violation: Violation,
        progress: float
    ):
        """
        Atualiza progresso de recuperação
        """
        if driver_id not in self.recovery_progress:
            self.recovery_progress[driver_id] = {}
            
        violation_key = f"{violation.type.value}_{violation.timestamp}"
        self.recovery_progress[driver_id][violation_key] = progress
        
    def get_recovery_progress(
        self,
        driver_id: str,
        violation: Optional[Violation] = None
    ) -> Dict:
        """
        Retorna progresso de recuperação
        """
        if driver_id not in self.recovery_progress:
            return {}
            
        if violation:
            violation_key = f"{violation.type.value}_{violation.timestamp}"
            return {
                violation_key: self.recovery_progress[driver_id].get(violation_key, 0.0)
            }
            
        return self.recovery_progress[driver_id] 