"""
Script to monitor miner wallet and blocks
"""

import json
import os
import sqlite3
import logging
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
BLOCKS_FILE = "data/blockchain/blocks.json"
MINER_ADDRESS = "LOGI46d9d74d564d25b45127046a9526314e"

def check_miner_balance():
    """Check miner wallet balance"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get mining rewards (incoming from system)
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE to_address = ?
            AND from_address = ?
        """, (MINER_ADDRESS, '0' * 64))
        mining_rewards = cursor.fetchone()[0] or 0
        
        # Get other incoming transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE to_address = ?
            AND from_address != ?
        """, (MINER_ADDRESS, '0' * 64))
        incoming = cursor.fetchone()[0] or 0
        
        # Get outgoing transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE from_address = ?
        """, (MINER_ADDRESS,))
        outgoing = cursor.fetchone()[0] or 0
        
        conn.close()
        
        logger.info("\nMiner Wallet Balance:")
        logger.info(f"Address: {MINER_ADDRESS}")
        logger.info(f"Mining Rewards: {mining_rewards} LOGI")
        logger.info(f"Other Incoming: {incoming} LOGI")
        logger.info(f"Total Outgoing: {outgoing} LOGI")
        logger.info(f"Current Balance: {mining_rewards + incoming - outgoing} LOGI")
        
    except Exception as e:
        logger.error(f"Error checking balance: {e}")

def check_recent_blocks(minutes=5):
    """Check recently mined blocks"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get recent blocks
        recent_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        cursor.execute("""
            SELECT hash, previous_hash, timestamp, nonce, difficulty
            FROM blocks
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (recent_time,))
        
        blocks = cursor.fetchall()
        
        logger.info(f"\nBlocks mined in last {minutes} minutes: {len(blocks)}")
        
        if blocks:
            logger.info("\nRecent blocks:")
            for block in blocks:
                logger.info(f"Hash: {block[0][:16]}...")
                logger.info(f"Previous: {block[1][:16]}...")
                logger.info(f"Time: {block[2]}")
                logger.info(f"Nonce: {block[3]}")
                logger.info(f"Difficulty: {block[4]}\n")
                
        # Get mining rate
        if len(blocks) > 1:
            first_time = datetime.fromisoformat(blocks[-1][2])
            last_time = datetime.fromisoformat(blocks[0][2])
            duration = (last_time - first_time).total_seconds()
            rate = len(blocks) / (duration / 60) if duration > 0 else 0
            logger.info(f"Mining rate: {rate:.2f} blocks/minute")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Error checking blocks: {e}")

def monitor_mining(interval=10, duration=60):
    """Monitor mining activity"""
    logger.info(f"Starting mining monitor for {duration} seconds...")
    
    start_time = time.time()
    while time.time() - start_time < duration:
        check_miner_balance()
        check_recent_blocks(minutes=1)
        time.sleep(interval)
        logger.info("\n" + "="*50 + "\n")

if __name__ == "__main__":
    # Initial check
    check_miner_balance()
    check_recent_blocks()
    
    # Monitor mining
    print("\nDo you want to monitor mining activity? (y/n)")
    if input().lower() == 'y':
        monitor_mining() 