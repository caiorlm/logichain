"""
Script para enviar LOGI entre carteiras
"""

import os
import json
import sqlite3
import time
import hashlib
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"

def load_wallet(address):
    """Load wallet from file"""
    wallet_path = os.path.join('data/wallets', f'{address}.json')
    if not os.path.exists(wallet_path):
        raise ValueError(f"Wallet not found: {address}")
        
    with open(wallet_path) as f:
        return json.load(f)

def get_balance(address):
    """Get wallet balance"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get incoming transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE to_address = ?
        """, (address,))
        incoming = cursor.fetchone()[0] or 0
        
        # Get outgoing transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE from_address = ?
            AND from_address != ?
        """, (address, '0' * 64))
        outgoing = cursor.fetchone()[0] or 0
        
        # Get mining rewards
        cursor.execute("""
            SELECT COUNT(*) * 50.0
            FROM blocks
            WHERE miner_address = ?
        """, (address,))
        mining_rewards = cursor.fetchone()[0] or 0
        
        return incoming - outgoing + mining_rewards
        
    finally:
        conn.close()

def send_logi(from_address, to_address, amount):
    """Send LOGI from one wallet to another"""
    # Check balance
    balance = get_balance(from_address)
    if balance < amount:
        raise ValueError(f"Insufficient balance: {balance} LOGI")
    
    # Create transaction
    tx = {
        'from_address': from_address,
        'to_address': to_address,
        'amount': amount,
        'timestamp': time.time(),
        'nonce': int(time.time() * 1000)
    }
    
    # Sign transaction (simplified for testing)
    message = json.dumps(tx, sort_keys=True)
    signature = hashlib.sha256(message.encode()).hexdigest()
    tx['signature'] = signature
    
    # Save to mempool
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create transaction hash
        tx_hash = hashlib.sha256(message.encode()).hexdigest()
        
        # Convert transaction to JSON
        raw_transaction = json.dumps(tx)
        
        cursor.execute("""
            INSERT INTO mempool (
                tx_hash, raw_transaction, timestamp, fee, status
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            tx_hash,
            raw_transaction,
            tx['timestamp'],
            0.0,  # fee
            'pending'  # status
        ))
        conn.commit()
        
        logger.info(f"Transaction added to mempool:")
        logger.info(f"Hash: {tx_hash}")
        logger.info(f"From: {from_address}")
        logger.info(f"To: {to_address}")
        logger.info(f"Amount: {amount} LOGI")
        
    finally:
        conn.close()

if __name__ == "__main__":
    # Create new wallet
    logger.info("Creating new wallet...")
    from create_test_wallet import create_wallet
    new_wallet = create_wallet()
    
    # Get miner wallet
    miner_address = None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT miner_address FROM blocks LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    
    if result:
        miner_address = result[0]
        logger.info(f"Found miner wallet: {miner_address}")
        
        # Send 100 LOGI
        logger.info(f"Sending 100 LOGI from miner to new wallet...")
        send_logi(miner_address, new_wallet['address'], 100.0)
        logger.info("Transaction sent! The miner will process it in the next block.") 