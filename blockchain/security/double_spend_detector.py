import time
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from enum import Enum

class SpendAttemptType(Enum):
    DOUBLE_SPEND = "DOUBLE_SPEND"
    REPLAY = "REPLAY"
    BALANCE_OVERFLOW = "BALANCE_OVERFLOW"
    NONCE_REUSE = "NONCE_REUSE"

@dataclass
class SpendAttempt:
    tx_id: str
    wallet: str
    attempt_type: SpendAttemptType
    timestamp: float
    details: Dict
    is_malicious: bool

class DoubleSpendDetector:
    def __init__(self):
        self.spent_outputs: Set[str] = set()  # tx_id:output_index
        self.pending_spends: Dict[str, float] = {}  # output -> lock time
        self.suspicious_attempts: List[SpendAttempt] = []
        self.blacklisted_wallets: Set[str] = set()
        self.spend_lock_time = 3600  # 1 hour
        
    def check_spend_attempt(
        self,
        tx_id: str,
        wallet: str,
        inputs: List[Dict],
        amount: float,
        nonce: int
    ) -> Optional[SpendAttempt]:
        """Check for double spend attempts"""
        try:
            # Check if wallet is blacklisted
            if wallet in self.blacklisted_wallets:
                return SpendAttempt(
                    tx_id=tx_id,
                    wallet=wallet,
                    attempt_type=SpendAttemptType.DOUBLE_SPEND,
                    timestamp=time.time(),
                    details={"reason": "Blacklisted wallet"},
                    is_malicious=True
                )
                
            # Check each input
            for input_data in inputs:
                input_id = f"{input_data['tx_id']}:{input_data['index']}"
                
                # Check if already spent
                if input_id in self.spent_outputs:
                    attempt = SpendAttempt(
                        tx_id=tx_id,
                        wallet=wallet,
                        attempt_type=SpendAttemptType.DOUBLE_SPEND,
                        timestamp=time.time(),
                        details={
                            "input": input_id,
                            "reason": "Already spent"
                        },
                        is_malicious=True
                    )
                    self._handle_malicious_attempt(attempt)
                    return attempt
                    
                # Check if pending
                if input_id in self.pending_spends:
                    lock_time = self.pending_spends[input_id]
                    if time.time() - lock_time < self.spend_lock_time:
                        return SpendAttempt(
                            tx_id=tx_id,
                            wallet=wallet,
                            attempt_type=SpendAttemptType.DOUBLE_SPEND,
                            timestamp=time.time(),
                            details={
                                "input": input_id,
                                "reason": "Pending spend"
                            },
                            is_malicious=False
                        )
                        
            # Lock inputs
            for input_data in inputs:
                input_id = f"{input_data['tx_id']}:{input_data['index']}"
                self.pending_spends[input_id] = time.time()
                
            return None
            
        except Exception as e:
            print(f"Error checking spend: {e}")
            return None
            
    def confirm_spend(
        self,
        tx_id: str,
        inputs: List[Dict]
    ):
        """Mark inputs as spent after confirmation"""
        try:
            # Mark inputs as spent
            for input_data in inputs:
                input_id = f"{input_data['tx_id']}:{input_data['index']}"
                self.spent_outputs.add(input_id)
                
                # Remove from pending
                if input_id in self.pending_spends:
                    del self.pending_spends[input_id]
                    
        except Exception as e:
            print(f"Error confirming spend: {e}")
            
    def release_pending(
        self,
        tx_id: str,
        inputs: List[Dict]
    ):
        """Release pending inputs if transaction fails"""
        try:
            for input_data in inputs:
                input_id = f"{input_data['tx_id']}:{input_data['index']}"
                if input_id in self.pending_spends:
                    del self.pending_spends[input_id]
                    
        except Exception as e:
            print(f"Error releasing pending: {e}")
            
    def _handle_malicious_attempt(
        self,
        attempt: SpendAttempt
    ):
        """Handle detected malicious attempt"""
        # Add to suspicious list
        self.suspicious_attempts.append(attempt)
        
        # Blacklist wallet after 3 attempts
        wallet_attempts = len([
            a for a in self.suspicious_attempts
            if (
                a.wallet == attempt.wallet and
                a.is_malicious and
                time.time() - a.timestamp < 86400  # Last 24h
            )
        ])
        
        if wallet_attempts >= 3:
            self.blacklisted_wallets.add(attempt.wallet)
            
    def cleanup_old_pending(self):
        """Cleanup expired pending spends"""
        current_time = time.time()
        expired = [
            input_id
            for input_id, lock_time in self.pending_spends.items()
            if current_time - lock_time > self.spend_lock_time
        ]
        
        for input_id in expired:
            del self.pending_spends[input_id]
            
    def get_wallet_status(self, wallet: str) -> Dict:
        """Get wallet's security status"""
        attempts = [
            a for a in self.suspicious_attempts
            if a.wallet == wallet
        ]
        
        return {
            "is_blacklisted": wallet in self.blacklisted_wallets,
            "total_attempts": len(attempts),
            "malicious_attempts": len([
                a for a in attempts if a.is_malicious
            ]),
            "last_attempt": max(
                [a.timestamp for a in attempts]
                if attempts else [0]
            )
        } 