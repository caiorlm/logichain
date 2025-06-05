"""
LogiChain Bridge Custody Service
Manages secure custody of bridge funds
"""

from typing import Dict, Optional, List
import time
from dataclasses import dataclass
import logging
from .bridge_service import ChainType
from .chain_adapters import ChainAdapter, AdapterFactory
from ..security.crypto import KeyManager

@dataclass
class CustodyWallet:
    """Bridge custody wallet"""
    chain: ChainType
    address: str
    balance: float
    last_update: int

class CustodyService:
    """Manages bridge custody wallets and security"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.wallets: Dict[ChainType, CustodyWallet] = {}
        self.adapters: Dict[ChainType, ChainAdapter] = {}
        self.min_balances: Dict[ChainType, float] = {
            ChainType.ETHEREUM: 0.1,
            ChainType.BINANCE: 1.0,
            ChainType.POLYGON: 100.0,
            ChainType.AVALANCHE: 10.0
        }
        
    def initialize_chain(
        self,
        chain: ChainType,
        rpc_url: str
    ) -> bool:
        """Initialize custody for chain"""
        try:
            # Generate or load bridge wallet
            wallet = self._get_or_create_wallet(chain)
            
            # Create chain adapter
            adapter = AdapterFactory.create_adapter(
                chain,
                rpc_url,
                wallet.address
            )
            
            self.adapters[chain] = adapter
            self.wallets[chain] = wallet
            
            logging.info(f"Initialized custody for {chain.value}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize custody for {chain.value}: {e}")
            return False
            
    def _get_or_create_wallet(self, chain: ChainType) -> CustodyWallet:
        """Get existing or create new custody wallet"""
        # Check if wallet exists
        wallet_key = f"bridge_wallet_{chain.value}"
        address = self.key_manager.get_address(wallet_key)
        
        if not address:
            # Generate new wallet
            address = self.key_manager.generate_wallet(wallet_key)
            
        return CustodyWallet(
            chain=chain,
            address=address,
            balance=0.0,
            last_update=int(time.time())
        )
        
    def update_balances(self):
        """Update balances for all custody wallets"""
        for chain, wallet in self.wallets.items():
            adapter = self.adapters.get(chain)
            if adapter:
                try:
                    balance = adapter.get_balance(wallet.address)
                    wallet.balance = balance
                    wallet.last_update = int(time.time())
                except Exception as e:
                    logging.error(f"Failed to update balance for {chain.value}: {e}")
                    
    def check_liquidity(self, chain: ChainType, amount: float) -> bool:
        """Check if custody has sufficient liquidity"""
        wallet = self.wallets.get(chain)
        if not wallet:
            return False
            
        min_balance = self.min_balances.get(chain, 0)
        return wallet.balance >= (amount + min_balance)
        
    def verify_transaction(
        self,
        chain: ChainType,
        tx_hash: str,
        required_confirmations: Optional[int] = None
    ) -> bool:
        """Verify transaction on external chain"""
        adapter = self.adapters.get(chain)
        if not adapter:
            return False
            
        try:
            # Verify transaction exists
            if not adapter.verify_transaction(tx_hash):
                return False
                
            # Check confirmations if required
            if required_confirmations:
                confirmations = adapter.get_confirmations(tx_hash)
                if confirmations < required_confirmations:
                    return False
                    
            return True
            
        except Exception as e:
            logging.error(f"Failed to verify transaction {tx_hash}: {e}")
            return False
            
    def create_transaction(
        self,
        chain: ChainType,
        to_address: str,
        amount: float
    ) -> Optional[str]:
        """Create transaction on external chain"""
        adapter = self.adapters.get(chain)
        if not adapter:
            return None
            
        # Check liquidity
        if not self.check_liquidity(chain, amount):
            logging.error(f"Insufficient liquidity for {chain.value}")
            return None
            
        try:
            tx_hash = adapter.create_transaction(to_address, amount)
            if tx_hash:
                # Update balance
                wallet = self.wallets[chain]
                wallet.balance -= amount
                wallet.last_update = int(time.time())
                
            return tx_hash
            
        except Exception as e:
            logging.error(f"Failed to create transaction on {chain.value}: {e}")
            return None
            
    def get_wallet(self, chain: ChainType) -> Optional[CustodyWallet]:
        """Get custody wallet for chain"""
        return self.wallets.get(chain)
        
    def get_balances(self) -> Dict[ChainType, float]:
        """Get balances for all custody wallets"""
        return {
            chain: wallet.balance
            for chain, wallet in self.wallets.items()
        }
        
    def get_status(self) -> Dict:
        """Get custody service status"""
        return {
            "wallets": len(self.wallets),
            "adapters": len(self.adapters),
            "balances": self.get_balances(),
            "min_balances": self.min_balances
        } 