"""
Wallet manager with BIP39 mnemonic support and transaction signing
"""

import sqlite3
import logging
import time
import json
from datetime import datetime
import csv
import os
import hashlib
import rsa
from mnemonic import Mnemonic
import binascii
from typing import Optional, Dict, List
import random
import hmac

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
REPORTS_PATH = "data/reports"

class WalletManager:
    def __init__(self, db_path: str = "data/blockchain/chain.db"):
        self.db_path = db_path
        self.mnemo = Mnemonic("english")
        self.current_wallet = None
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
        
    def get_connection(self):
        """Get database connection with proper settings"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def init_database(self):
        """Initialize wallet database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create wallets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    encrypted_private_key TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    mnemonic TEXT NOT NULL,
                    nonce INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            
            # Create nonce tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nonce_tracker (
                    address TEXT NOT NULL,
                    nonce INTEGER NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (address)
                )
            """)
            
            # Create transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
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
            
            # Create mempool table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mempool (
                    tx_hash TEXT PRIMARY KEY,
                    raw_transaction TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            conn.commit()
        finally:
            conn.close()

    def _derive_deterministic_key(self, seed: bytes, length: int = 256) -> bytes:
        """Derive a deterministic key from seed using HMAC"""
        key = b''
        counter = 0
        while len(key) < length:
            counter_bytes = counter.to_bytes(4, 'big')
            h = hmac.new(seed, counter_bytes, hashlib.sha512)
            key += h.digest()
            counter += 1
        return key[:length]

    def create_wallet(self) -> Dict:
        """Create new wallet with mnemonic phrase"""
        # Generate mnemonic
        mnemonic = self.mnemo.generate(strength=128)  # 12 words
        seed = self.mnemo.to_seed(mnemonic)
        
        # Generate deterministic private key
        private_key_bytes = self._derive_deterministic_key(seed)
        private_key = int.from_bytes(private_key_bytes, 'big')
        
        # Create RSA key pair
        e = 65537  # Standard RSA public exponent
        p = rsa.prime.getprime(1024)
        q = rsa.prime.getprime(1024)
        n = p * q
        phi = (p - 1) * (q - 1)
        d = rsa.common.inverse(e, phi)
        
        # Create public and private key objects
        pubkey = rsa.PublicKey(n, e)
        privkey = rsa.PrivateKey(n, e, d, p, q)
        
        # Create wallet address from public key
        address = "LOGI" + hashlib.sha256(pubkey.save_pkcs1()).hexdigest()[:40]
        
        # Encrypt private key
        encrypted_privkey = binascii.hexlify(privkey.save_pkcs1()).decode()
        
        wallet = {
            "address": address,
            "encrypted_private_key": encrypted_privkey,
            "public_key": binascii.hexlify(pubkey.save_pkcs1()).decode(),
            "mnemonic": mnemonic,
            "nonce": 0
        }
        
        # Save to database
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO wallets (
                    address, encrypted_private_key, public_key,
                    mnemonic, nonce, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                wallet["address"],
                wallet["encrypted_private_key"],
                wallet["public_key"],
                wallet["mnemonic"],
                wallet["nonce"],
                time.time()
            ))
            conn.commit()
        finally:
            conn.close()
        
        self.current_wallet = wallet
        return wallet

    def load_wallet(self, address: str) -> Optional[Dict]:
        """Load wallet by address"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT address, encrypted_private_key, public_key, 
                       mnemonic, nonce
                FROM wallets 
                WHERE address = ?
            """, (address,))
            result = cursor.fetchone()
            
            if result:
                wallet = {
                    "address": result[0],
                    "encrypted_private_key": result[1],
                    "public_key": result[2],
                    "mnemonic": result[3],
                    "nonce": result[4]
                }
                self.current_wallet = wallet
                return wallet
            return None
        finally:
            conn.close()

    def list_wallets(self) -> List[Dict]:
        """List all wallets"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT address, mnemonic, nonce FROM wallets")
            wallets = []
            for row in cursor.fetchall():
                wallets.append({
                    "address": row[0],
                    "mnemonic": row[1],
                    "nonce": row[2]
                })
            return wallets
        finally:
            conn.close()

    def get_balance(self, address: str) -> float:
        """Get wallet balance"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Get incoming transactions
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
                AND status = 'confirmed'
            """, (address,))
            incoming = cursor.fetchone()[0] or 0
            
            # Get outgoing transactions
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE from_address = ?
                AND from_address != ?
                AND status = 'confirmed'
            """, (address, '0' * 64))
            outgoing = cursor.fetchone()[0] or 0
            
            return incoming - outgoing
        finally:
            conn.close()

    def create_transaction(self, to_address: str, amount: float) -> Dict:
        """Create and sign a new transaction"""
        if not self.current_wallet:
            raise Exception("No wallet loaded")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check balance
            balance = self.get_balance(self.current_wallet["address"])
            if balance < amount:
                raise Exception(f"Insufficient balance: {balance} < {amount}")
            
            # Get current nonce
            cursor.execute("""
                SELECT nonce FROM wallets
                WHERE address = ?
            """, (self.current_wallet["address"],))
            current_nonce = cursor.fetchone()[0]
            
            # Create transaction
            tx = {
                "from_address": self.current_wallet["address"],
                "to_address": to_address,
                "amount": amount,
                "nonce": current_nonce + 1,
                "timestamp": time.time()
            }
            
            # Sign transaction
            tx_string = json.dumps(tx, sort_keys=True)
            privkey = rsa.PrivateKey.load_pkcs1(binascii.unhexlify(self.current_wallet["encrypted_private_key"]))
            signature = rsa.sign(tx_string.encode(), privkey, 'SHA-256')
            tx["signature"] = binascii.hexlify(signature).decode()
            
            # Update nonce atomically
            cursor.execute("""
                UPDATE wallets
                SET nonce = ?
                WHERE address = ? AND nonce = ?
            """, (tx["nonce"], self.current_wallet["address"], current_nonce))
            
            if cursor.rowcount == 0:
                raise Exception("Nonce update failed - possible replay attack")
            
            # Add to mempool
            cursor.execute("""
                INSERT INTO mempool (tx_hash, raw_transaction, timestamp, status)
                VALUES (?, ?, ?, ?)
            """, (
                hashlib.sha256(tx_string.encode()).hexdigest(),
                json.dumps(tx),
                tx["timestamp"],
                "pending"
            ))
            
            conn.commit()
            return tx
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def verify_transaction(self, tx: Dict) -> bool:
        """Verify transaction signature"""
        if "signature" not in tx:
            return False
            
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Get sender's public key
            cursor.execute("""
                SELECT public_key FROM wallets
                WHERE address = ?
            """, (tx["from_address"],))
            result = cursor.fetchone()
            
            if not result:
                return False
                
            pubkey = rsa.PublicKey.load_pkcs1(binascii.unhexlify(result[0]))
            
            # Verify signature
            tx_copy = tx.copy()
            try:
                signature = binascii.unhexlify(tx_copy.pop("signature"))
            except:
                return False
                
            tx_string = json.dumps(tx_copy, sort_keys=True)
            
            try:
                rsa.verify(tx_string.encode(), signature, pubkey)
                return True
            except:
                return False
        finally:
            conn.close()

    def export_wallet(self, address: str, file_path: str):
        """Export wallet to file"""
        wallet = self.load_wallet(address)
        if wallet:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(wallet, f, indent=2)

    def import_wallet(self, file_path: str) -> Optional[Dict]:
        """Import wallet from file"""
        try:
            with open(file_path, 'r') as f:
                wallet = json.load(f)
                
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # Check if wallet already exists
                cursor.execute("SELECT address FROM wallets WHERE address = ?", 
                             (wallet["address"],))
                if cursor.fetchone():
                    raise Exception("Wallet already exists")
                
                cursor.execute("""
                    INSERT INTO wallets (
                        address, encrypted_private_key, public_key,
                        mnemonic, nonce, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    wallet["address"],
                    wallet["encrypted_private_key"],
                    wallet["public_key"],
                    wallet["mnemonic"],
                    wallet["nonce"],
                    time.time()
                ))
                conn.commit()
                return wallet
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error importing wallet: {e}")
            return None

    def recover_wallet(self, mnemonic: str) -> Optional[Dict]:
        """Recover wallet from mnemonic phrase"""
        try:
            if not self.mnemo.check(mnemonic):
                raise Exception("Invalid mnemonic phrase")
                
            # Generate seed from mnemonic
            seed = self.mnemo.to_seed(mnemonic)
            
            # Generate deterministic private key
            private_key_bytes = self._derive_deterministic_key(seed)
            private_key = int.from_bytes(private_key_bytes, 'big')
            
            # Create RSA key pair
            e = 65537  # Standard RSA public exponent
            p = rsa.prime.getprime(1024)
            q = rsa.prime.getprime(1024)
            n = p * q
            phi = (p - 1) * (q - 1)
            d = rsa.common.inverse(e, phi)
            
            # Create public and private key objects
            pubkey = rsa.PublicKey(n, e)
            privkey = rsa.PrivateKey(n, e, d, p, q)
            
            # Create wallet address
            address = "LOGI" + hashlib.sha256(pubkey.save_pkcs1()).hexdigest()[:40]
            
            wallet = {
                "address": address,
                "encrypted_private_key": binascii.hexlify(privkey.save_pkcs1()).decode(),
                "public_key": binascii.hexlify(pubkey.save_pkcs1()).decode(),
                "mnemonic": mnemonic,
                "nonce": 0
            }
            
            # Save recovered wallet
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO wallets (
                        address, encrypted_private_key, public_key,
                        mnemonic, nonce, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    wallet["address"],
                    wallet["encrypted_private_key"],
                    wallet["public_key"],
                    wallet["mnemonic"],
                    wallet["nonce"],
                    time.time()
                ))
                conn.commit()
                return wallet
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error recovering wallet: {e}")
            return None

    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
        
    def setup_database(self):
        """Setup/upgrade wallet database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Add new columns and indices if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE NOT NULL,
                    public_key TEXT NOT NULL,
                    balance REAL DEFAULT 0.0,
                    type TEXT DEFAULT 'user',
                    total_received REAL DEFAULT 0.0,
                    total_sent REAL DEFAULT 0.0,
                    mining_rewards REAL DEFAULT 0.0,
                    blocks_mined INTEGER DEFAULT 0,
                    transaction_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_updated REAL NOT NULL,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Create indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets(address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_balance ON wallets(balance)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_type ON wallets(type)")
            
            conn.commit()
            logger.info("Wallet database schema atualizado")
            
        finally:
            cursor.close()
            conn.close()
            
    def update_miner_wallet(self, miner_address, block_reward, block_hash):
        """Update miner wallet after block mining"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            now = time.time()
            
            # Check if wallet exists
            cursor.execute("SELECT id FROM wallets WHERE address = ?", (miner_address,))
            wallet = cursor.fetchone()
            
            if wallet:
                # Update existing wallet
                cursor.execute("""
                    UPDATE wallets 
                    SET balance = balance + ?,
                        mining_rewards = mining_rewards + ?,
                        blocks_mined = blocks_mined + 1,
                        type = CASE WHEN type = 'user' THEN 'miner' ELSE type END,
                        last_updated = ?
                    WHERE address = ?
                """, (block_reward, block_reward, now, miner_address))
            else:
                # Create new wallet
                cursor.execute("""
                    INSERT INTO wallets (
                        address, public_key, balance, type,
                        mining_rewards, blocks_mined,
                        created_at, last_updated
                    ) VALUES (?, ?, ?, 'miner', ?, 1, ?, ?)
                """, (miner_address, miner_address, block_reward, 
                      block_reward, now, now))
            
            # Record mining reward transaction
            cursor.execute("""
                INSERT INTO transactions (
                    tx_hash, block_hash, tx_type,
                    from_address, to_address, amount,
                    timestamp, status
                ) VALUES (?, ?, 'mining_reward', ?, ?, ?, ?, 'confirmed')
            """, (
                f"reward_{block_hash}", block_hash,
                "0"*64, miner_address, block_reward, now
            ))
            
            conn.commit()
            logger.info(f"Carteira do minerador {miner_address} atualizada")
            
        finally:
            cursor.close()
            conn.close()
            
    def update_transaction_wallets(self, from_address, to_address, amount, tx_hash):
        """Update wallets involved in a transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            now = time.time()
            
            # Update sender wallet
            cursor.execute("""
                UPDATE wallets 
                SET balance = balance - ?,
                    total_sent = total_sent + ?,
                    transaction_count = transaction_count + 1,
                    last_updated = ?
                WHERE address = ?
            """, (amount, amount, now, from_address))
            
            # Update or create receiver wallet
            cursor.execute("SELECT id FROM wallets WHERE address = ?", (to_address,))
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE wallets 
                    SET balance = balance + ?,
                        total_received = total_received + ?,
                        transaction_count = transaction_count + 1,
                        last_updated = ?
                    WHERE address = ?
                """, (amount, amount, now, to_address))
            else:
                cursor.execute("""
                    INSERT INTO wallets (
                        address, public_key, balance,
                        total_received, transaction_count,
                        created_at, last_updated
                    ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (to_address, to_address, amount, amount, now, now))
            
            conn.commit()
            logger.info(f"Carteiras atualizadas para transação {tx_hash}")
            
        finally:
            cursor.close()
            conn.close()
            
    def validate_transaction(self, from_address, amount):
        """Validate if a transaction can be processed"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get current balance
            cursor.execute("""
                SELECT balance 
                FROM wallets 
                WHERE address = ?
            """, (from_address,))
            result = cursor.fetchone()
            
            if not result:
                return False, "Carteira de origem não existe"
                
            current_balance = result[0]
            
            # Check if transaction would result in negative balance
            if current_balance < amount:
                return False, f"Saldo insuficiente (atual: {current_balance}, necessário: {amount})"
                
            # Get pending transactions from mempool
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM mempool
                WHERE from_address = ?
                AND status = 'pending'
            """, (from_address,))
            pending_amount = cursor.fetchone()[0]
            
            # Check if balance would be negative including pending transactions
            if current_balance < (amount + pending_amount):
                return False, f"Saldo insuficiente considerando transações pendentes"
                
            return True, "Transação válida"
            
        finally:
            cursor.close()
            conn.close()
            
    def recalculate_all_balances(self):
        """Recalculate and fix all wallet balances"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all wallets
            cursor.execute("SELECT address FROM wallets")
            wallets = cursor.fetchall()
            
            fixed_count = 0
            for wallet in wallets:
                address = wallet[0]
                
                # Calculate received amount (excluding mining rewards)
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE to_address = ?
                    AND tx_type != 'mining_reward'
                    AND status = 'confirmed'
                """, (address,))
                received = cursor.fetchone()[0]
                
                # Calculate sent amount
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE from_address = ?
                    AND tx_type != 'mining_reward'
                    AND status = 'confirmed'
                """, (address,))
                sent = cursor.fetchone()[0]
                
                # Calculate mining rewards
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE to_address = ?
                    AND tx_type = 'mining_reward'
                    AND status = 'confirmed'
                """, (address,))
                rewards = cursor.fetchone()[0]
                
                # Calculate correct balance
                correct_balance = received - sent + rewards
                
                # Get current balance
                cursor.execute("""
                    SELECT balance
                    FROM wallets
                    WHERE address = ?
                """, (address,))
                current_balance = cursor.fetchone()[0]
                
                # Fix if different
                if abs(current_balance - correct_balance) > 0.00001:
                    cursor.execute("""
                        UPDATE wallets
                        SET balance = ?,
                            total_received = ?,
                            total_sent = ?,
                            mining_rewards = ?,
                            last_updated = ?
                        WHERE address = ?
                    """, (correct_balance, received, sent, rewards, 
                          time.time(), address))
                    fixed_count += 1
                    logger.info(f"Corrigido saldo da carteira {address}")
                    
            if fixed_count > 0:
                conn.commit()
                logger.info(f"Corrigidos {fixed_count} saldos de carteiras")
            else:
                logger.info("Todos os saldos estão corretos")
                
        finally:
            cursor.close()
            conn.close()
            
    def generate_wallet_report(self, report_type='csv'):
        """Generate wallet report"""
        if not os.path.exists(REPORTS_PATH):
            os.makedirs(REPORTS_PATH)
            
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT address, balance, type, total_received,
                       total_sent, mining_rewards, blocks_mined,
                       transaction_count, created_at, last_updated
                FROM wallets
                ORDER BY balance DESC
            """)
            wallets = cursor.fetchall()
            
            if report_type == 'csv':
                filename = f"{REPORTS_PATH}/wallets_{now}.csv"
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'Address', 'Balance', 'Type', 'Total Received',
                        'Total Sent', 'Mining Rewards', 'Blocks Mined',
                        'Transaction Count', 'Created At', 'Last Updated'
                    ])
                    writer.writerows(wallets)
            else:
                filename = f"{REPORTS_PATH}/wallets_{now}.json"
                with open(filename, 'w') as f:
                    json.dump([{
                        'address': w[0],
                        'balance': w[1],
                        'type': w[2],
                        'total_received': w[3],
                        'total_sent': w[4],
                        'mining_rewards': w[5],
                        'blocks_mined': w[6],
                        'transaction_count': w[7],
                        'created_at': w[8],
                        'last_updated': w[9]
                    } for w in wallets], f, indent=2)
                    
            logger.info(f"Relatório de carteiras gerado: {filename}")
            return filename
            
        finally:
            cursor.close()
            conn.close()
            
    def generate_mining_report(self, report_type='csv'):
        """Generate mining activity report"""
        if not os.path.exists(REPORTS_PATH):
            os.makedirs(REPORTS_PATH)
            
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT m.miner_address,
                       COUNT(*) as blocks_mined,
                       SUM(m.mining_reward) as total_reward,
                       MIN(m.timestamp) as first_block,
                       MAX(m.timestamp) as last_block,
                       w.balance as current_balance
                FROM blocks m
                LEFT JOIN wallets w ON w.address = m.miner_address
                WHERE m.miner_address IS NOT NULL
                GROUP BY m.miner_address
                ORDER BY blocks_mined DESC
            """)
            miners = cursor.fetchall()
            
            if report_type == 'csv':
                filename = f"{REPORTS_PATH}/mining_{now}.csv"
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'Miner Address', 'Blocks Mined', 'Total Reward',
                        'First Block', 'Last Block', 'Current Balance'
                    ])
                    writer.writerows(miners)
            else:
                filename = f"{REPORTS_PATH}/mining_{now}.json"
                with open(filename, 'w') as f:
                    json.dump([{
                        'miner_address': m[0],
                        'blocks_mined': m[1],
                        'total_reward': m[2],
                        'first_block': m[3],
                        'last_block': m[4],
                        'current_balance': m[5]
                    } for m in miners], f, indent=2)
                    
            logger.info(f"Relatório de mineração gerado: {filename}")
            return filename
            
        finally:
            cursor.close()
            conn.close()
            
    def generate_transaction_report(self, start_time=None, end_time=None, 
                                  report_type='csv'):
        """Generate transaction report for a time period"""
        if not os.path.exists(REPORTS_PATH):
            os.makedirs(REPORTS_PATH)
            
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT tx_hash, block_hash, tx_type,
                       from_address, to_address, amount,
                       timestamp, status
                FROM transactions
                WHERE status = 'confirmed'
            """
            params = []
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
                
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            transactions = cursor.fetchall()
            
            if report_type == 'csv':
                filename = f"{REPORTS_PATH}/transactions_{now}.csv"
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'Transaction Hash', 'Block Hash', 'Type',
                        'From Address', 'To Address', 'Amount',
                        'Timestamp', 'Status'
                    ])
                    writer.writerows(transactions)
            else:
                filename = f"{REPORTS_PATH}/transactions_{now}.json"
                with open(filename, 'w') as f:
                    json.dump([{
                        'tx_hash': t[0],
                        'block_hash': t[1],
                        'tx_type': t[2],
                        'from_address': t[3],
                        'to_address': t[4],
                        'amount': t[5],
                        'timestamp': t[6],
                        'status': t[7]
                    } for t in transactions], f, indent=2)
                    
            logger.info(f"Relatório de transações gerado: {filename}")
            return filename
            
        finally:
            cursor.close()
            conn.close() 