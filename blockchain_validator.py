"""
Blockchain Validation and Correction System
"""

import sqlite3
import logging
import hashlib
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from wallet_manager import WalletManager
from mining_manager import MiningManager
from transaction_manager import TransactionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='data/logs/blockchain_validator.log'
)
logger = logging.getLogger(__name__)

class BlockchainValidator:
    def __init__(self, db_path="data/blockchain/chain.db"):
        self.db_path = db_path
        self.wallet_manager = WalletManager(db_path)
        self.mining_manager = MiningManager()
        self.transaction_manager = TransactionManager()
        self.block_reward = 50.0  # LOGI per block
        self.difficulty = 4
        
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
        
    def validate_and_fix_blockchain(self) -> Dict:
        """Main validation and correction function"""
        logger.info("Iniciando validação e correção da blockchain...")
        
        # Initialize report
        report = {
            'invalid_blocks': [],
            'orphan_transactions': [],
            'incorrect_balances': [],
            'fixed_mining_rewards': [],
            'fixed_block_hashes': [],
            'created_wallets': [],
            'start_time': time.time(),
            'end_time': None
        }
        
        try:
            # 1. Fix mining rewards
            self._fix_mining_rewards(report)
            
            # 2. Fix block chain and hashes
            self._fix_block_chain(report)
            
            # 3. Handle orphan transactions
            self._handle_orphan_transactions(report)
            
            # 4. Rebuild wallet table
            self._rebuild_wallet_table(report)
            
            report['end_time'] = time.time()
            report['success'] = True
            
        except Exception as e:
            logger.error(f"Erro durante validação: {str(e)}")
            report['error'] = str(e)
            report['success'] = False
            report['end_time'] = time.time()
            
        # Save report
        self._save_audit_report(report)
        return report
        
    def _fix_mining_rewards(self, report: Dict):
        """Fix missing mining rewards"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all blocks except genesis
            cursor.execute("""
                SELECT block_index, hash, miner_address
                FROM blocks
                WHERE block_index > 0
                ORDER BY block_index ASC
            """)
            blocks = cursor.fetchall()
            
            for block_index, block_hash, miner_address in blocks:
                # Check if mining reward exists
                cursor.execute("""
                    SELECT tx_hash
                    FROM transactions
                    WHERE block_hash = ?
                    AND tx_type = 'mining_reward'
                    AND from_address = ?
                """, (block_hash, "0" * 64))
                
                reward_tx = cursor.fetchone()
                
                if not reward_tx:
                    # Create missing reward transaction
                    reward_tx_hash = f"reward_{block_hash}"
                    cursor.execute("""
                        INSERT INTO transactions (
                            tx_hash, block_hash, tx_type,
                            from_address, to_address, amount,
                            timestamp, status
                        ) VALUES (?, ?, 'mining_reward', ?, ?, ?, ?, 'confirmed')
                    """, (
                        reward_tx_hash, block_hash,
                        "0" * 64, miner_address,
                        self.block_reward, time.time()
                    ))
                    
                    # Update miner wallet
                    self.wallet_manager.update_miner_wallet(
                        miner_address,
                        self.block_reward,
                        block_hash
                    )
                    
                    report['fixed_mining_rewards'].append({
                        'block_index': block_index,
                        'block_hash': block_hash,
                        'miner_address': miner_address,
                        'reward': self.block_reward
                    })
                    
                    logger.info(f"Recompensa de mineração criada para bloco {block_index}")
                    
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()
            
    def _fix_block_chain(self, report: Dict):
        """Fix block chain and hashes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all blocks ordered by index
            cursor.execute("""
                SELECT block_index, hash, previous_hash,
                       timestamp, nonce, miner_address
                FROM blocks
                ORDER BY block_index ASC
            """)
            blocks = cursor.fetchall()
            
            previous_hash = "0" * 64  # Genesis block previous hash
            
            for block in blocks:
                block_index, block_hash, prev_hash, timestamp, nonce, miner_address = block
                
                # Skip genesis block
                if block_index == 0:
                    previous_hash = block_hash
                    continue
                
                # Check if previous hash matches
                if prev_hash != previous_hash:
                    # Update previous hash
                    cursor.execute("""
                        UPDATE blocks
                        SET previous_hash = ?
                        WHERE block_index = ?
                    """, (previous_hash, block_index))
                    
                    report['fixed_block_hashes'].append({
                        'block_index': block_index,
                        'old_prev_hash': prev_hash,
                        'new_prev_hash': previous_hash
                    })
                    
                    logger.info(f"Hash anterior corrigido para bloco {block_index}")
                
                # Calculate and verify block hash
                block_data = {
                    'timestamp': timestamp,
                    'previous_hash': previous_hash,
                    'nonce': nonce
                }
                calculated_hash = self.mining_manager.calculate_block_hash(block_data)
                
                if calculated_hash != block_hash:
                    # Update block hash
                    cursor.execute("""
                        UPDATE blocks
                        SET hash = ?
                        WHERE block_index = ?
                    """, (calculated_hash, block_index))
                    
                    # Update transactions referencing this block
                    cursor.execute("""
                        UPDATE transactions
                        SET block_hash = ?
                        WHERE block_hash = ?
                    """, (calculated_hash, block_hash))
                    
                    report['fixed_block_hashes'].append({
                        'block_index': block_index,
                        'old_hash': block_hash,
                        'new_hash': calculated_hash
                    })
                    
                    logger.info(f"Hash do bloco {block_index} corrigido")
                    
                previous_hash = calculated_hash
                
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()
            
    def _handle_orphan_transactions(self, report: Dict):
        """Handle orphan transactions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Find orphan transactions
            cursor.execute("""
                SELECT t.tx_hash, t.tx_type, t.from_address,
                       t.to_address, t.amount, t.timestamp
                FROM transactions t
                LEFT JOIN blocks b ON t.block_hash = b.hash
                WHERE b.hash IS NULL
                AND t.tx_type != 'mining_reward'
            """)
            orphans = cursor.fetchall()
            
            for tx in orphans:
                tx_hash, tx_type, from_addr, to_addr, amount, timestamp = tx
                
                # Check if transaction is still valid
                if time.time() - timestamp < 24 * 3600:  # Less than 24h old
                    # Move to mempool
                    cursor.execute("""
                        INSERT INTO mempool (
                            tx_hash, raw_transaction,
                            timestamp, fee, status
                        ) VALUES (?, ?, ?, 0.0, 'pending')
                    """, (
                        tx_hash,
                        str({
                            'from_address': from_addr,
                            'to_address': to_addr,
                            'amount': amount,
                            'timestamp': timestamp
                        }),
                        timestamp
                    ))
                    
                    report['orphan_transactions'].append({
                        'tx_hash': tx_hash,
                        'action': 'moved_to_mempool'
                    })
                else:
                    report['orphan_transactions'].append({
                        'tx_hash': tx_hash,
                        'action': 'discarded'
                    })
                    
                # Remove from transactions table
                cursor.execute("""
                    DELETE FROM transactions
                    WHERE tx_hash = ?
                """, (tx_hash,))
                
            conn.commit()
            logger.info(f"Processadas {len(orphans)} transações órfãs")
            
        finally:
            cursor.close()
            conn.close()
            
    def _rebuild_wallet_table(self, report: Dict):
        """Rebuild wallet table from transactions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create temporary table
            cursor.execute("""
                CREATE TEMPORARY TABLE temp_wallets (
                    address TEXT PRIMARY KEY,
                    balance REAL DEFAULT 0.0,
                    total_received REAL DEFAULT 0.0,
                    total_sent REAL DEFAULT 0.0,
                    mining_rewards REAL DEFAULT 0.0,
                    blocks_mined INTEGER DEFAULT 0,
                    transaction_count INTEGER DEFAULT 0
                )
            """)
            
            # Process all confirmed transactions
            cursor.execute("""
                SELECT tx_type, from_address, to_address, amount
                FROM transactions
                WHERE status = 'confirmed'
                ORDER BY timestamp ASC
            """)
            
            for tx in cursor.fetchall():
                tx_type, from_addr, to_addr, amount = tx
                
                if tx_type == 'mining_reward':
                    # Update miner wallet
                    cursor.execute("""
                        INSERT INTO temp_wallets (
                            address, balance, mining_rewards,
                            blocks_mined, transaction_count
                        ) VALUES (?, ?, ?, 1, 1)
                        ON CONFLICT(address) DO UPDATE SET
                            balance = balance + ?,
                            mining_rewards = mining_rewards + ?,
                            blocks_mined = blocks_mined + 1,
                            transaction_count = transaction_count + 1
                    """, (to_addr, amount, amount, amount, amount))
                else:
                    # Update sender wallet
                    cursor.execute("""
                        INSERT INTO temp_wallets (
                            address, balance, total_sent,
                            transaction_count
                        ) VALUES (?, -?, ?, 1)
                        ON CONFLICT(address) DO UPDATE SET
                            balance = balance - ?,
                            total_sent = total_sent + ?,
                            transaction_count = transaction_count + 1
                    """, (from_addr, amount, amount, amount, amount))
                    
                    # Update receiver wallet
                    cursor.execute("""
                        INSERT INTO temp_wallets (
                            address, balance, total_received,
                            transaction_count
                        ) VALUES (?, ?, ?, 1)
                        ON CONFLICT(address) DO UPDATE SET
                            balance = balance + ?,
                            total_received = total_received + ?,
                            transaction_count = transaction_count + 1
                    """, (to_addr, amount, amount, amount, amount))
                    
            # Find wallets with negative balance
            cursor.execute("""
                SELECT address, balance
                FROM temp_wallets
                WHERE balance < 0
            """)
            negative_balances = cursor.fetchall()
            
            if negative_balances:
                report['incorrect_balances'].extend([
                    {'address': addr, 'balance': bal}
                    for addr, bal in negative_balances
                ])
                raise Exception(f"Encontradas {len(negative_balances)} carteiras com saldo negativo")
                
            # Replace wallet table with corrected data
            cursor.execute("DELETE FROM wallets")
            
            cursor.execute("""
                INSERT INTO wallets (
                    address, public_key, balance, type,
                    total_received, total_sent, mining_rewards,
                    blocks_mined, transaction_count,
                    created_at, last_updated, status
                )
                SELECT 
                    address, address as public_key,
                    balance,
                    CASE WHEN blocks_mined > 0 THEN 'miner' ELSE 'user' END,
                    total_received, total_sent, mining_rewards,
                    blocks_mined, transaction_count,
                    ? as created_at,
                    ? as last_updated,
                    'active' as status
                FROM temp_wallets
            """, (time.time(), time.time()))
            
            conn.commit()
            logger.info("Tabela de carteiras reconstruída com sucesso")
            
        finally:
            cursor.execute("DROP TABLE IF EXISTS temp_wallets")
            cursor.close()
            conn.close()
            
    def _save_audit_report(self, report: Dict):
        """Save audit report to file"""
        if not os.path.exists('data/reports'):
            os.makedirs('data/reports')
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'data/reports/audit_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Relatório de auditoria salvo em {filename}")
        
    def audit_blockchain(self) -> Dict:
        """Run audit without fixing issues"""
        logger.info("Iniciando auditoria da blockchain...")
        
        report = {
            'invalid_blocks': [],
            'orphan_transactions': [],
            'incorrect_balances': [],
            'missing_mining_rewards': [],
            'incorrect_hashes': [],
            'start_time': time.time(),
            'end_time': None
        }
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Check blocks
            cursor.execute("""
                SELECT block_index, hash, previous_hash,
                       timestamp, nonce, miner_address
                FROM blocks
                ORDER BY block_index ASC
            """)
            blocks = cursor.fetchall()
            
            previous_hash = "0" * 64
            for block in blocks:
                block_index, block_hash, prev_hash, timestamp, nonce, miner_address = block
                
                if block_index > 0:
                    # Check previous hash
                    if prev_hash != previous_hash:
                        report['invalid_blocks'].append({
                            'block_index': block_index,
                            'error': 'invalid_previous_hash',
                            'expected': previous_hash,
                            'found': prev_hash
                        })
                        
                    # Check mining reward
                    cursor.execute("""
                        SELECT tx_hash
                        FROM transactions
                        WHERE block_hash = ?
                        AND tx_type = 'mining_reward'
                    """, (block_hash,))
                    
                    if not cursor.fetchone():
                        report['missing_mining_rewards'].append({
                            'block_index': block_index,
                            'block_hash': block_hash,
                            'miner_address': miner_address
                        })
                        
                # Verify block hash
                block_data = {
                    'timestamp': timestamp,
                    'previous_hash': previous_hash if block_index > 0 else "0" * 64,
                    'nonce': nonce
                }
                calculated_hash = self.mining_manager.calculate_block_hash(block_data)
                
                if calculated_hash != block_hash:
                    report['incorrect_hashes'].append({
                        'block_index': block_index,
                        'current_hash': block_hash,
                        'calculated_hash': calculated_hash
                    })
                    
                previous_hash = block_hash
                
            # 2. Find orphan transactions
            cursor.execute("""
                SELECT t.tx_hash
                FROM transactions t
                LEFT JOIN blocks b ON t.block_hash = b.hash
                WHERE b.hash IS NULL
                AND t.tx_type != 'mining_reward'
            """)
            
            orphans = cursor.fetchall()
            report['orphan_transactions'].extend([
                {'tx_hash': tx[0]} for tx in orphans
            ])
            
            # 3. Check wallet balances
            cursor.execute("""
                SELECT address, balance
                FROM wallets
                WHERE balance < 0
            """)
            
            negative_balances = cursor.fetchall()
            report['incorrect_balances'].extend([
                {'address': addr, 'balance': bal}
                for addr, bal in negative_balances
            ])
            
            report['end_time'] = time.time()
            report['success'] = True
            
        except Exception as e:
            logger.error(f"Erro durante auditoria: {str(e)}")
            report['error'] = str(e)
            report['success'] = False
            report['end_time'] = time.time()
            
        finally:
            cursor.close()
            conn.close()
            
        # Save report
        self._save_audit_report(report)
        return report 