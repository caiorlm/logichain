"""
LogiChain Nonce Manager
Prevents replay attacks and duplicate nonces
"""

from typing import Dict, Optional, Set
from dataclasses import dataclass
from ..storage.database import BlockchainDB

@dataclass
class NonceState:
    """State of account nonces"""
    last_used: int
    pending: Set[int]

class NonceManager:
    """Manages transaction nonces to prevent replays"""
    
    def __init__(self, db: BlockchainDB):
        self.db = db
        self._load_nonces()
        
    def _load_nonces(self):
        """Load nonce states from database"""
        self.nonces: Dict[str, NonceState] = {}
        
        # Get current nonce states
        states = self.db.get_nonce_states()
        
        # Initialize states
        for address, state in states.items():
            self.nonces[address] = NonceState(
                last_used=state.get("last_used", -1),
                pending=set(state.get("pending", []))
            )
            
    def validate_nonce(
        self,
        address: str,
        nonce: int,
        is_pending: bool = True
    ) -> bool:
        """Validate transaction nonce"""
        # Get or create nonce state
        state = self._get_state(address)
        
        # Check if nonce is valid
        if nonce <= state.last_used:
            return False
            
        # Check if nonce is pending
        if nonce in state.pending:
            return False
            
        # Add to pending if requested
        if is_pending:
            state.pending.add(nonce)
            self._save_state(address)
            
        return True
        
    def confirm_nonce(self, address: str, nonce: int):
        """Confirm nonce usage in committed transaction"""
        state = self._get_state(address)
        
        # Update last used nonce
        if nonce > state.last_used:
            state.last_used = nonce
            
        # Remove from pending
        state.pending.discard(nonce)
        
        # Save updated state
        self._save_state(address)
        
    def reject_nonce(self, address: str, nonce: int):
        """Reject pending nonce for failed transaction"""
        state = self._get_state(address)
        
        # Remove from pending
        state.pending.discard(nonce)
        
        # Save updated state
        self._save_state(address)
        
    def get_next_nonce(self, address: str) -> int:
        """Get next valid nonce for address"""
        state = self._get_state(address)
        
        # Start with last used + 1
        next_nonce = state.last_used + 1
        
        # Skip pending nonces
        while next_nonce in state.pending:
            next_nonce += 1
            
        return next_nonce
        
    def _get_state(self, address: str) -> NonceState:
        """Get or create nonce state for address"""
        if address not in self.nonces:
            self.nonces[address] = NonceState(
                last_used=-1,
                pending=set()
            )
            
        return self.nonces[address]
        
    def _save_state(self, address: str):
        """Save nonce state to database"""
        state = self.nonces[address]
        
        self.db.set_nonce_state(
            address,
            {
                "last_used": state.last_used,
                "pending": list(state.pending)
            }
        )
        
    def clear_pending(self, address: str):
        """Clear pending nonces for address"""
        if address in self.nonces:
            self.nonces[address].pending.clear()
            self._save_state(address)
            
    def reset_state(self, address: str):
        """Reset nonce state for address"""
        if address in self.nonces:
            del self.nonces[address]
            self.db.delete_nonce_state(address) 