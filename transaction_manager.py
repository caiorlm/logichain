"""
Transaction Manager for LogiChain
"""

import sqlite3
import logging
import hashlib
import time
import json
from wallet_manager import WalletManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TransactionManager:
    def __init__(self):
        self.wallet_manager = WalletManager()
        
    def get_connection(self):
        """Get database connection"""
        return self.wallet_manager.get_connection()
        
    def calculate_transaction_hash(self, tx_data):
        """Calculate transaction hash"""
        data_string = f"{tx_data['timestamp']}{tx_data['from_address']}{tx_data['to_address']}{tx_data['amount']}{tx_data['nonce']}"
        return hashlib.sha256(data_string.encode()).hexdigest()
        
    def create_transaction(self, from_address, to_address, amount, fee=0.0):
        """Create and validate a new transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Validate transaction
            valid, message = self.wallet_manager.validate_transaction(
                from_address, amount + fee
            )
            
            if not valid:
                logger.error(f"Transação inválida: {message}")
                return False, message
                
            # Create transaction data
            tx_data = {
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'fee': fee,
                'timestamp': time.time(),
                'nonce': 0  # Should be incremented based on sender's tx count
            }
            
            # Get sender's transaction count for nonce
            cursor.execute("""
                SELECT transaction_count
                FROM wallets
                WHERE address = ?
            """, (from_address,))
            result = cursor.fetchone()
            tx_data['nonce'] = result[0] if result else 0
            
            # Calculate transaction hash
            tx_hash = self.calculate_transaction_hash(tx_data)
            
            # Add to mempool
            cursor.execute("""
                INSERT INTO mempool (
                    tx_hash, raw_transaction,
                    timestamp, fee, status
                ) VALUES (?, ?, ?, ?, 'pending')
            """, (
                tx_hash,
                str(tx_data),
                tx_data['timestamp'],
                fee
            ))
            
            conn.commit()
            logger.info(f"Transação {tx_hash} adicionada ao mempool")
            return True, tx_hash
            
        except Exception as e:
            logger.error(f"Erro ao criar transação: {str(e)}")
            conn.rollback()
            return False, str(e)
            
        finally:
            cursor.close()
            conn.close()
            
    def get_transaction_status(self, tx_hash):
        """Get transaction status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check mempool
            cursor.execute("""
                SELECT status
                FROM mempool
                WHERE tx_hash = ?
            """, (tx_hash,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'status': result[0],
                    'location': 'mempool'
                }
                
            # Check confirmed transactions
            cursor.execute("""
                SELECT t.status, t.block_hash, b.block_index
                FROM transactions t
                LEFT JOIN blocks b ON t.block_hash = b.hash
                WHERE t.tx_hash = ?
            """, (tx_hash,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'status': result[0],
                    'location': 'blockchain',
                    'block_hash': result[1],
                    'block_index': result[2]
                }
                
            return {
                'status': 'not_found',
                'location': None
            }
            
        finally:
            cursor.close()
            conn.close()
            
    def get_mempool_transactions(self, limit=100):
        """Get pending transactions from mempool"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT tx_hash, raw_transaction, timestamp, fee, status
                FROM mempool
                WHERE status = 'pending'
                ORDER BY fee DESC, timestamp ASC
                LIMIT ?
            """, (limit,))
            
            transactions = []
            for row in cursor.fetchall():
                tx_hash, raw_tx, timestamp, fee, status = row
                tx_data = eval(raw_tx)  # Convert string to dict
                tx_data.update({
                    'tx_hash': tx_hash,
                    'fee': fee,
                    'status': status
                })
                transactions.append(tx_data)
                
            return transactions
            
        finally:
            cursor.close()
            conn.close()
            
    def clean_mempool(self, max_age_hours=24):
        """Clean old transactions from mempool"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            
            # Delete old transactions
            cursor.execute("""
                DELETE FROM mempool
                WHERE timestamp < ?
                AND status != 'pending'
            """, (cutoff_time,))
            
            deleted = cursor.rowcount
            conn.commit()
            
            logger.info(f"Removidas {deleted} transações antigas do mempool")
            return deleted
            
        finally:
            cursor.close()
            conn.close()
            
    def get_wallet_transactions(self, address, limit=100):
        """Get transactions for a specific wallet"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT tx_hash, block_hash, tx_type,
                       from_address, to_address, amount,
                       timestamp, status
                FROM transactions
                WHERE (from_address = ? OR to_address = ?)
                AND status = 'confirmed'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (address, address, limit))
            
            transactions = []
            for row in cursor.fetchall():
                tx_hash, block_hash, tx_type, from_addr, to_addr, amount, timestamp, status = row
                
                transactions.append({
                    'tx_hash': tx_hash,
                    'block_hash': block_hash,
                    'type': tx_type,
                    'from_address': from_addr,
                    'to_address': to_addr,
                    'amount': amount,
                    'timestamp': timestamp,
                    'status': status,
                    'direction': 'received' if to_addr == address else 'sent'
                })
                
            return transactions
            
        finally:
            cursor.close()
            conn.close()
            
    def get_block_transactions(self, block_hash):
        """Get all transactions in a block"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT tx_hash, tx_type, from_address,
                       to_address, amount, timestamp,
                       status
                FROM transactions
                WHERE block_hash = ?
                ORDER BY timestamp ASC
            """, (block_hash,))
            
            transactions = []
            for row in cursor.fetchall():
                tx_hash, tx_type, from_addr, to_addr, amount, timestamp, status = row
                
                transactions.append({
                    'tx_hash': tx_hash,
                    'type': tx_type,
                    'from_address': from_addr,
                    'to_address': to_addr,
                    'amount': amount,
                    'timestamp': timestamp,
                    'status': status
                })
                
            return transactions
            
        finally:
            cursor.close()
            conn.close() 