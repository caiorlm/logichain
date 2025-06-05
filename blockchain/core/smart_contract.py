"""
Módulo de contratos inteligentes para logística.
Implementa contratos de entrega com Proof of Delivery.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from .pod import GeoPoint, ProofOfDelivery
from .fare_calculator import FareCalculator
from ..security.crypto import CryptoManager
from .config import SecurityConstants, EnergyType

class ContractStatus(Enum):
    """Status possíveis do contrato"""
    CREATED = "created"
    ACCEPTED = "accepted"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    FAILED = "failed"
    DISPUTED = "disputed"

@dataclass
class DeliveryContract:
    """Contrato inteligente de entrega"""
    contract_id: str
    client_wallet: str
    pickup_point: GeoPoint
    delivery_point: GeoPoint
    value: Decimal
    energy_type: EnergyType
    driver_wallet: Optional[str] = None
    status: ContractStatus = ContractStatus.CREATED
    pod: Optional[Dict] = None
    checkpoints: List[GeoPoint] = None
    created_at: int = None
    completed_at: Optional[int] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = int(datetime.now().timestamp())
        if not self.checkpoints:
            self.checkpoints = []
    
    def to_dict(self) -> Dict:
        """Converte contrato para dicionário"""
        return {
            "contract_id": self.contract_id,
            "client_wallet": self.client_wallet,
            "pickup_point": self.pickup_point.to_dict(),
            "delivery_point": self.delivery_point.to_dict(),
            "value": str(self.value),
            "energy_type": self.energy_type.value,
            "driver_wallet": self.driver_wallet,
            "status": self.status.value,
            "pod": self.pod,
            "checkpoints": [p.to_dict() for p in self.checkpoints],
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DeliveryContract':
        """Cria contrato a partir de dicionário"""
        return cls(
            contract_id=data["contract_id"],
            client_wallet=data["client_wallet"],
            pickup_point=GeoPoint.from_dict(data["pickup_point"]),
            delivery_point=GeoPoint.from_dict(data["delivery_point"]),
            value=Decimal(data["value"]),
            energy_type=EnergyType(data["energy_type"]),
            driver_wallet=data.get("driver_wallet"),
            status=ContractStatus(data["status"]),
            pod=data.get("pod"),
            checkpoints=[GeoPoint.from_dict(p) for p in data.get("checkpoints", [])],
            created_at=data["created_at"],
            completed_at=data.get("completed_at")
        )

class SmartContractManager:
    """Gerenciador de contratos inteligentes"""
    
    def __init__(self):
        self.crypto = CryptoManager()
        self.pod_manager = ProofOfDelivery()
        self.fare_calculator = FareCalculator()
        self.contracts: Dict[str, DeliveryContract] = {}
    
    def create_contract(
        self,
        client_wallet: str,
        pickup_point: GeoPoint,
        delivery_point: GeoPoint,
        energy_type: EnergyType = EnergyType.DIESEL
    ) -> str:
        """Cria novo contrato de entrega"""
        
        # Gera ID único
        contract_id = self.crypto.hash_data({
            "client": client_wallet,
            "pickup": pickup_point.to_dict(),
            "delivery": delivery_point.to_dict(),
            "timestamp": datetime.now().isoformat()
        })[:12]
        
        # Calcula valor do frete
        route_stats = self.pod_manager.calculate_route_stats(
            [pickup_point, delivery_point]
        )
        
        fare = self.fare_calculator.calculate_fare(
            distance_km=Decimal(str(route_stats["total_distance_km"]))
        )
        
        # Cria contrato
        contract = DeliveryContract(
            contract_id=contract_id,
            client_wallet=client_wallet,
            pickup_point=pickup_point,
            delivery_point=delivery_point,
            value=fare["total_fare"],
            energy_type=energy_type
        )
        
        self.contracts[contract_id] = contract
        return contract_id
    
    def accept_contract(
        self,
        contract_id: str,
        driver_wallet: str
    ) -> bool:
        """Aceita contrato de entrega"""
        if contract_id not in self.contracts:
            return False
            
        contract = self.contracts[contract_id]
        
        if contract.status != ContractStatus.CREATED:
            return False
            
        contract.driver_wallet = driver_wallet
        contract.status = ContractStatus.ACCEPTED
        return True
    
    def add_checkpoint(
        self,
        contract_id: str,
        point: GeoPoint,
        driver_wallet: str
    ) -> bool:
        """Adiciona checkpoint ao contrato"""
        if contract_id not in self.contracts:
            return False
            
        contract = self.contracts[contract_id]
        
        if (contract.status not in [ContractStatus.ACCEPTED, ContractStatus.IN_TRANSIT] or
            contract.driver_wallet != driver_wallet):
            return False
        
        contract.checkpoints.append(point)
        contract.status = ContractStatus.IN_TRANSIT
        return True
    
    def complete_contract(
        self,
        contract_id: str,
        driver_wallet: str,
        signature: str
    ) -> bool:
        """Completa contrato com prova de entrega"""
        if contract_id not in self.contracts:
            return False
            
        contract = self.contracts[contract_id]
        
        if (contract.status != ContractStatus.IN_TRANSIT or
            contract.driver_wallet != driver_wallet):
            return False
        
        try:
            # Cria PoD
            pod = self.pod_manager.create_pod(
                contract_id=contract_id,
                driver_wallet=driver_wallet,
                pickup_point=contract.pickup_point,
                delivery_point=contract.delivery_point,
                checkpoints=contract.checkpoints,
                signature=signature
            )
            
            # Verifica PoD
            if not self.pod_manager.verify_pod(pod):
                return False
            
            # Atualiza contrato
            contract.pod = pod
            contract.status = ContractStatus.COMPLETED
            contract.completed_at = int(datetime.now().timestamp())
            
            return True
            
        except Exception:
            return False
    
    def get_contract(self, contract_id: str) -> Optional[Dict]:
        """Retorna dados do contrato"""
        if contract_id not in self.contracts:
            return None
            
        return self.contracts[contract_id].to_dict()
    
    def list_contracts(
        self,
        status: Optional[ContractStatus] = None,
        wallet: Optional[str] = None
    ) -> List[Dict]:
        """Lista contratos filtrados"""
        contracts = []
        
        for contract in self.contracts.values():
            if status and contract.status != status:
                continue
                
            if wallet and (
                contract.client_wallet != wallet and
                contract.driver_wallet != wallet
            ):
                continue
                
            contracts.append(contract.to_dict())
        
        return contracts 