"""
Penalty and reputation management system for LogiChain
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

class ViolationType(Enum):
    ROUTE_DEVIATION = "route_deviation"
    TIME_DELAY = "time_delay"
    CONTRACT_VIOLATION = "contract_violation"
    POD_FAILURE = "pod_failure"
    NETWORK_VIOLATION = "network_violation"

class ViolationSeverity(Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    SEVERE = "severe"
    CRITICAL = "critical"

@dataclass
class Violation:
    type: ViolationType
    severity: ViolationSeverity
    timestamp: float
    details: Dict
    resolved: bool = False

class PenaltySystem:
    """Manages penalties and reputation impacts"""
    
    # Desvio de rota permitido
    ROUTE_FLEXIBILITY_KM = 1.0
    
    # Limites de tempo
    TIME_LIMITS = {
        "light": 30,      # 30 minutos
        "medium": 120,    # 2 horas
        "severe": 240,    # 4 horas
        "critical": 241   # > 4 horas
    }
    
    # Impactos na reputação
    REPUTATION_IMPACTS = {
        ViolationType.ROUTE_DEVIATION: {
            ViolationSeverity.LIGHT: -0.10,    # -10%
            ViolationSeverity.MEDIUM: -0.20,   # -20%
            ViolationSeverity.SEVERE: -0.30,   # -30%
            ViolationSeverity.CRITICAL: -0.50   # -50%
        },
        ViolationType.TIME_DELAY: {
            ViolationSeverity.LIGHT: -0.05,    # -5%
            ViolationSeverity.MEDIUM: -0.15,   # -15%
            ViolationSeverity.SEVERE: -0.30,   # -30%
            ViolationSeverity.CRITICAL: -0.50   # -50%
        },
        ViolationType.CONTRACT_VIOLATION: {
            ViolationSeverity.LIGHT: -0.20,    # -20%
            ViolationSeverity.MEDIUM: -0.30,   # -30%
            ViolationSeverity.SEVERE: -0.40,   # -40%
            ViolationSeverity.CRITICAL: -1.00   # -100%
        },
        ViolationType.POD_FAILURE: {
            ViolationSeverity.LIGHT: -0.10,    # -10%
            ViolationSeverity.MEDIUM: -0.20,   # -20%
            ViolationSeverity.SEVERE: -0.40,   # -40%
            ViolationSeverity.CRITICAL: -0.60   # -60%
        },
        ViolationType.NETWORK_VIOLATION: {
            ViolationSeverity.LIGHT: -0.05,    # -5%
            ViolationSeverity.MEDIUM: -0.10,   # -10%
            ViolationSeverity.SEVERE: -0.20,   # -20%
            ViolationSeverity.CRITICAL: -0.40   # -40%
        }
    }
    
    # Tempos de bloqueio (em horas)
    BLOCK_TIMES = {
        ViolationSeverity.LIGHT: 24,     # 1 dia
        ViolationSeverity.MEDIUM: 72,    # 3 dias
        ViolationSeverity.SEVERE: 168,   # 7 dias
        ViolationSeverity.CRITICAL: -1   # Permanente
    }
    
    def __init__(self):
        self.violations: Dict[str, List[Violation]] = {}  # driver_id -> violations
        self.blocks: Dict[str, datetime] = {}  # driver_id -> block_until
        
    def check_route_deviation(
        self,
        driver_id: str,
        actual_location: Dict[str, float],
        expected_location: Dict[str, float],
        deviation_km: float
    ) -> Tuple[bool, Optional[Violation]]:
        """
        Verifica desvio de rota e aplica penalidades
        """
        if deviation_km <= self.ROUTE_FLEXIBILITY_KM:
            return True, None
            
        # Determina severidade
        severity = self._get_deviation_severity(deviation_km)
        
        # Cria violação
        violation = Violation(
            type=ViolationType.ROUTE_DEVIATION,
            severity=severity,
            timestamp=datetime.now().timestamp(),
            details={
                "actual_location": actual_location,
                "expected_location": expected_location,
                "deviation_km": deviation_km
            }
        )
        
        # Registra violação
        self._record_violation(driver_id, violation)
        
        return False, violation
        
    def check_time_delay(
        self,
        driver_id: str,
        expected_time: datetime,
        actual_time: datetime
    ) -> Tuple[bool, Optional[Violation]]:
        """
        Verifica atraso e aplica penalidades
        """
        delay_minutes = (actual_time - expected_time).total_seconds() / 60
        
        if delay_minutes <= 0:
            return True, None
            
        # Determina severidade
        severity = self._get_delay_severity(delay_minutes)
        
        # Cria violação
        violation = Violation(
            type=ViolationType.TIME_DELAY,
            severity=severity,
            timestamp=datetime.now().timestamp(),
            details={
                "expected_time": expected_time.isoformat(),
                "actual_time": actual_time.isoformat(),
                "delay_minutes": delay_minutes
            }
        )
        
        # Registra violação
        self._record_violation(driver_id, violation)
        
        return False, violation
        
    def check_pod_violation(
        self,
        driver_id: str,
        pod_data: Dict,
        violation_type: str
    ) -> Tuple[bool, Optional[Violation]]:
        """
        Verifica violações de POD
        """
        # Determina severidade
        severity = self._get_pod_severity(violation_type)
        
        # Cria violação
        violation = Violation(
            type=ViolationType.POD_FAILURE,
            severity=severity,
            timestamp=datetime.now().timestamp(),
            details={
                "pod_data": pod_data,
                "violation_type": violation_type
            }
        )
        
        # Registra violação
        self._record_violation(driver_id, violation)
        
        return False, violation
        
    def is_blocked(self, driver_id: str) -> bool:
        """Verifica se motorista está bloqueado"""
        if driver_id not in self.blocks:
            return False
            
        if self.blocks[driver_id] == datetime.max:  # Bloqueio permanente
            return True
            
        return datetime.now() < self.blocks[driver_id]
        
    def get_reputation_impact(
        self,
        violation_type: ViolationType,
        severity: ViolationSeverity
    ) -> float:
        """Retorna impacto na reputação"""
        return self.REPUTATION_IMPACTS[violation_type][severity]
        
    def _record_violation(self, driver_id: str, violation: Violation):
        """Registra violação e aplica bloqueio se necessário"""
        if driver_id not in self.violations:
            self.violations[driver_id] = []
            
        self.violations[driver_id].append(violation)
        
        # Aplica bloqueio
        block_time = self.BLOCK_TIMES[violation.severity]
        if block_time == -1:  # Bloqueio permanente
            self.blocks[driver_id] = datetime.max
        else:
            self.blocks[driver_id] = datetime.now() + timedelta(hours=block_time)
            
    def _get_deviation_severity(self, deviation_km: float) -> ViolationSeverity:
        """Determina severidade do desvio de rota"""
        if deviation_km <= 2:
            return ViolationSeverity.LIGHT
        elif deviation_km <= 3:
            return ViolationSeverity.MEDIUM
        elif deviation_km <= 5:
            return ViolationSeverity.SEVERE
        else:
            return ViolationSeverity.CRITICAL
            
    def _get_delay_severity(self, delay_minutes: float) -> ViolationSeverity:
        """Determina severidade do atraso"""
        if delay_minutes <= self.TIME_LIMITS["light"]:
            return ViolationSeverity.LIGHT
        elif delay_minutes <= self.TIME_LIMITS["medium"]:
            return ViolationSeverity.MEDIUM
        elif delay_minutes <= self.TIME_LIMITS["severe"]:
            return ViolationSeverity.SEVERE
        else:
            return ViolationSeverity.CRITICAL
            
    def _get_pod_severity(self, violation_type: str) -> ViolationSeverity:
        """Determina severidade da violação de POD"""
        severity_map = {
            "invalid": ViolationSeverity.LIGHT,
            "missing": ViolationSeverity.MEDIUM,
            "fraudulent": ViolationSeverity.CRITICAL
        }
        return severity_map.get(violation_type, ViolationSeverity.SEVERE)
        
    def get_driver_violations(
        self,
        driver_id: str,
        violation_type: Optional[ViolationType] = None
    ) -> List[Violation]:
        """Retorna violações do motorista"""
        if driver_id not in self.violations:
            return []
            
        if violation_type:
            return [v for v in self.violations[driver_id] if v.type == violation_type]
        return self.violations[driver_id]
        
    def can_level_up(self, driver_id: str) -> bool:
        """Verifica se motorista pode subir de nível"""
        recent_violations = [
            v for v in self.get_driver_violations(driver_id)
            if (datetime.now().timestamp() - v.timestamp) < 30 * 24 * 3600  # 30 dias
        ]
        
        # Não pode ter violações críticas
        if any(v.severity == ViolationSeverity.CRITICAL for v in recent_violations):
            return False
            
        # Máximo de violações leves permitidas
        light_violations = len([
            v for v in recent_violations
            if v.severity == ViolationSeverity.LIGHT
        ])
        
        return light_violations <= 2  # Máximo 2 violações leves em 30 dias 