"""
Módulo de contratos inteligentes
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import hashlib

class SmartContract:
    """Contrato inteligente base"""
    
    def __init__(
        self,
        address: str,
        owner: str,
        code: str,
        state: Optional[Dict[str, Any]] = None,
        abi: Optional[List[Dict[str, Any]]] = None
    ):
        """Inicializa contrato"""
        self.address = address
        self.owner = owner
        self.code = code
        self.state = state or {}
        self.abi = abi or []
        self.created_at = datetime.now()
        self.hash = self.calculate_hash()
        
    def calculate_hash(self) -> str:
        """Calcula hash do contrato"""
        contract_dict = {
            "address": self.address,
            "owner": self.owner,
            "code": self.code,
            "state": self.state,
            "abi": self.abi,
            "created_at": self.created_at.isoformat()
        }
        contract_string = json.dumps(contract_dict, sort_keys=True)
        return hashlib.sha256(contract_string.encode()).hexdigest()
        
    async def execute(self, method: str, args: List[Any]) -> Any:
        """Executa um método do contrato"""
        # Verifica se método existe
        if not self._validate_method(method, args):
            raise ValueError(f"Método inválido: {method}")
            
        # Executa método
        return await getattr(self, method)(*args)
        
    def get_state(self) -> Dict[str, Any]:
        """Retorna estado do contrato"""
        return self.state.copy()
        
    def set_state(self, state: Dict[str, Any]):
        """Atualiza estado do contrato"""
        self.state = state.copy()
        
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            "address": self.address,
            "owner": self.owner,
            "code": self.code,
            "state": self.state,
            "abi": self.abi,
            "created_at": self.created_at.isoformat(),
            "hash": self.hash
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SmartContract":
        """Cria contrato a partir de dicionário"""
        contract = cls(
            address=data["address"],
            owner=data["owner"],
            code=data["code"],
            state=data["state"],
            abi=data["abi"]
        )
        contract.created_at = datetime.fromisoformat(data["created_at"])
        contract.hash = data["hash"]
        return contract
        
    def _validate_method(self, method: str, args: List[Any]) -> bool:
        """Valida um método e seus argumentos"""
        # Verifica se método existe
        if not hasattr(self, method):
            return False
            
        # Verifica se está no ABI
        method_abi = None
        for abi_entry in self.abi:
            if abi_entry["name"] == method:
                method_abi = abi_entry
                break
                
        if not method_abi:
            return False
            
        # Verifica argumentos
        if len(args) != len(method_abi["inputs"]):
            return False
            
        # TODO: Validar tipos dos argumentos
        
        return True
        
    def __eq__(self, other):
        if not isinstance(other, SmartContract):
            return False
        return self.hash == other.hash
        
    def __hash__(self):
        return hash(self.hash)

__all__ = ["SmartContract"] 