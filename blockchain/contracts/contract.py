"""
Implementação de contratos para blockchain
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .wallet import Wallet
from .region import Region

@dataclass
class DeliveryContract:
    """
    Contrato de entrega
    Base para mineração de tokens laterais
    """
    contract_id: str
    start_coords: Tuple[float, float]
    end_coords: Tuple[float, float]
    executor_address: str
    establishment_address: str
    timestamp: float
    value: float
    region_hash: str
    status: str = 'pending'  # pending, in_progress, completed, failed
    hash: Optional[str] = None
    signatures: Dict[str, str] = None  # address -> signature
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
        if self.signatures is None:
            self.signatures = {}
            
    def calculate_hash(self) -> str:
        """
        Calcula hash única do contrato
        Usa todos os campos exceto signatures
        """
        contract_data = {
            'contract_id': self.contract_id,
            'start_coords': self.start_coords,
            'end_coords': self.end_coords,
            'executor_address': self.executor_address,
            'establishment_address': self.establishment_address,
            'timestamp': self.timestamp,
            'value': self.value,
            'region_hash': self.region_hash,
            'status': self.status
        }
        contract_string = json.dumps(contract_data, sort_keys=True)
        return hashlib.sha256(contract_string.encode()).hexdigest()
        
    def sign(self, wallet: Wallet) -> None:
        """
        Assina contrato com carteira
        Executor e estabelecimento devem assinar
        """
        signature = wallet.signing_key.sign(
            self.hash.encode(),
            hashfunc=hashlib.sha256
        ).hex()
        self.signatures[wallet.address] = signature
        
    def verify_signatures(self) -> bool:
        """
        Verifica assinaturas do contrato
        """
        required = {self.executor_address, self.establishment_address}
        if set(self.signatures.keys()) != required:
            return False
            
        for address, signature in self.signatures.items():
            try:
                # TODO: Recuperar chave pública do endereço
                verifying_key = Wallet.get_verifying_key_from_address(address)
                verifying_key.verify(
                    bytes.fromhex(signature),
                    self.hash.encode(),
                    hashfunc=hashlib.sha256
                )
            except:
                return False
                
        return True

@dataclass
class TokenConversionContract:
    """
    Contrato de conversão entre tokens
    Usado para trocar tokens laterais por centrais
    """
    contract_id: str
    from_address: str
    to_address: str
    amount: float
    from_token_type: str  # 'central' ou 'lateral'
    to_token_type: str
    from_region_hash: Optional[str]  # Obrigatório se from_token_type='lateral'
    to_region_hash: Optional[str]  # Obrigatório se to_token_type='lateral'
    conversion_rate: float
    timestamp: float
    hash: Optional[str] = None
    signature: Optional[str] = None
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
            
    def calculate_hash(self) -> str:
        """Calcula hash única do contrato"""
        contract_data = {
            'contract_id': self.contract_id,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'amount': self.amount,
            'from_token_type': self.from_token_type,
            'to_token_type': self.to_token_type,
            'from_region_hash': self.from_region_hash,
            'to_region_hash': self.to_region_hash,
            'conversion_rate': self.conversion_rate,
            'timestamp': self.timestamp
        }
        contract_string = json.dumps(contract_data, sort_keys=True)
        return hashlib.sha256(contract_string.encode()).hexdigest()
        
    def sign(self, wallet: Wallet) -> None:
        """
        Assina contrato com carteira do remetente
        """
        if wallet.address != self.from_address:
            raise ValueError("Apenas remetente pode assinar")
            
        self.signature = wallet.signing_key.sign(
            self.hash.encode(),
            hashfunc=hashlib.sha256
        ).hex()
        
    def verify(self) -> bool:
        """
        Verifica assinatura e validade do contrato
        """
        if not self.signature:
            return False
            
        try:
            verifying_key = Wallet.get_verifying_key_from_address(self.from_address)
            verifying_key.verify(
                bytes.fromhex(self.signature),
                self.hash.encode(),
                hashfunc=hashlib.sha256
            )
            return True
        except:
            return False

class ContractManager:
    """
    Gerenciador de contratos
    Mantém registro e valida contratos
    """
    
    def __init__(self):
        self.delivery_contracts: Dict[str, DeliveryContract] = {}
        self.conversion_contracts: Dict[str, TokenConversionContract] = {}
        
    def create_delivery_contract(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
        executor_address: str,
        establishment_address: str,
        value: float,
        region_hash: str
    ) -> DeliveryContract:
        """
        Cria novo contrato de entrega
        """
        contract = DeliveryContract(
            contract_id=self._generate_contract_id(),
            start_coords=start_coords,
            end_coords=end_coords,
            executor_address=executor_address,
            establishment_address=establishment_address,
            timestamp=time.time(),
            value=value,
            region_hash=region_hash
        )
        
        self.delivery_contracts[contract.hash] = contract
        return contract
        
    def create_conversion_contract(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        from_token_type: str,
        to_token_type: str,
        from_region_hash: Optional[str],
        to_region_hash: Optional[str],
        conversion_rate: float
    ) -> TokenConversionContract:
        """
        Cria novo contrato de conversão
        """
        contract = TokenConversionContract(
            contract_id=self._generate_contract_id(),
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            from_token_type=from_token_type,
            to_token_type=to_token_type,
            from_region_hash=from_region_hash,
            to_region_hash=to_region_hash,
            conversion_rate=conversion_rate,
            timestamp=time.time()
        )
        
        self.conversion_contracts[contract.hash] = contract
        return contract
        
    def get_delivery_contract(self, contract_hash: str) -> Optional[DeliveryContract]:
        """Retorna contrato de entrega por hash"""
        return self.delivery_contracts.get(contract_hash)
        
    def get_conversion_contract(self, contract_hash: str) -> Optional[TokenConversionContract]:
        """Retorna contrato de conversão por hash"""
        return self.conversion_contracts.get(contract_hash)
        
    def get_contracts_by_region(self, region_hash: str) -> List[DeliveryContract]:
        """Retorna contratos de entrega de uma região"""
        return [
            contract for contract in self.delivery_contracts.values()
            if contract.region_hash == region_hash
        ]
        
    def get_contracts_by_address(
        self,
        address: str,
        contract_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Retorna contratos por endereço
        
        Args:
            address: Endereço da carteira
            contract_type: 'delivery' ou 'conversion' (opcional)
        """
        contracts = []
        
        if contract_type in (None, 'delivery'):
            delivery = [
                contract for contract in self.delivery_contracts.values()
                if address in (contract.executor_address, contract.establishment_address)
            ]
            contracts.extend(delivery)
            
        if contract_type in (None, 'conversion'):
            conversion = [
                contract for contract in self.conversion_contracts.values()
                if address in (contract.from_address, contract.to_address)
            ]
            contracts.extend(conversion)
            
        return contracts
        
    def _generate_contract_id(self) -> str:
        """Gera ID único para contrato"""
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16] 