"""
Cross-platform blockchain miner implementation
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from colorama import init, Fore, Style
import threading
from queue import Queue
import platform
import rsa
import binascii

# Initialize colorama for Windows support
init()

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
MAX_RETRIES = 5
RETRY_DELAY = 1

# Determine number of threads based on system
if platform.system() == "Windows":
    THREAD_COUNT = max(1, os.cpu_count() - 1)  # Leave one CPU for system
else:
    THREAD_COUNT = max(1, (os.cpu_count() or 1) - 1)  # Handle None return on some Unix

class MiningThread(threading.Thread):
    def __init__(self, start_nonce, step, target, block_template, result_queue):
        super().__init__()
        self.start_nonce = start_nonce
        self.step = step
        self.target = target
        self.block_template = block_template
        self.result_queue = result_queue
        self.running = True

    def run(self):
        nonce = self.start_nonce
        while self.running:
            block_string = f"{self.block_template['timestamp']}{self.block_template['transactions']}{self.block_template['previous_hash']}{nonce}"
            block_hash = hashlib.sha256(block_string.encode()).hexdigest()
            
            if block_hash.startswith(self.target):
                self.result_queue.put((nonce, block_hash))
                break
            
            nonce += self.step

    def stop(self):
        self.running = False

class SimpleMiner:
    def __init__(self):
        self.target = '0' * DIFFICULTY
        self.blocks = []
        self.init_database()
        self.load_blocks()
        
    def get_db_connection(self):
        """Get database connection with retry mechanism"""
        for attempt in range(MAX_RETRIES):
            try:
                conn = sqlite3.connect(DB_PATH, timeout=20.0)
                conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
                conn.execute("PRAGMA busy_timeout=10000")  # 10 second timeout
                return conn
            except sqlite3.OperationalError as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise e

    def get_next_block_index(self):
        """Get next block index"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(block_index) FROM blocks")
            result = cursor.fetchone()[0]
            next_index = (result + 1) if result is not None else 0
            return next_index
        finally:
            conn.close()

    def mine_block(self, transactions):
        """Mine a new block using multiple threads"""
        # Clean mempool first
        self.clean_mempool()
        
        # Process input transactions first
        processed_transactions = []
        for tx in transactions:
            # Add nonce field if missing (for mining rewards)
            if 'nonce' not in tx:
                tx['nonce'] = 0
                
            if not self.validate_transaction(tx):
                logger.warning(f"Invalid transaction skipped")
                continue
            processed_transactions.append(tx)
            
        # Get pending transactions from mempool
        for attempt in range(MAX_RETRIES):
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute("SELECT tx_hash, raw_transaction FROM mempool WHERE status = 'pending'")
                pending_txs = cursor.fetchall()
                
                # Parse pending transactions
                for tx_hash, raw_tx in pending_txs:
                    try:
                        tx_data = json.loads(raw_tx)
                        
                        # Verify sender has enough balance
                        if tx_data.get('from_address', '') != '0' * 64:  # Not a mining reward
                            balance = self.get_balance(tx_data['from_address'])
                            if balance < tx_data['amount']:
                                logger.warning(f"Insufficient balance for transaction {tx_hash}")
                                continue
                        
                        processed_transactions.append({
                            'from_address': tx_data.get('from_address', '0' * 64),
                            'to_address': tx_data.get('to_address', ''),
                            'amount': tx_data.get('amount', 0),
                            'timestamp': tx_data.get('timestamp', time.time()),
                            'nonce': tx_data.get('nonce', 0),
                            'signature': tx_data.get('signature', '')
                        })
                        
                        # Mark transaction as processing
                        cursor.execute("""
                            UPDATE mempool 
                            SET status = 'processing' 
                            WHERE tx_hash = ?
                        """, (tx_hash,))
                    except KeyError as e:
                        logger.warning(f"Invalid transaction in mempool: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing mempool transaction: {e}")
                        continue
                
                conn.commit()
                conn.close()
                break
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                logger.error(f"Error accessing mempool: {e}")
                raise
            except Exception as e:
                logger.error(f"Error accessing mempool: {e}")
                raise
        
        previous_hash = self.blocks[-1]['hash'] if self.blocks else '0' * 64
        timestamp = time.time()
        
        print(f"\n{Fore.RED}Previous Hash: {previous_hash}{Style.RESET_ALL}")
        print(f"Starting mining process with {THREAD_COUNT} threads...")
        start_time = time.time()

        # Create block template
        block_template = {
            'timestamp': timestamp,
            'transactions': processed_transactions,
            'previous_hash': previous_hash
        }

        # Create result queue and threads
        result_queue = Queue()
        threads = []
        
        # Start mining threads
        for i in range(THREAD_COUNT):
            thread = MiningThread(i, THREAD_COUNT, self.target, block_template, result_queue)
            threads.append(thread)
            thread.start()

        try:
            # Wait for result
            winning_nonce, winning_hash = result_queue.get()
            
            # Stop all threads
            for thread in threads:
                thread.stop()
            
            # Wait for threads to finish
            for thread in threads:
                thread.join()

        except Exception as e:
            # Stop all threads on error
            for thread in threads:
                thread.stop()
            for thread in threads:
                thread.join()
            raise e

        end_time = time.time()
        mining_time = end_time - start_time
        
        # Create the winning block
        block = {
            'timestamp': timestamp,
            'transactions': processed_transactions,
            'previous_hash': previous_hash,
            'nonce': winning_nonce,
            'hash': winning_hash
        }
        
        print(f"\n{Fore.GREEN}Block Hash: {winning_hash}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Nonce: {winning_nonce}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Time taken: {mining_time:.2f} seconds{Style.RESET_ALL}")
        
        # Get next block index
        block_index = self.get_next_block_index()
        
        # Save block with correct index
        for attempt in range(MAX_RETRIES):
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                
                # Save block with the correct index
                cursor.execute("""
                    INSERT INTO blocks (
                        hash, block_index, timestamp, previous_hash,
                        difficulty, nonce, miner_address, mining_reward,
                        merkle_root, version, state, total_transactions,
                        size_bytes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    block['hash'],
                    block_index,
                    block['timestamp'],
                    block['previous_hash'],
                    DIFFICULTY,
                    winning_nonce,
                    block['transactions'][0]['to_address'],
                    BLOCK_REWARD,
                    '',
                    1,
                    'confirmed',
                    len(block['transactions']),
                    len(str(block))
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
                        'mining_reward' if tx['from_address'] == '0' * 64 else 'transfer',
                        tx['from_address'],
                        tx['to_address'],
                        tx['amount'],
                        tx['timestamp'],
                        0,
                        '',
                        None,
                        'confirmed',
                        0.0
                    ))
                
                conn.commit()
                
                # Clear processed transactions from mempool
                cursor.execute("DELETE FROM mempool WHERE status = 'processing'")
                conn.commit()
                conn.close()
                
                # Save to blocks list and file
                self.blocks.append(block)
                self.save_blocks()
                
                # Get updated balance
                balance = self.get_balance(block['transactions'][0]['to_address'])
                print(f"{Fore.BLUE}Current balance: {balance} LOGI{Style.RESET_ALL}")
                print(f"Total blocks: {len(self.blocks)}")
                print(f"Mining reward: {BLOCK_REWARD} LOGI")
                
                return block
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    # Another miner got there first, try again with next index
                    block_index = self.get_next_block_index()
                    if attempt < MAX_RETRIES - 1:
                        continue
                logger.error(f"Database integrity error: {e}")
                raise
            except Exception as e:
                logger.error(f"Error saving block: {e}")
                raise
        
    def init_database(self):
        """Initialize SQLite database"""
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = self.get_db_connection()
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
                    block_hash TEXT,
                    tx_type TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    nonce INTEGER DEFAULT 0,
                    signature TEXT,
                    data TEXT,
                    status TEXT DEFAULT 'pending',
                    fee REAL DEFAULT 0.0
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mempool (
                    tx_hash TEXT PRIMARY KEY,
                    raw_transaction TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            
    def load_blocks(self):
        """Load blocks from file"""
        try:
            if os.path.exists(BLOCKS_FILE):
                with open(BLOCKS_FILE, 'r') as f:
                    self.blocks = json.load(f)
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
            
    def get_balance(self, address):
        """Get balance for address"""
        for attempt in range(MAX_RETRIES):
            try:
                conn = self.get_db_connection()
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
                
                conn.close()
                return balance
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                logger.error(f"Error getting balance: {e}")
                raise
            except Exception as e:
                logger.error(f"Error getting balance: {e}")
                raise

    def validate_transaction(self, tx_data):
        """Validate a single transaction"""
        try:
            # Check required fields
            required_fields = ['from_address', 'to_address', 'amount', 'timestamp', 'nonce']
            if not all(field in tx_data for field in required_fields):
                return False
                
            # Skip signature check for mining rewards
            if tx_data['from_address'] != '0' * 64:  # Not a mining reward
                if 'signature' not in tx_data:
                    return False
                    
                # Get sender's public key
                conn = self.get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT public_key FROM wallets 
                        WHERE address = ?
                    """, (tx_data['from_address'],))
                    result = cursor.fetchone()
                    if not result:
                        return False
                        
                    pubkey = rsa.PublicKey.load_pkcs1(binascii.unhexlify(result[0]))
                    
                    # Verify signature
                    tx_copy = tx_data.copy()
                    signature = binascii.unhexlify(tx_copy.pop('signature'))
                    tx_string = json.dumps(tx_copy, sort_keys=True)
                    
                    try:
                        rsa.verify(tx_string.encode(), signature, pubkey)
                    except:
                        return False
                finally:
                    conn.close()
            
            return True
        except Exception as e:
            logging.error(f"Transaction validation error: {e}")
            return False

    def create_mining_reward(self, wallet):
        """Create a mining reward transaction"""
        return {
            'from_address': '0' * 64,  # System reward
            'to_address': wallet['address'],
            'amount': BLOCK_REWARD,
            'timestamp': time.time(),
            'nonce': 0
        }

    def validate_mempool_transaction(self, tx_data):
        """Validate a transaction from mempool"""
        try:
            # Check balance for non-mining transactions
            if tx_data['from_address'] != '0' * 64:  # Not a mining reward
                balance = self.get_balance(tx_data['from_address'])
                if balance < tx_data['amount']:
                    return False
                    
            # Create standardized transaction
            tx = {
                'from_address': tx_data['from_address'],
                'to_address': tx_data['to_address'],
                'amount': tx_data['amount'],
                'timestamp': tx_data['timestamp'],
                'nonce': tx_data['nonce']
            }
            
            if 'signature' in tx_data:
                tx['signature'] = tx_data['signature']
                
            return self.validate_transaction(tx)
            
        except Exception as e:
            logging.error(f"Mempool transaction validation error: {e}")
            return False

    def clean_mempool(self):
        """Clean invalid transactions from mempool"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cleaned = 0
        
        try:
            # Get all pending transactions
            cursor.execute("SELECT tx_hash, raw_transaction FROM mempool WHERE status = 'pending'")
            pending_txs = cursor.fetchall()
            
            for tx_hash, raw_tx in pending_txs:
                try:
                    tx_data = json.loads(raw_tx)
                    
                    # Check required fields
                    required_fields = ['from_address', 'to_address', 'amount', 'timestamp', 'nonce']
                    if not all(field in tx_data for field in required_fields):
                        cursor.execute("DELETE FROM mempool WHERE tx_hash = ?", (tx_hash,))
                        cleaned += 1
                        continue
                        
                    # Check if it's a valid transaction
                    if not self.validate_transaction(tx_data):
                        cursor.execute("DELETE FROM mempool WHERE tx_hash = ?", (tx_hash,))
                        cleaned += 1
                        
                except (json.JSONDecodeError, KeyError):
                    # Remove invalid JSON or transactions with missing fields
                    cursor.execute("DELETE FROM mempool WHERE tx_hash = ?", (tx_hash,))
                    cleaned += 1
                    
            conn.commit()
            logger.info(f"Cleaned {cleaned} invalid transactions from mempool")
            
        finally:
            conn.close()
            
        return cleaned

def main():
    try:
        # Initialize miner
        miner = SimpleMiner()
        
        # Clean mempool on startup
        cleaned = miner.clean_mempool()
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} invalid transactions from mempool on startup")
        
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
                
        print(f"\nMining with address: {wallet['address']}")
        print(f"Using {THREAD_COUNT} threads for mining")
        print(f"Running on {platform.system()} {platform.release()}")
        
        # Start mining loop
        while True:
            try:
                # Create mining reward transaction
                reward_tx = {
                    'from_address': '0' * 64,  # System reward
                    'to_address': wallet['address'],
                    'amount': BLOCK_REWARD,
                    'timestamp': time.time(),
                    'nonce': 0
                }
                
                # Mine block
                mined_block = miner.mine_block([reward_tx])
                
                time.sleep(0.1)  # Small delay between blocks
                
            except KeyboardInterrupt:
                print("\nMining stopped by user")
                break
            except Exception as e:
                logger.error(f"Mining error: {e}")
                time.sleep(RETRY_DELAY)
                
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main() 