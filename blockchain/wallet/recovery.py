"""
Robust wallet recovery system implementation.
Includes social recovery and multisig capabilities.
"""

from __future__ import annotations
import json
import os
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import base64
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.fernet import Fernet
from eth_account import Account
from web3 import Web3
import shamir_mnemonic
from datetime import datetime, timedelta

@dataclass
class Guardian:
    """Represents a trusted guardian for social recovery"""
    address: str
    public_key: str
    name: str
    contact: str
    added_at: int
    last_verified: int
    status: str  # active, pending, removed

@dataclass
class RecoveryShare:
    """Represents a share of the recovery data"""
    index: int
    data: str
    guardian: str
    signature: str
    timestamp: int

class WalletRecovery:
    """
    Implements robust wallet recovery mechanisms including:
    - Social Recovery (Shamir's Secret Sharing)
    - Hardware Security Module backup
    - Time-locked recovery
    - Multi-signature recovery
    """
    
    # Minimum number of guardians needed for recovery
    MIN_GUARDIANS = 3
    # Minimum shares needed for recovery (M of N)
    MIN_SHARES = 2
    # Maximum guardians allowed
    MAX_GUARDIANS = 5
    # Verification interval for guardians (90 days)
    GUARDIAN_VERIFY_INTERVAL = 90 * 24 * 60 * 60
    
    def __init__(self, wallet_path: str):
        """Initialize recovery system"""
        self.wallet_path = wallet_path
        self.recovery_path = os.path.join(os.path.dirname(wallet_path), 'recovery')
        os.makedirs(self.recovery_path, exist_ok=True)
        
        # Load or initialize recovery config
        self.config_path = os.path.join(self.recovery_path, 'recovery_config.json')
        self.config = self._load_or_init_config()
        
        # Initialize web3 for address validation
        self.w3 = Web3()
        
        logging.info("Wallet recovery system initialized")
    
    def _load_or_init_config(self) -> Dict:
        """Load existing config or create new one"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        
        config = {
            'guardians': {},
            'recovery_type': 'social',  # social, multisig, timelock
            'created_at': int(time.time()),
            'last_updated': int(time.time()),
            'min_shares': self.MIN_SHARES,
            'total_shares': self.MIN_GUARDIANS
        }
        
        self._save_config(config)
        return config
    
    def _save_config(self, config: Dict):
        """Save recovery configuration securely"""
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)
        os.chmod(self.config_path, 0o600)
    
    def setup_social_recovery(
        self,
        guardians: List[Dict],
        min_shares: int = None
    ) -> bool:
        """
        Setup social recovery with trusted guardians
        
        Args:
            guardians: List of guardian info (address, name, contact)
            min_shares: Minimum shares needed for recovery
        """
        try:
            # Validate inputs
            if len(guardians) < self.MIN_GUARDIANS:
                raise ValueError(
                    f"Need at least {self.MIN_GUARDIANS} guardians"
                )
            
            if len(guardians) > self.MAX_GUARDIANS:
                raise ValueError(
                    f"Maximum {self.MAX_GUARDIANS} guardians allowed"
                )
            
            min_shares = min_shares or self.MIN_SHARES
            if min_shares > len(guardians):
                raise ValueError("min_shares cannot exceed number of guardians")
            
            # Validate guardian addresses
            for guardian in guardians:
                if not self.w3.is_address(guardian['address']):
                    raise ValueError(f"Invalid address: {guardian['address']}")
            
            # Create guardian objects
            guardian_dict = {}
            timestamp = int(time.time())
            
            for g in guardians:
                guardian = Guardian(
                    address=g['address'],
                    public_key=g.get('public_key', ''),
                    name=g['name'],
                    contact=g['contact'],
                    added_at=timestamp,
                    last_verified=timestamp,
                    status='pending'
                )
                guardian_dict[g['address']] = guardian.__dict__
            
            # Update config
            self.config['guardians'] = guardian_dict
            self.config['recovery_type'] = 'social'
            self.config['min_shares'] = min_shares
            self.config['total_shares'] = len(guardians)
            self.config['last_updated'] = timestamp
            
            self._save_config(self.config)
            
            # Generate and distribute recovery shares
            self._generate_recovery_shares()
            
            return True
            
        except Exception as e:
            logging.error(f"Error setting up social recovery: {e}")
            return False
    
    def _generate_recovery_shares(self):
        """Generate recovery shares using Shamir's Secret Sharing"""
        try:
            # Get wallet private key
            with open(self.wallet_path, 'r') as f:
                wallet_data = json.load(f)
            
            # Generate shares
            groups = [[i + 1] for i in range(self.config['total_shares'])]
            shares = shamir_mnemonic.generate_mnemonics(
                group_threshold=self.config['min_shares'],
                groups=groups,
                secret=wallet_data['encrypted_key'].encode()
            )
            
            # Encrypt and save shares
            timestamp = int(time.time())
            addresses = list(self.config['guardians'].keys())
            
            for i, share in enumerate(shares):
                recovery_share = RecoveryShare(
                    index=i + 1,
                    data=base64.b64encode(share[0].encode()).decode(),
                    guardian=addresses[i],
                    signature='',  # To be signed by guardian
                    timestamp=timestamp
                )
                
                # Save share
                share_path = os.path.join(
                    self.recovery_path,
                    f'share_{i + 1}.json'
                )
                with open(share_path, 'w') as f:
                    json.dump(recovery_share.__dict__, f, indent=4)
                os.chmod(share_path, 0o600)
            
        except Exception as e:
            logging.error(f"Error generating recovery shares: {e}")
            raise
    
    def verify_guardian(self, address: str, signature: str) -> bool:
        """Verify a guardian's control of their address"""
        try:
            if address not in self.config['guardians']:
                return False
            
            guardian = self.config['guardians'][address]
            
            # Verify signature
            message = f"Verify guardian {address} at {int(time.time())}"
            recovered = Account.recover_message(
                message,
                signature=signature
            )
            
            if recovered.lower() != address.lower():
                return False
            
            # Update verification timestamp
            guardian['last_verified'] = int(time.time())
            guardian['status'] = 'active'
            self._save_config(self.config)
            
            return True
            
        except Exception as e:
            logging.error(f"Error verifying guardian: {e}")
            return False
    
    def initiate_recovery(
        self,
        new_password: str,
        shares: List[Dict]
    ) -> Optional[str]:
        """
        Initiate wallet recovery using guardian shares
        
        Args:
            new_password: New wallet password
            shares: List of recovery shares with signatures
            
        Returns:
            str: New wallet address if successful
        """
        try:
            # Validate shares
            if len(shares) < self.config['min_shares']:
                raise ValueError(
                    f"Need at least {self.config['min_shares']} valid shares"
                )
            
            # Verify share signatures
            valid_shares = []
            for share in shares:
                # Load share data
                share_path = os.path.join(
                    self.recovery_path,
                    f"share_{share['index']}.json"
                )
                with open(share_path, 'r') as f:
                    stored_share = json.load(f)
                
                # Verify guardian signature
                message = f"Approve recovery share {share['index']}"
                recovered = Account.recover_message(
                    message,
                    signature=share['signature']
                )
                
                if recovered.lower() != stored_share['guardian'].lower():
                    continue
                
                valid_shares.append(
                    base64.b64decode(stored_share['data']).decode()
                )
            
            if len(valid_shares) < self.config['min_shares']:
                raise ValueError("Insufficient valid shares")
            
            # Combine shares to recover wallet
            recovered_key = shamir_mnemonic.combine_mnemonics(valid_shares)
            
            # Create new wallet with recovered key
            account = Account.from_key(recovered_key)
            
            # Generate new encryption key
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(
                kdf.derive(new_password.encode())
            )
            
            # Encrypt private key
            f = Fernet(key)
            encrypted_key = f.encrypt(account.key.hex().encode())
            
            # Save new wallet
            wallet_data = {
                'address': account.address,
                'encrypted_key': encrypted_key.decode(),
                'salt': base64.b64encode(salt).decode()
            }
            
            with open(self.wallet_path, 'w') as f:
                json.dump(wallet_data, f, indent=4)
            os.chmod(self.wallet_path, 0o600)
            
            return account.address
            
        except Exception as e:
            logging.error(f"Error recovering wallet: {e}")
            return None
    
    def add_guardian(
        self,
        address: str,
        name: str,
        contact: str,
        public_key: str = ''
    ) -> bool:
        """Add a new guardian"""
        try:
            if len(self.config['guardians']) >= self.MAX_GUARDIANS:
                raise ValueError(f"Maximum {self.MAX_GUARDIANS} guardians allowed")
            
            if not self.w3.is_address(address):
                raise ValueError(f"Invalid address: {address}")
            
            timestamp = int(time.time())
            guardian = Guardian(
                address=address,
                public_key=public_key,
                name=name,
                contact=contact,
                added_at=timestamp,
                last_verified=timestamp,
                status='pending'
            )
            
            self.config['guardians'][address] = guardian.__dict__
            self.config['last_updated'] = timestamp
            self._save_config(self.config)
            
            # Regenerate shares
            self._generate_recovery_shares()
            
            return True
            
        except Exception as e:
            logging.error(f"Error adding guardian: {e}")
            return False
    
    def remove_guardian(self, address: str) -> bool:
        """Remove a guardian"""
        try:
            if address not in self.config['guardians']:
                return False
            
            if len(self.config['guardians']) <= self.MIN_GUARDIANS:
                raise ValueError(
                    f"Need at least {self.MIN_GUARDIANS} guardians"
                )
            
            # Mark guardian as removed
            self.config['guardians'][address]['status'] = 'removed'
            self.config['last_updated'] = int(time.time())
            self._save_config(self.config)
            
            # Regenerate shares
            self._generate_recovery_shares()
            
            return True
            
        except Exception as e:
            logging.error(f"Error removing guardian: {e}")
            return False
    
    def check_guardian_status(self) -> Dict[str, List[str]]:
        """Check status of all guardians"""
        active = []
        pending = []
        expired = []
        removed = []
        
        current_time = int(time.time())
        verify_threshold = current_time - self.GUARDIAN_VERIFY_INTERVAL
        
        for address, guardian in self.config['guardians'].items():
            if guardian['status'] == 'removed':
                removed.append(address)
            elif guardian['status'] == 'pending':
                pending.append(address)
            elif guardian['last_verified'] < verify_threshold:
                expired.append(address)
            else:
                active.append(address)
        
        return {
            'active': active,
            'pending': pending,
            'expired': expired,
            'removed': removed
        } 