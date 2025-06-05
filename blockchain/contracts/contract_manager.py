"""
LogiChain Contract Manager with Reputation System Integration
"""

from typing import Dict, List, Optional, Tuple
import logging
import time
from datetime import datetime, timedelta
import asyncio
from .smart_contract import SmartContract, ContractRequirements, ContractStatus
from ..reputation.reputation_system import ReputationManager

class ContractManager:
    """Manages contracts with reputation requirements"""
    
    def __init__(self, reputation_manager: ReputationManager):
        self.contracts: Dict[str, SmartContract] = {}
        self.reputation_manager = reputation_manager
        self.adjustment_task = None
        
    async def start_adjustment_task(self):
        """Start background task to check for reputation adjustments"""
        async def check_adjustments():
            while True:
                try:
                    for contract in self.contracts.values():
                        if contract.check_reputation_adjustment():
                            contract.adjust_reputation_requirements()
                    await asyncio.sleep(60)  # Check every minute
                except Exception as e:
                    logging.error(f"Error in adjustment task: {e}")
                    await asyncio.sleep(60)
                    
        if not self.adjustment_task:
            self.adjustment_task = asyncio.create_task(check_adjustments())
            
    def create_contract(
        self,
        client_address: str,
        value: float,
        pickup_location: Dict[str, float],
        delivery_location: Dict[str, float],
        min_driver_reputation: float = 0.0,
        min_pool_reputation: float = 0.0,
        min_establishment_reputation: float = 0.0,
        allow_adjustment: bool = True,
        adjustment_delay: int = 60,
        adjustment_steps: int = 2
    ) -> SmartContract:
        """
        Create new contract with reputation requirements
        """
        contract_id = self._generate_contract_id(client_address)
        
        requirements = ContractRequirements(
            min_driver_reputation=min_driver_reputation,
            min_pool_reputation=min_pool_reputation,
            min_establishment_reputation=min_establishment_reputation,
            allow_reputation_adjustment=allow_adjustment,
            reputation_adjustment_delay=adjustment_delay,
            reputation_adjustment_steps=adjustment_steps
        )
        
        contract = SmartContract(
            contract_id=contract_id,
            client_address=client_address,
            value=value,
            pickup_location=pickup_location,
            delivery_location=delivery_location,
            requirements=requirements,
            reputation_manager=self.reputation_manager
        )
        
        self.contracts[contract_id] = contract
        logging.info(f"Created contract {contract_id} with reputation requirements")
        
        return contract
        
    def accept_contract(
        self,
        contract_id: str,
        driver_address: str,
        pool_address: str
    ) -> bool:
        """
        Accept contract if reputation requirements are met
        """
        contract = self.contracts.get(contract_id)
        if not contract:
            logging.error(f"Contract {contract_id} not found")
            return False
            
        return contract.accept_contract(driver_address, pool_address)
        
    def get_available_contracts(
        self,
        driver_address: str,
        pool_address: str
    ) -> List[SmartContract]:
        """
        Get list of contracts available for driver/pool based on reputation
        """
        available = []
        for contract in self.contracts.values():
            if (contract.status == ContractStatus.PENDING and
                contract.can_accept(driver_address, pool_address)):
                available.append(contract)
        return available
        
    def get_contract(self, contract_id: str) -> Optional[SmartContract]:
        """Get contract by ID"""
        return self.contracts.get(contract_id)
        
    def get_contracts_by_status(self, status: ContractStatus) -> List[SmartContract]:
        """Get all contracts with given status"""
        return [c for c in self.contracts.values() if c.status == status]
        
    def get_contracts_by_client(self, client_address: str) -> List[SmartContract]:
        """Get all contracts for a client"""
        return [c for c in self.contracts.values() if c.client_address == client_address]
        
    def get_contracts_by_driver(self, driver_address: str) -> List[SmartContract]:
        """Get all contracts for a driver"""
        return [c for c in self.contracts.values() if c.driver_address == driver_address]
        
    def _generate_contract_id(self, client_address: str) -> str:
        """Generate unique contract ID"""
        timestamp = int(time.time())
        return f"{client_address[:8]}-{timestamp}"
        
    def cleanup_old_contracts(self, max_age_days: int = 30):
        """Remove old completed/failed contracts"""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        to_remove = []
        
        for contract_id, contract in self.contracts.items():
            if (contract.status in (ContractStatus.COMPLETED, ContractStatus.FAILED) and
                contract.completion_time and
                contract.completion_time < cutoff):
                to_remove.append(contract_id)
                
        for contract_id in to_remove:
            del self.contracts[contract_id]
            logging.info(f"Removed old contract {contract_id}")
            
    def to_dict(self) -> Dict:
        """Convert manager state to dictionary"""
        return {
            "contracts": {
                cid: contract.to_dict()
                for cid, contract in self.contracts.items()
            }
        }
        
    @classmethod
    def from_dict(
        cls,
        data: Dict,
        reputation_manager: ReputationManager
    ) -> 'ContractManager':
        """Create manager from dictionary"""
        manager = cls(reputation_manager)
        
        for contract_data in data["contracts"].values():
            contract = SmartContract.from_dict(
                contract_data,
                reputation_manager=reputation_manager
            )
            manager.contracts[contract.contract_id] = contract
            
        return manager 