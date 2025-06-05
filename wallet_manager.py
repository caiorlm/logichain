"""
Wallet Management System for LogiChain
"""

import sqlite3
import logging
import time
import json
from datetime import datetime
import csv
import os

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
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.setup_database()
        
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