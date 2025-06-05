"""
Blockchain Database Initialization Script
"""

import os
import sqlite3
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"

def init_database():
    """Initialize database with all required tables"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create blocks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                block_index INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                previous_hash TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 4,
                nonce INTEGER NOT NULL DEFAULT 0,
                miner_address TEXT,
                mining_reward REAL DEFAULT 50.0,
                merkle_root TEXT,
                version INTEGER DEFAULT 1,
                state TEXT DEFAULT 'confirmed',
                total_transactions INTEGER DEFAULT 0,
                size_bytes INTEGER DEFAULT 0,
                UNIQUE(block_index)
            )
        """)
        
        # Create transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                block_hash TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                from_address TEXT NOT NULL,
                to_address TEXT,
                amount REAL NOT NULL DEFAULT 0.0,
                timestamp REAL NOT NULL,
                nonce INTEGER NOT NULL DEFAULT 0,
                signature TEXT,
                data TEXT,
                status TEXT DEFAULT 'confirmed',
                fee REAL DEFAULT 0.0,
                FOREIGN KEY (block_hash) REFERENCES blocks(hash)
            )
        """)
        
        # Create mempool table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mempool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                raw_transaction TEXT NOT NULL,
                timestamp REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                UNIQUE(tx_hash)
            )
        """)
        
        # Create wallets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                public_key TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                created_at REAL NOT NULL,
                last_updated REAL NOT NULL
            )
        """)
        
        # Create peers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                port INTEGER NOT NULL,
                last_seen REAL NOT NULL,
                status TEXT DEFAULT 'active',
                version TEXT,
                blocks_height INTEGER DEFAULT 0
            )
        """)
        
        conn.commit()
        logger.info("Database tables created successfully")
        
    finally:
        cursor.close()
        conn.close()

def create_genesis_block():
    """Create genesis block if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if genesis block exists
        cursor.execute("SELECT COUNT(*) FROM blocks WHERE block_index = 0")
        if cursor.fetchone()[0] == 0:
            # Create genesis block
            zero_hash = '0' * 64
            timestamp = time.time()
            
            cursor.execute("""
                INSERT INTO blocks (
                    hash, block_index, timestamp, previous_hash,
                    difficulty, nonce, mining_reward, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                zero_hash,  # hash
                0,  # block_index
                timestamp,  # timestamp
                zero_hash,  # previous_hash
                4,  # difficulty
                0,  # nonce
                0.0,  # mining_reward
                'confirmed'  # state
            ))
            
            conn.commit()
            logger.info("Genesis block created successfully")
        else:
            logger.info("Genesis block already exists")
            
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Initializing blockchain database...")
    init_database()
    
    logger.info("Creating genesis block...")
    create_genesis_block()
    
    logger.info("Blockchain initialized successfully!")

if __name__ == "__main__":
    main() 