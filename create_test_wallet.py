"""
Script para criar uma carteira de teste
"""

import os
import json
import hashlib
import secrets
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_wallet():
    """Create a new wallet"""
    # Generate private key
    private_key = secrets.token_hex(32)
    
    # Generate public key (simple hash of private key)
    public_key = hashlib.sha256(private_key.encode()).hexdigest()
    
    # Generate address (hash of public key)
    address = "LOGI" + hashlib.sha256(public_key.encode()).hexdigest()[:32]
    
    wallet = {
        'address': address,
        'private_key': private_key,
        'public_key': public_key,
        'balance': 0.0
    }
    
    # Save wallet
    os.makedirs('data/wallets', exist_ok=True)
    wallet_path = os.path.join('data/wallets', f'{address}.json')
    with open(wallet_path, 'w') as f:
        json.dump(wallet, f, indent=2)
        
    logger.info(f"Created new wallet")
    logger.info(f"Address: {address}")
    logger.info(f"Wallet saved to: {wallet_path}")
    
    return wallet

if __name__ == "__main__":
    create_wallet() 