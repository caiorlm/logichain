"""
Implementação de transações para blockchain
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
import time

class TransactionType(Enum):
    """
    Tipos de transação suportados
    """
    DELIVERY = "delivery"
    CONTRACT = "contract"
    POOL_REGISTRATION = "pool_registration"
    OPERATOR_REGISTRATION = "operator_registration"

@dataclass
class BaseTransaction:
    """
    Transação base
    """
    tx_type: TransactionType
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def dict(self) -> Dict:
        """
        Converte para dicionário
        """
        return {
            'type': self.tx_type.value,
            'timestamp': self.timestamp
        }

@dataclass
class DeliveryTransaction(BaseTransaction):
    """
    Transação de entrega
    """
    tx_type: TransactionType = TransactionType.DELIVERY
    timestamp: float = None
    contract_id: str = None
    driver_id: str = None
    start_coords: tuple = None
    end_coords: tuple = None
    proof_data: Dict = None

    def dict(self) -> Dict:
        base = super().dict()
        base.update({
            'contract_id': self.contract_id,
            'driver_id': self.driver_id,
            'start_coords': self.start_coords,
            'end_coords': self.end_coords,
            'proof_data': self.proof_data
        })
        return base

@dataclass
class ContractTransaction(BaseTransaction):
    """
    Transação de contrato
    """
    tx_type: TransactionType = TransactionType.CONTRACT
    timestamp: float = None
    contract_id: str = None
    pickup_location: tuple = None
    delivery_location: tuple = None
    metadata: Optional[Dict] = None

    def dict(self) -> Dict:
        base = super().dict()
        base.update({
            'contract_id': self.contract_id,
            'pickup_location': self.pickup_location,
            'delivery_location': self.delivery_location,
            'metadata': self.metadata or {}
        })
        return base

@dataclass
class PoolRegistrationTransaction(BaseTransaction):
    """
    Transação de registro de pool
    """
    tx_type: TransactionType = TransactionType.POOL_REGISTRATION
    timestamp: float = None
    pool_id: str = None
    capacity: int = 0
    location: tuple = None

    def dict(self) -> Dict:
        base = super().dict()
        base.update({
            'pool_id': self.pool_id,
            'capacity': self.capacity,
            'location': self.location
        })
        return base

@dataclass
class OperatorRegistrationTransaction(BaseTransaction):
    """
    Transação de registro de operador
    """
    tx_type: TransactionType = TransactionType.OPERATOR_REGISTRATION
    timestamp: float = None
    operator_id: str = None
    pool_id: str = None
    credentials: Dict = None

    def dict(self) -> Dict:
        base = super().dict()
        base.update({
            'operator_id': self.operator_id,
            'pool_id': self.pool_id,
            'credentials': self.credentials
        })
        return base 