"""
LogiChain OfflineMesh Module
Optional module for offline blockchain operations
"""

import logging
from typing import Dict, Optional, List
from .config import OfflineMeshConfig
from .hybrid_manager import HybridMeshManager
from .validator import OfflineMeshValidator
from .lora import LoRaManager
from ..core.blockchain import Blockchain
from ..core.transaction import Transaction
from ..core.wallet import Wallet

logger = logging.getLogger(__name__)

class OfflineMeshModule:
    """Optional module for offline blockchain operations"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        config: OfflineMeshConfig
    ):
        self.blockchain = blockchain
        self.config = config
        self.enabled = False
        self.validator: Optional[OfflineMeshValidator] = None
        self.lora: Optional[LoRaManager] = None
        self.manager: Optional[HybridMeshManager] = None
        
    def start(self) -> bool:
        """Start offline mesh module"""
        # Check if module is enabled
        if not self.config.enabled:
            logger.info("OfflineMesh module is disabled")
            return False
            
        # Validate configuration
        if not self.config.validate():
            logger.error("Invalid OfflineMesh configuration")
            return False
            
        try:
            # Initialize components
            self._init_components()
            
            # Start mesh network
            if self.manager:
                self.manager.start()
                
            self.enabled = True
            logger.info("OfflineMesh module started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start OfflineMesh module: {str(e)}")
            self.stop()
            return False
            
    def stop(self):
        """Stop offline mesh module"""
        try:
            # Stop mesh network
            if self.manager:
                self.manager.stop()
                
            self.enabled = False
            self.validator = None
            self.lora = None
            self.manager = None
            
            logger.info("OfflineMesh module stopped")
            
        except Exception as e:
            logger.error(f"Error stopping OfflineMesh module: {str(e)}")
            
    def create_offline_transaction(
        self,
        wallet: Wallet,
        recipient: str,
        amount: float,
        location: Optional[str] = None
    ) -> Optional[str]:
        """Create offline transaction"""
        if not self.enabled or not self.validator:
            logger.error("OfflineMesh module is not enabled")
            return None
            
        try:
            # Check wallet stake
            if not self._check_wallet_stake(wallet.address):
                logger.error(f"Insufficient stake for wallet {wallet.address}")
                return None
                
            # Create transaction
            tx = Transaction(
                sender=wallet.address,
                recipient=recipient,
                amount=amount,
                timestamp=self.blockchain.get_current_timestamp()
            )
            
            # Sign transaction
            tx.sign(wallet.private_key)
            
            # Create contract
            genesis_hash, _ = self.validator.broadcast_handshake(
                contract_id=tx.hash,
                value=amount,
                location=location
            )
            
            return genesis_hash
            
        except Exception as e:
            logger.error(f"Failed to create offline transaction: {str(e)}")
            return None
            
    def validate_offline_transaction(
        self,
        contract_id: str,
        wallet: Wallet,
        location: Optional[str] = None
    ) -> bool:
        """Validate offline transaction"""
        if not self.enabled or not self.validator:
            logger.error("OfflineMesh module is not enabled")
            return False
            
        try:
            # Check wallet stake
            if not self._check_wallet_stake(wallet.address):
                logger.error(f"Insufficient stake for wallet {wallet.address}")
                return False
                
            # Create validation snapshot
            snapshot = self.validator.receive_handshake(
                contract_id=contract_id,
                genesis_hash=contract_id,  # Use contract ID as genesis hash
                value=0.0,  # Value not needed for validation
                location=location
            )
            
            return bool(snapshot)
            
        except Exception as e:
            logger.error(f"Failed to validate offline transaction: {str(e)}")
            return False
            
    def get_pending_contracts(self) -> List[Dict]:
        """Get pending offline contracts"""
        if not self.enabled or not self.validator:
            return []
            
        try:
            return [
                contract.to_dict()
                for contract in self.validator.pending_contracts.values()
            ]
        except Exception as e:
            logger.error(f"Failed to get pending contracts: {str(e)}")
            return []
            
    def _init_components(self):
        """Initialize module components"""
        # Create validator
        self.validator = OfflineMeshValidator(
            db=self.blockchain.db,
            node_id=self.blockchain.node_id,
            private_key=self.blockchain.private_key,
            contracts_dir="offline_contracts"
        )
        
        # Create LoRa manager
        self.lora = LoRaManager(
            node_id=self.blockchain.node_id,
            port=self.config.lora_port,
            baudrate=self.config.lora_baudrate
        )
        
        # Create hybrid manager
        self.manager = HybridMeshManager(
            validator=self.validator,
            lora=self.lora,
            is_bridge=self._is_bridge_node()
        )
        
    def _check_wallet_stake(self, address: str) -> bool:
        """Check if wallet has sufficient stake"""
        try:
            balance = self.blockchain.get_balance(address)
            return balance >= self.config.min_stake_amount
        except Exception:
            return False
            
    def _is_bridge_node(self) -> bool:
        """Check if node should act as bridge"""
        try:
            # Check if node has internet connection
            return self.blockchain.is_online()
        except Exception:
            return False 