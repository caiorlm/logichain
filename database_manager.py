"""
Database Manager for blockchain persistence
"""

import sqlite3
import logging
import json
import time
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from models import Block, Transaction
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages blockchain database with atomic operations"""
    
    def __init__(self, db_path: str = "data/blockchain/chain.db"):
        self.db_path = db_path
        self.setup_database()
        
    @contextmanager
    def get_connection(self):
        """Get database connection with context management"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
            
    def setup_database(self):
        """Initialize database schema with proper indices"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create blocks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    block_index INTEGER UNIQUE,
                    timestamp REAL,
                    previous_hash TEXT,
                    merkle_root TEXT,
                    difficulty INTEGER,
                    nonce INTEGER,
                    miner_address TEXT,
                    mining_reward REAL,
                    state TEXT DEFAULT 'pending',
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (previous_hash) REFERENCES blocks (hash)
                )
            """)
            
            # Create transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    block_hash TEXT,
                    tx_type TEXT,
                    from_address TEXT,
                    to_address TEXT,
                    amount REAL,
                    timestamp REAL,
                    signature TEXT,
                    public_key TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (block_hash) REFERENCES blocks (hash)
                )
            """)
            
            # Create mempool table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mempool (
                    tx_hash TEXT PRIMARY KEY,
                    raw_transaction TEXT,
                    timestamp REAL,
                    fee REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'pending',
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # Create wallets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    public_key TEXT,
                    balance REAL DEFAULT 0.0,
                    type TEXT DEFAULT 'user',
                    total_received REAL DEFAULT 0.0,
                    total_sent REAL DEFAULT 0.0,
                    mining_rewards REAL DEFAULT 0.0,
                    blocks_mined INTEGER DEFAULT 0,
                    transaction_count INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    last_updated REAL DEFAULT (strftime('%s', 'now')),
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Create indices for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_index ON blocks(block_index)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_prev_hash ON blocks(previous_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transactions(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mempool_timestamp ON mempool(timestamp)")
            
            conn.commit()
            logger.info("Database schema initialized")
            
    def save_block(self, block: Block, atomic: bool = True) -> bool:
        """Save block and its transactions atomically"""
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                if atomic:
                    cursor.execute("BEGIN TRANSACTION")
                    
                # Insert block
                block_data = block.to_dict()
                cursor.execute("""
                    INSERT INTO blocks (
                        hash, block_index, timestamp,
                        previous_hash, merkle_root,
                        difficulty, nonce,
                        miner_address, mining_reward,
                        state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
                """, (
                    block_data['hash'],
                    block_data['index'],
                    block_data['timestamp'],
                    block_data['previous_hash'],
                    block_data['merkle_root'],
                    block_data['difficulty'],
                    block_data['nonce'],
                    block_data['miner_address'],
                    block_data['mining_reward']
                ))
                
                # Insert transactions
                for tx in block.transactions:
                    cursor.execute("""
                        INSERT INTO transactions (
                            tx_hash, block_hash, tx_type,
                            from_address, to_address, amount,
                            timestamp, signature, public_key,
                            status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
                    """, (
                        tx.tx_hash,
                        block.hash,
                        tx.tx_type,
                        tx.from_address,
                        tx.to_address,
                        tx.amount,
                        tx.timestamp,
                        tx.signature,
                        tx.public_key
                    ))
                    
                    # Update wallet balances
                    if tx.tx_type == 'mining_reward':
                        cursor.execute("""
                            INSERT INTO wallets (
                                address, balance, mining_rewards,
                                blocks_mined, transaction_count
                            ) VALUES (?, ?, ?, 1, 1)
                            ON CONFLICT(address) DO UPDATE SET
                                balance = balance + ?,
                                mining_rewards = mining_rewards + ?,
                                blocks_mined = blocks_mined + 1,
                                transaction_count = transaction_count + 1,
                                last_updated = strftime('%s', 'now')
                        """, (
                            tx.to_address,
                            tx.amount,
                            tx.amount,
                            tx.amount,
                            tx.amount
                        ))
                    else:
                        # Update sender balance
                        cursor.execute("""
                            INSERT INTO wallets (
                                address, balance, total_sent,
                                transaction_count
                            ) VALUES (?, -?, ?, 1)
                            ON CONFLICT(address) DO UPDATE SET
                                balance = balance - ?,
                                total_sent = total_sent + ?,
                                transaction_count = transaction_count + 1,
                                last_updated = strftime('%s', 'now')
                        """, (
                            tx.from_address,
                            tx.amount,
                            tx.amount,
                            tx.amount,
                            tx.amount
                        ))
                        
                        # Update receiver balance
                        cursor.execute("""
                            INSERT INTO wallets (
                                address, balance, total_received,
                                transaction_count
                            ) VALUES (?, ?, ?, 1)
                            ON CONFLICT(address) DO UPDATE SET
                                balance = balance + ?,
                                total_received = total_received + ?,
                                transaction_count = transaction_count + 1,
                                last_updated = strftime('%s', 'now')
                        """, (
                            tx.to_address,
                            tx.amount,
                            tx.amount,
                            tx.amount,
                            tx.amount
                        ))
                        
                    # Remove from mempool if present
                    cursor.execute("DELETE FROM mempool WHERE tx_hash = ?", (tx.tx_hash,))
                    
                if atomic:
                    conn.commit()
                return True
                
            except Exception as e:
                if atomic:
                    conn.rollback()
                logger.error(f"Error saving block: {str(e)}")
                return False
                
    def get_block(self, block_hash: str) -> Optional[Block]:
        """Get block by hash"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get block data
            cursor.execute("""
                SELECT * FROM blocks WHERE hash = ?
            """, (block_hash,))
            block_data = cursor.fetchone()
            
            if not block_data:
                return None
                
            # Get block transactions
            cursor.execute("""
                SELECT * FROM transactions 
                WHERE block_hash = ?
                ORDER BY timestamp ASC
            """, (block_hash,))
            transactions = []
            
            for tx_data in cursor.fetchall():
                transaction = Transaction(
                    tx_hash=tx_data['tx_hash'],
                    tx_type=tx_data['tx_type'],
                    from_address=tx_data['from_address'],
                    to_address=tx_data['to_address'],
                    amount=tx_data['amount'],
                    timestamp=tx_data['timestamp'],
                    signature=tx_data['signature'],
                    public_key=tx_data['public_key']
                )
                transactions.append(transaction)
                
            # Create block
            return Block(
                index=block_data['block_index'],
                timestamp=block_data['timestamp'],
                transactions=transactions,
                previous_hash=block_data['previous_hash'],
                difficulty=block_data['difficulty'],
                nonce=block_data['nonce'],
                miner_address=block_data['miner_address'],
                mining_reward=block_data['mining_reward']
            )
            
    def get_latest_block(self) -> Optional[Block]:
        """Get latest confirmed block"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT hash FROM blocks 
                WHERE state = 'confirmed'
                ORDER BY block_index DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                return self.get_block(result['hash'])
            return None
            
    def save_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """Save transaction to mempool"""
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO mempool (
                        tx_hash, raw_transaction,
                        timestamp, status
                    ) VALUES (?, ?, ?, 'pending')
                """, (
                    transaction.tx_hash,
                    json.dumps(transaction.to_dict()),
                    transaction.timestamp
                ))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error saving to mempool: {str(e)}")
                return False
                
    def get_pending_transactions(self, limit: int = 100) -> List[Transaction]:
        """Get pending transactions from mempool"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT raw_transaction 
                FROM mempool 
                WHERE status = 'pending'
                ORDER BY fee DESC, timestamp ASC
                LIMIT ?
            """, (limit,))
            
            transactions = []
            for row in cursor.fetchall():
                tx_data = json.loads(row['raw_transaction'])
                transactions.append(Transaction(**tx_data))
            return transactions
            
    def get_wallet_balance(self, address: str) -> float:
        """Get accurate wallet balance including mining rewards"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Get mining rewards
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE to_address = ?
                    AND from_address = ?
                    AND tx_type = 'mining_reward'
                    AND status = 'confirmed'
                """, (address, '0' * 64))
                mining_rewards = cursor.fetchone()[0] or 0
                
                # Get regular incoming transactions
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE to_address = ?
                    AND tx_type != 'mining_reward'
                    AND status = 'confirmed'
                """, (address,))
                incoming = cursor.fetchone()[0] or 0
                
                # Get outgoing transactions
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE from_address = ?
                    AND status = 'confirmed'
                """, (address,))
                outgoing = cursor.fetchone()[0] or 0
                
                # Get blocks mined count for verification
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM blocks
                    WHERE miner_address = ?
                """, (address,))
                blocks_mined = cursor.fetchone()[0] or 0
                
                # Verify mining rewards match blocks mined
                expected_rewards = blocks_mined * 50.0  # Assuming no halving yet
                if abs(mining_rewards - expected_rewards) > 0.00001:
                    logger.warning(f"Mining rewards mismatch for {address}")
                    logger.warning(f"Expected: {expected_rewards}, Actual: {mining_rewards}")
                    
                balance = mining_rewards + incoming - outgoing
                
                # Log detailed balance info
                logger.info(f"\nWallet Balance Details for {address}:")
                logger.info(f"Mining Rewards: {mining_rewards} LOGI")
                logger.info(f"Other Incoming: {incoming} LOGI")
                logger.info(f"Total Outgoing: {outgoing} LOGI")
                logger.info(f"Blocks Mined: {blocks_mined}")
                logger.info(f"Current Balance: {balance} LOGI")
                
                return balance
                
            except Exception as e:
                logger.error(f"Error calculating balance: {e}")
                return 0.0
                
    def verify_chain_integrity(self) -> Tuple[bool, List[str]]:
        """Verify entire blockchain integrity"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            errors = []
            
            try:
                # Get all blocks in order
                cursor.execute("""
                    SELECT hash, previous_hash, timestamp, nonce, difficulty,
                           miner_address, merkle_root
                    FROM blocks
                    ORDER BY timestamp ASC
                """)
                blocks = cursor.fetchall()
                
                prev_hash = "0" * 64  # Genesis block previous hash
                
                for block in blocks:
                    block_hash, previous_hash, timestamp, nonce, difficulty, \
                    miner_address, merkle_root = block
                    
                    # Verify previous hash links
                    if previous_hash != prev_hash:
                        errors.append(f"Invalid previous hash link at block {block_hash}")
                        
                    # Verify proof of work
                    if not self._verify_pow(block_hash, difficulty):
                        errors.append(f"Invalid proof of work for block {block_hash}")
                        
                    # Verify merkle root
                    calculated_root = self._calculate_merkle_root(block_hash)
                    if calculated_root != merkle_root:
                        errors.append(f"Invalid merkle root for block {block_hash}")
                        
                    # Verify mining reward transaction exists
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM transactions
                        WHERE block_hash = ?
                        AND tx_type = 'mining_reward'
                        AND from_address = ?
                        AND to_address = ?
                    """, (block_hash, '0' * 64, miner_address))
                    
                    if cursor.fetchone()[0] != 1:
                        errors.append(f"Missing mining reward for block {block_hash}")
                        
                    prev_hash = block_hash
                    
                return len(errors) == 0, errors
                
            except Exception as e:
                logger.error(f"Error verifying chain: {e}")
                return False, [str(e)]
                
    def _verify_pow(self, block_hash: str, difficulty: int) -> bool:
        """Verify proof of work for a block"""
        try:
            # Check if hash starts with required number of zeros
            return block_hash.startswith('0' * difficulty)
        except Exception:
            return False
            
    def _calculate_merkle_root(self, block_hash: str) -> str:
        """Calculate merkle root for a block's transactions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Get all transaction hashes for the block
                cursor.execute("""
                    SELECT tx_hash
                    FROM transactions
                    WHERE block_hash = ?
                    ORDER BY timestamp ASC
                """, (block_hash,))
                
                tx_hashes = [row[0] for row in cursor.fetchall()]
                
                if not tx_hashes:
                    return "0" * 64
                    
                # Calculate merkle root
                while len(tx_hashes) > 1:
                    if len(tx_hashes) % 2 == 1:
                        tx_hashes.append(tx_hashes[-1])
                        
                    new_hashes = []
                    for i in range(0, len(tx_hashes), 2):
                        combined = tx_hashes[i] + tx_hashes[i+1]
                        new_hash = hashlib.sha256(combined.encode()).hexdigest()
                        new_hashes.append(new_hash)
                    tx_hashes = new_hashes
                    
                return tx_hashes[0]
                
            except Exception as e:
                logger.error(f"Error calculating merkle root: {e}")
                return "0" * 64 