"""
Check wallet balance
"""

import argparse
import logging
import sqlite3
from blockchain.network.config import DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_balance(address: str) -> float:
    """Get balance for address"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all incoming transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE to_address = ?
        """, (address,))
        incoming = cursor.fetchone()[0] or 0
        
        # Get all outgoing transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount + fee), 0)
            FROM transactions
            WHERE from_address = ?
            AND from_address != ?  -- Exclude mining rewards
        """, (address, '0' * 64))
        outgoing = cursor.fetchone()[0] or 0
        
        # Get number of blocks mined
        cursor.execute("""
            SELECT COUNT(*)
            FROM blocks
            WHERE miner_address = ?
        """, (address,))
        blocks_mined = cursor.fetchone()[0] or 0
        
        conn.close()
        
        # Calculate final balance
        balance = incoming - outgoing
        logger.info(f"Address: {address}")
        logger.info(f"Total received: {incoming} LOGI")
        logger.info(f"Total sent: {outgoing} LOGI")
        logger.info(f"Blocks mined: {blocks_mined}")
        logger.info(f"Current balance: {balance} LOGI")
        
        return balance
        
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return 0.0

def main():
    parser = argparse.ArgumentParser(description="Check wallet balance")
    parser.add_argument("--address", type=str, required=True, help="Wallet address to check")
    args = parser.parse_args()
    
    get_balance(args.address)

if __name__ == "__main__":
    main() 