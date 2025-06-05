"""
Módulo de cálculo de frete com lógica adaptativa baseada em variáveis do mundo real.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional
import json

@dataclass
class FareConstants:
    """Constantes imutáveis do Genesis Block"""
    LITERS_PER_BARREL: int = 159
    MINUTES_PER_HOUR: int = 60
    VOTING_CYCLE_MONTHS: int = 4
    MAX_FAILED_VOTES: int = 5
    MIN_CONSENSUS_PERCENTAGE: float = 0.66

@dataclass
class FareVariables:
    """Variáveis ajustáveis por votação"""
    diesel_barrel_price_gbp: Decimal
    minimum_wage_hour_gbp: Decimal
    default_delivery_time_min: int
    country_tax_rate: Decimal
    fuel_efficiency_kmpl: Decimal
    driver_fixed_profit_gbp: Decimal
    
    @classmethod
    def from_genesis(cls) -> 'FareVariables':
        """Carrega valores iniciais do Genesis Block"""
        return cls(
            diesel_barrel_price_gbp=Decimal('90.00'),
            minimum_wage_hour_gbp=Decimal('11.44'),
            default_delivery_time_min=25,
            country_tax_rate=Decimal('0.28'),
            fuel_efficiency_kmpl=Decimal('10.0'),
            driver_fixed_profit_gbp=Decimal('1.50')
        )
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            "diesel_barrel_price_gbp": str(self.diesel_barrel_price_gbp),
            "minimum_wage_hour_gbp": str(self.minimum_wage_hour_gbp),
            "default_delivery_time_min": self.default_delivery_time_min,
            "country_tax_rate": str(self.country_tax_rate),
            "fuel_efficiency_kmpl": str(self.fuel_efficiency_kmpl),
            "driver_fixed_profit_gbp": str(self.driver_fixed_profit_gbp)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FareVariables':
        """Cria instância a partir de dicionário"""
        return cls(
            diesel_barrel_price_gbp=Decimal(data["diesel_barrel_price_gbp"]),
            minimum_wage_hour_gbp=Decimal(data["minimum_wage_hour_gbp"]),
            default_delivery_time_min=int(data["default_delivery_time_min"]),
            country_tax_rate=Decimal(data["country_tax_rate"]),
            fuel_efficiency_kmpl=Decimal(data["fuel_efficiency_kmpl"]),
            driver_fixed_profit_gbp=Decimal(data["driver_fixed_profit_gbp"])
        )

class FareCalculator:
    """Calculadora de fretes com lógica adaptativa"""
    
    def __init__(self, variables: Optional[FareVariables] = None):
        self.constants = FareConstants()
        self.variables = variables or FareVariables.from_genesis()
    
    def calculate_fuel_cost(self, distance_km: Decimal) -> Decimal:
        """Calcula custo de combustível baseado no preço bruto do barril"""
        # Preço real por litro (do barril bruto)
        price_per_liter = self.variables.diesel_barrel_price_gbp / self.constants.LITERS_PER_BARREL
        
        # Litros usados na entrega
        liters_used = distance_km / self.variables.fuel_efficiency_kmpl
        
        return price_per_liter * liters_used
    
    def calculate_labor_cost(self, delivery_time_min: Optional[int] = None) -> Decimal:
        """Calcula custo do trabalho baseado no salário mínimo"""
        time_min = delivery_time_min or self.variables.default_delivery_time_min
        hours_worked = Decimal(time_min) / self.constants.MINUTES_PER_HOUR
        
        return self.variables.minimum_wage_hour_gbp * hours_worked
    
    def calculate_fare(
        self,
        distance_km: Decimal,
        delivery_time_min: Optional[int] = None
    ) -> Dict[str, Decimal]:
        """Calcula frete total com breakdown de custos"""
        
        # 1. Custo de combustível
        fuel_cost = self.calculate_fuel_cost(distance_km)
        
        # 2. Custo de trabalho
        labor_cost = self.calculate_labor_cost(delivery_time_min)
        
        # 3. Custo base
        base_cost = fuel_cost + labor_cost
        
        # 4. Imposto
        tax_amount = base_cost * self.variables.country_tax_rate
        
        # 5. Frete final com lucro fixo
        total_fare = base_cost + tax_amount + self.variables.driver_fixed_profit_gbp
        
        return {
            "fuel_cost": fuel_cost.quantize(Decimal('0.01')),
            "labor_cost": labor_cost.quantize(Decimal('0.01')),
            "base_cost": base_cost.quantize(Decimal('0.01')),
            "tax_amount": tax_amount.quantize(Decimal('0.01')),
            "fixed_profit": self.variables.driver_fixed_profit_gbp,
            "total_fare": total_fare.quantize(Decimal('0.01'))
        }
    
    def to_json(self) -> str:
        """Serializa calculadora para JSON"""
        return json.dumps({
            "variables": self.variables.to_dict(),
            "constants": vars(self.constants)
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FareCalculator':
        """Cria calculadora a partir de JSON"""
        data = json.loads(json_str)
        variables = FareVariables.from_dict(data["variables"])
        return cls(variables=variables) 