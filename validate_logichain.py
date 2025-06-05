"""
Validador completo da LogiChain
Verifica todos os aspectos do sistema
"""

import logging
import sqlite3
import json
import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
BLOCKS_FILE = "data/blockchain/blocks.json"
INITIAL_REWARD = 50.0
HALVING_INTERVAL = 210_000
MAX_SUPPLY = 21_000_000

class LogiChainValidator:
    """Validador completo da LogiChain"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.blocks = []
        self.transactions = set()
        self.balances = {}
        self.total_supply = Decimal('0')
        
    def validate_all(self) -> bool:
        """Executa todas as validações"""
        try:
            logger.info("Iniciando validação completa da LogiChain...")
            
            # 1. Estrutura da blockchain
            if not self.validate_blockchain_structure():
                return False
                
            # 2. Mineração
            if not self.validate_mining():
                return False
                
            # 3. Wallets
            if not self.validate_wallets():
                return False
                
            # 4. Recompensas
            if not self.validate_rewards():
                return False
                
            # 5. Transações
            if not self.validate_transactions():
                return False
                
            # 6. Saldos
            if not self.validate_balances():
                return False
                
            logger.info("Validação completa concluída com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"Erro durante validação: {e}")
            return False
            
        finally:
            self.conn.close()
            
    def validate_blockchain_structure(self) -> bool:
        """Valida estrutura da blockchain"""
        try:
            logger.info("Validando estrutura da blockchain...")
            
            # Verifica tabelas
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in self.cursor.fetchall()}
            required_tables = {'blocks', 'transactions', 'wallets', 'mempool', 'peers'}
            
            if not required_tables.issubset(tables):
                missing = required_tables - tables
                logger.error(f"Tabelas faltando: {missing}")
                return False
                
            # Verifica colunas da tabela blocks
            self.cursor.execute("PRAGMA table_info(blocks)")
            columns = {row[1] for row in self.cursor.fetchall()}
            required_columns = {
                'id', 'hash', 'block_index', 'timestamp', 'previous_hash',
                'difficulty', 'nonce', 'miner_address', 'mining_reward',
                'merkle_root', 'version', 'state', 'total_transactions',
                'size_bytes'
            }
            
            if not required_columns.issubset(columns):
                missing = required_columns - columns
                logger.error(f"Colunas faltando na tabela blocks: {missing}")
                return False
                
            # Verifica integridade da chain
            self.cursor.execute("""
                SELECT b1.block_index, b1.hash, b1.previous_hash, b2.hash
                FROM blocks b1
                LEFT JOIN blocks b2 ON b1.previous_hash = b2.hash
                WHERE b1.block_index > 0
                  AND (b2.hash IS NULL OR b1.block_index != b2.block_index + 1)
            """)
            
            invalid_links = self.cursor.fetchall()
            if invalid_links:
                logger.error(f"Links inválidos encontrados: {invalid_links}")
                return False
                
            logger.info("Estrutura da blockchain válida")
            return True
            
        except Exception as e:
            logger.error(f"Erro validando estrutura: {e}")
            return False
            
    def validate_mining(self) -> bool:
        """Valida aspectos da mineração"""
        try:
            logger.info("Validando mineração...")
            
            # Verifica dificuldade dos blocos
            self.cursor.execute("""
                SELECT hash, difficulty
                FROM blocks
                WHERE NOT (hash LIKE '0000%')
            """)
            
            invalid_difficulty = self.cursor.fetchall()
            if invalid_difficulty:
                logger.error(f"Blocos com dificuldade inválida: {invalid_difficulty}")
                return False
                
            # Verifica timestamps
            self.cursor.execute("""
                SELECT b1.block_index, b1.timestamp, b2.timestamp
                FROM blocks b1
                JOIN blocks b2 ON b1.block_index = b2.block_index + 1
                WHERE b1.timestamp <= b2.timestamp
            """)
            
            invalid_timestamps = self.cursor.fetchall()
            if invalid_timestamps:
                logger.error(f"Timestamps inválidos: {invalid_timestamps}")
                return False
                
            logger.info("Mineração válida")
            return True
            
        except Exception as e:
            logger.error(f"Erro validando mineração: {e}")
            return False
            
    def validate_wallets(self) -> bool:
        """Valida wallets"""
        try:
            logger.info("Validando wallets...")
            
            # Verifica endereços válidos
            self.cursor.execute("""
                SELECT DISTINCT miner_address 
                FROM blocks
                WHERE miner_address NOT LIKE 'LOGI%'
            """)
            
            invalid_miners = self.cursor.fetchall()
            if invalid_miners:
                logger.error(f"Endereços de mineradores inválidos: {invalid_miners}")
                return False
                
            # Verifica wallets na tabela de wallets
            self.cursor.execute("""
                SELECT DISTINCT w.address
                FROM wallets w
                LEFT JOIN (
                    SELECT miner_address as address FROM blocks
                    UNION
                    SELECT from_address as address FROM transactions
                    UNION
                    SELECT to_address as address FROM transactions
                ) a ON w.address = a.address
                WHERE a.address IS NULL
            """)
            
            unused_wallets = self.cursor.fetchall()
            if unused_wallets:
                logger.warning(f"Wallets sem uso: {unused_wallets}")
                
            logger.info("Wallets válidas")
            return True
            
        except Exception as e:
            logger.error(f"Erro validando wallets: {e}")
            return False
            
    def validate_rewards(self) -> bool:
        """Valida recompensas de mineração"""
        try:
            logger.info("Validando recompensas...")
            
            # Verifica recompensas por bloco
            self.cursor.execute("""
                SELECT block_index, mining_reward
                FROM blocks
                WHERE mining_reward > (
                    SELECT 50.0 / POWER(2, FLOOR(block_index / 210000))
                )
            """)
            
            invalid_rewards = self.cursor.fetchall()
            if invalid_rewards:
                logger.error(f"Recompensas inválidas: {invalid_rewards}")
                return False
                
            # Verifica transações de recompensa
            self.cursor.execute("""
                SELECT b.block_index, b.mining_reward, t.amount
                FROM blocks b
                LEFT JOIN transactions t ON b.hash = t.block_hash
                WHERE t.from_address = ? 
                  AND t.amount != b.mining_reward
            """, ('0' * 64,))
            
            mismatched_rewards = self.cursor.fetchall()
            if mismatched_rewards:
                logger.error(f"Recompensas não correspondem: {mismatched_rewards}")
                return False
                
            logger.info("Recompensas válidas")
            return True
            
        except Exception as e:
            logger.error(f"Erro validando recompensas: {e}")
            return False
            
    def validate_transactions(self) -> bool:
        """Valida transações"""
        try:
            logger.info("Validando transações...")
            
            # Verifica transações duplicadas
            self.cursor.execute("""
                SELECT tx_hash, COUNT(*)
                FROM transactions
                GROUP BY tx_hash
                HAVING COUNT(*) > 1
            """)
            
            duplicates = self.cursor.fetchall()
            if duplicates:
                logger.error(f"Transações duplicadas: {duplicates}")
                return False
                
            # Verifica valores negativos
            self.cursor.execute("""
                SELECT tx_hash, amount
                FROM transactions
                WHERE amount <= 0
            """)
            
            invalid_amounts = self.cursor.fetchall()
            if invalid_amounts:
                logger.error(f"Valores inválidos: {invalid_amounts}")
                return False
                
            # Verifica transações sem bloco
            self.cursor.execute("""
                SELECT tx_hash
                FROM transactions t
                LEFT JOIN blocks b ON t.block_hash = b.hash
                WHERE b.hash IS NULL
            """)
            
            orphan_txs = self.cursor.fetchall()
            if orphan_txs:
                logger.error(f"Transações órfãs: {orphan_txs}")
                return False
                
            logger.info("Transações válidas")
            return True
            
        except Exception as e:
            logger.error(f"Erro validando transações: {e}")
            return False
            
    def validate_balances(self) -> bool:
        """Valida saldos"""
        try:
            logger.info("Validando saldos...")
            
            # Calcula saldos
            self.cursor.execute("""
                WITH inflow AS (
                    SELECT to_address as address,
                           SUM(amount) as received
                    FROM transactions
                    GROUP BY to_address
                ),
                outflow AS (
                    SELECT from_address as address,
                           SUM(amount) as sent
                    FROM transactions
                    WHERE from_address != ?
                    GROUP BY from_address
                ),
                mining_rewards AS (
                    SELECT miner_address as address,
                           SUM(mining_reward) as rewards
                    FROM blocks
                    GROUP BY miner_address
                )
                SELECT 
                    COALESCE(i.address, o.address, m.address) as address,
                    COALESCE(i.received, 0) - COALESCE(o.sent, 0) + COALESCE(m.rewards, 0) as balance
                FROM inflow i
                FULL OUTER JOIN outflow o ON i.address = o.address
                FULL OUTER JOIN mining_rewards m ON i.address = m.address
                WHERE COALESCE(i.received, 0) - COALESCE(o.sent, 0) + COALESCE(m.rewards, 0) < 0
            """, ('0' * 64,))
            
            negative_balances = self.cursor.fetchall()
            if negative_balances:
                logger.error(f"Saldos negativos encontrados: {negative_balances}")
                return False
                
            # Verifica supply total
            self.cursor.execute("""
                SELECT SUM(mining_reward)
                FROM blocks
            """)
            total_supply = self.cursor.fetchone()[0] or 0
            
            if total_supply > MAX_SUPPLY:
                logger.error(f"Supply total excede o máximo: {total_supply} > {MAX_SUPPLY}")
                return False
                
            logger.info("Saldos válidos")
            return True
            
        except Exception as e:
            logger.error(f"Erro validando saldos: {e}")
            return False

def main():
    """Função principal"""
    validator = LogiChainValidator()
    success = validator.validate_all()
    
    if success:
        logger.info("Sistema LogiChain validado com sucesso!")
    else:
        logger.error("Falha na validação do sistema LogiChain")
        
if __name__ == "__main__":
    main() 