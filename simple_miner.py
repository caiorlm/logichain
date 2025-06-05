"""
Simple blockchain miner implementation
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DIFFICULTY = 4
BLOCK_REWARD = 50.0
DB_PATH = "data/blockchain/chain.db"
BLOCKS_FILE = "data/blockchain/blocks.json"

class SimpleMiner:
    def __init__(self):
        self.target = '0' * DIFFICULTY
        self.blocks = []
        self.init_database()
        self.load_blocks()
        
    def init_database(self):
        """Initialize SQLite database"""
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Create tables
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
            
            conn.commit()
            conn.close()
            logger.info("Database initialized")
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
            
    def load_blocks(self):
        """Load blocks from file"""
        try:
            if os.path.exists(BLOCKS_FILE):
                with open(BLOCKS_FILE, 'r') as f:
                    self.blocks = json.load(f)
                logger.info(f"Loaded {len(self.blocks)} blocks")
        except Exception as e:
            logger.error(f"Error loading blocks: {e}")
            
    def save_blocks(self):
        """Save blocks to file"""
        try:
            os.makedirs(os.path.dirname(BLOCKS_FILE), exist_ok=True)
            with open(BLOCKS_FILE, 'w') as f:
                json.dump(self.blocks, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving blocks: {e}")
            
    def save_to_db(self, block):
        """Save block to database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Save block
            cursor.execute("""
                INSERT INTO blocks (
                    hash, block_index, timestamp, previous_hash,
                    difficulty, nonce, miner_address, mining_reward,
                    merkle_root, version, state, total_transactions,
                    size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block['hash'],
                len(self.blocks),  # block_index
                block['timestamp'],
                block['previous_hash'],
                DIFFICULTY,  # difficulty
                block['nonce'],
                block['transactions'][0]['to'],  # miner_address
                BLOCK_REWARD,  # mining_reward
                '',  # merkle_root
                1,  # version
                'confirmed',  # state
                len(block['transactions']),  # total_transactions
                len(str(block))  # size_bytes
            ))
            
            # Save transactions
            for tx in block['transactions']:
                cursor.execute("""
                    INSERT INTO transactions (
                        tx_hash, block_hash, tx_type, from_address,
                        to_address, amount, timestamp, nonce,
                        signature, data, status, fee
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    hashlib.sha256(json.dumps(tx).encode()).hexdigest(),
                    block['hash'],
                    'mining_reward' if tx['from'] == '0' * 64 else 'transfer',
                    tx['from'],
                    tx['to'],
                    tx['amount'],
                    tx['timestamp'],
                    0,  # nonce
                    '',  # signature
                    None,  # data
                    'confirmed',  # status
                    0.0  # fee
                ))
                
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            
    def create_block(self, previous_hash, nonce, transactions):
        """Create a new block"""
        block = {
            'timestamp': time.time(),
            'transactions': transactions,
            'previous_hash': previous_hash,
            'nonce': nonce,
            'hash': None
        }
        block['hash'] = self.calculate_hash(block)
        return block
        
    def calculate_hash(self, block):
        """Calculate block hash"""
        block_string = f"{block['timestamp']}{block['transactions']}{block['previous_hash']}{block['nonce']}"
        return hashlib.sha256(block_string.encode()).hexdigest()
        
    def mine_block(self, transactions):
        """Mine a new block"""
        # Get pending transactions from mempool
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT tx_hash, raw_transaction FROM mempool WHERE status = 'pending'")
            pending_txs = cursor.fetchall()
            
            # Parse pending transactions
            for tx_hash, raw_tx in pending_txs:
                tx_data = json.loads(raw_tx)
                
                # Verify sender has enough balance
                if tx_data['from_address'] != '0' * 64:  # Not a mining reward
                    balance = self.get_balance(tx_data['from_address'])
                    if balance < tx_data['amount']:
                        logger.warning(f"Insufficient balance for transaction {tx_hash}")
                        continue
                
                transactions.append({
                    'from': tx_data['from_address'],
                    'to': tx_data['to_address'],
                    'amount': tx_data['amount'],
                    'timestamp': tx_data['timestamp'],
                    'nonce': tx_data['nonce'],
                    'signature': tx_data.get('signature', '')
                })
                
                # Mark transaction as processing
                cursor.execute("""
                    UPDATE mempool 
                    SET status = 'processing' 
                    WHERE tx_hash = ?
                """, (tx_hash,))
            
            conn.commit()
            
        finally:
            conn.close()
        
        previous_hash = self.blocks[-1]['hash'] if self.blocks else '0' * 64
        nonce = 0
        
        logger.info("Starting mining process...")
        start_time = time.time()
        
        while True:
            block = self.create_block(previous_hash, nonce, transactions)
            if block['hash'].startswith(self.target):
                end_time = time.time()
                mining_time = end_time - start_time
                logger.info(f"Block mined! Time taken: {mining_time:.2f} seconds")
                logger.info(f"Block hash: {block['hash']}")
                logger.info(f"Nonce: {nonce}")
                
                # Save block
                self.blocks.append(block)
                self.save_blocks()
                self.save_to_db(block)
                
                # Clear processed transactions from mempool
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM mempool WHERE status = 'processing'")
                conn.commit()
                conn.close()
                
                return block
            nonce += 1
            
    def get_balance(self, address):
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
            
            # Get outgoing transactions
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE from_address = ?
                AND from_address != ?
            """, (address, '0' * 64))
            outgoing = cursor.fetchone()[0] or 0
            
            # Get blocks mined
            cursor.execute("""
                SELECT COUNT(*)
                FROM blocks
                WHERE miner_address = ?
            """, (address,))
            blocks_mined = cursor.fetchone()[0] or 0
            
            # Calculate mining rewards
            mining_rewards = blocks_mined * BLOCK_REWARD
            
            balance = incoming - outgoing
            
            logger.info(f"Address: {address}")
            logger.info(f"Total received: {incoming} LOGI")
            logger.info(f"Total sent: {outgoing} LOGI")
            logger.info(f"Mining rewards: {mining_rewards} LOGI")
            logger.info(f"Blocks mined: {blocks_mined}")
            logger.info(f"Current balance: {balance} LOGI")
            
            return balance
            
        finally:
            conn.close()

def main():
    try:
        # Initialize miner
        miner = SimpleMiner()
        
        # Create or load wallet
        wallet_path = "data/wallets/miner_wallet.json"
        if os.path.exists(wallet_path):
            with open(wallet_path, 'r') as f:
                wallet = json.load(f)
        else:
            wallet = {
                'address': hashlib.sha256(os.urandom(32)).hexdigest(),
                'private_key': hashlib.sha256(os.urandom(32)).hexdigest()
            }
            os.makedirs(os.path.dirname(wallet_path), exist_ok=True)
            with open(wallet_path, 'w') as f:
                json.dump(wallet, f, indent=2)
                
        logger.info(f"Mining with address: {wallet['address']}")
        
        # Start mining loop
        while True:
            try:
                # Create mining reward transaction
                reward_tx = {
                    'from': '0' * 64,  # System reward
                    'to': wallet['address'],
                    'amount': BLOCK_REWARD,
                    'timestamp': time.time()
                }
                
                # Mine block
                mined_block = miner.mine_block([reward_tx])
                
                # Get updated balance
                balance = miner.get_balance(wallet['address'])
                logger.info(f"Current balance: {balance} LOGI")
                logger.info(f"Total blocks: {len(miner.blocks)}")
                
                time.sleep(1)  # Small delay between blocks
                
            except KeyboardInterrupt:
                logger.info("Mining stopped by user")
                break
            except Exception as e:
                logger.error(f"Mining error: {e}")
                time.sleep(1)
                
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main() 