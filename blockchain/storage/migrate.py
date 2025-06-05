"""
Migration script to transfer data from SQLite to the new storage system
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional
from .chaindb import ChainDB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StorageMigration:
    """Handles migration from SQLite to file-based storage"""
    
    def __init__(self, sqlite_path: str, data_dir: str):
        self.sqlite_path = sqlite_path
        self.chaindb = ChainDB(data_dir)
        
    def migrate(self) -> bool:
        """Perform the migration"""
        try:
            logger.info("Starting migration from SQLite to file-based storage...")
            
            # Connect to SQLite database
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Migrate blocks
            self._migrate_blocks(cursor)
            
            # Migrate transactions
            self._migrate_transactions(cursor)
            
            # Migrate wallets
            self._migrate_wallets(cursor)
            
            conn.close()
            
            logger.info("Migration completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
            
    def _migrate_blocks(self, cursor: sqlite3.Cursor):
        """Migrate blocks from SQLite"""
        logger.info("Migrating blocks...")
        
        try:
            # Get all blocks
            cursor.execute("""
                SELECT hash, prev_hash, timestamp, nonce, difficulty, merkle_root, height
                FROM blocks
                ORDER BY height ASC
            """)
            
            blocks = cursor.fetchall()
            logger.info(f"Found {len(blocks)} blocks to migrate")
            
            for block in blocks:
                block_data = {
                    'hash': block[0],
                    'prev_hash': block[1],
                    'timestamp': block[2],
                    'nonce': block[3],
                    'difficulty': block[4],
                    'merkle_root': block[5],
                    'height': block[6]
                }
                
                # Get transactions for this block
                cursor.execute("""
                    SELECT hash, from_address, to_address, amount, timestamp
                    FROM transactions
                    WHERE block_hash = ?
                """, (block[0],))
                
                transactions = []
                for tx in cursor.fetchall():
                    tx_data = {
                        'hash': tx[0],
                        'from_address': tx[1],
                        'to_address': tx[2],
                        'amount': float(tx[3]),
                        'timestamp': tx[4],
                        'block_hash': block[0]
                    }
                    transactions.append(tx_data)
                    
                block_data['transactions'] = transactions
                
                # Store block in new system
                if not self.chaindb.store_block(block_data):
                    raise Exception(f"Failed to store block {block[0]}")
                    
                # Store transactions separately
                for tx in transactions:
                    if not self.chaindb.store_transaction(tx):
                        raise Exception(f"Failed to store transaction {tx['hash']}")
                        
            logger.info("Blocks migration completed")
            
        except Exception as e:
            logger.error(f"Error migrating blocks: {e}")
            raise
            
    def _migrate_transactions(self, cursor: sqlite3.Cursor):
        """Migrate pending transactions from SQLite"""
        logger.info("Migrating pending transactions...")
        
        try:
            # Get pending transactions (not in any block)
            cursor.execute("""
                SELECT hash, from_address, to_address, amount, timestamp
                FROM transactions
                WHERE block_hash IS NULL
            """)
            
            transactions = cursor.fetchall()
            logger.info(f"Found {len(transactions)} pending transactions to migrate")
            
            for tx in transactions:
                tx_data = {
                    'hash': tx[0],
                    'from_address': tx[1],
                    'to_address': tx[2],
                    'amount': float(tx[3]),
                    'timestamp': tx[4]
                }
                
                if not self.chaindb.store_transaction(tx_data):
                    raise Exception(f"Failed to store transaction {tx[0]}")
                    
            logger.info("Pending transactions migration completed")
            
        except Exception as e:
            logger.error(f"Error migrating transactions: {e}")
            raise
            
    def _migrate_wallets(self, cursor: sqlite3.Cursor):
        """Migrate wallets from SQLite"""
        logger.info("Migrating wallets...")
        
        try:
            # Get all wallets
            cursor.execute("""
                SELECT address, public_key, balance
                FROM wallets
            """)
            
            wallets = cursor.fetchall()
            logger.info(f"Found {len(wallets)} wallets to migrate")
            
            for wallet in wallets:
                wallet_data = {
                    'address': wallet[0],
                    'public_key': wallet[1],
                    'balance': float(wallet[2])
                }
                
                if not self.chaindb.store_wallet(wallet_data):
                    raise Exception(f"Failed to store wallet {wallet[0]}")
                    
            logger.info("Wallets migration completed")
            
        except Exception as e:
            logger.error(f"Error migrating wallets: {e}")
            raise
            
def migrate_storage(sqlite_path: str, data_dir: str) -> bool:
    """
    Migrate data from SQLite to the new storage system
    
    Args:
        sqlite_path: Path to SQLite database file
        data_dir: Directory for new storage system
        
    Returns:
        bool: True if migration successful, False otherwise
    """
    migration = StorageMigration(sqlite_path, data_dir)
    return migration.migrate() 