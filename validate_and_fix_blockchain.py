"""
Blockchain Ecosystem Validation and Fix Script
"""

import sqlite3
import logging
import hashlib
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
DIFFICULTY = 4
BLOCK_REWARD = 50.0
ZERO_ADDRESS = "0" * 64
ZERO_HASH = "0" * 64

def init_database():
    """Initialize or fix database schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verify and create/fix tables
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mempool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                raw_transaction TEXT NOT NULL,
                timestamp REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending'
            )
        """)
        
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
        logger.info("Schema do banco de dados verificado/corrigido")
        
    finally:
        cursor.close()
        conn.close()

def verify_and_fix_genesis():
    """Verify and fix genesis block if needed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check genesis block
        cursor.execute("""
            SELECT hash, previous_hash, mining_reward, miner_address
            FROM blocks WHERE block_index = 0
        """)
        genesis = cursor.fetchone()
        
        if not genesis:
            # Create genesis block
            timestamp = time.time()
            cursor.execute("""
                INSERT INTO blocks (
                    hash, block_index, timestamp, previous_hash,
                    difficulty, nonce, miner_address, mining_reward,
                    state
                ) VALUES (?, 0, ?, ?, 4, 0, ?, 0.0, 'confirmed')
            """, (ZERO_HASH, timestamp, ZERO_HASH, ZERO_ADDRESS))
            logger.info("Bloco gênesis criado")
            
        elif (genesis[0] != ZERO_HASH or genesis[1] != ZERO_HASH or 
              genesis[2] != 0.0 or genesis[3] != ZERO_ADDRESS):
            # Fix genesis block
            cursor.execute("""
                UPDATE blocks 
                SET hash = ?, previous_hash = ?, mining_reward = 0.0,
                    miner_address = ?
                WHERE block_index = 0
            """, (ZERO_HASH, ZERO_HASH, ZERO_ADDRESS))
            logger.info("Bloco gênesis corrigido")
            
        conn.commit()
        
    finally:
        cursor.close()
        conn.close()

def calculate_block_hash(block_data):
    """Calculate block hash"""
    data_string = f"{block_data['timestamp']}{block_data['previous_hash']}{block_data['nonce']}"
    return hashlib.sha256(data_string.encode()).hexdigest()

def verify_and_fix_chain():
    """Verify and fix blockchain integrity"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT block_index, hash, previous_hash, timestamp, 
                   nonce, difficulty
            FROM blocks 
            ORDER BY block_index ASC
        """)
        blocks = cursor.fetchall()
        
        previous_hash = ZERO_HASH
        fixed_blocks = 0
        
        for block in blocks:
            (block_index, block_hash, prev_hash, timestamp,
             nonce, difficulty) = block
             
            # Skip genesis
            if block_index == 0:
                previous_hash = ZERO_HASH
                continue
                
            # Verify previous_hash linkage
            if prev_hash != previous_hash:
                cursor.execute("""
                    UPDATE blocks 
                    SET previous_hash = ?
                    WHERE block_index = ?
                """, (previous_hash, block_index))
                fixed_blocks += 1
                logger.info(f"Corrigido encadeamento do bloco {block_index}")
            
            # Verify/fix block hash
            block_data = {
                'timestamp': timestamp,
                'previous_hash': previous_hash,
                'nonce': nonce
            }
            calculated_hash = calculate_block_hash(block_data)
            
            if (block_hash != calculated_hash or 
                not block_hash.startswith('0' * difficulty)):
                cursor.execute("""
                    UPDATE blocks 
                    SET hash = ?
                    WHERE block_index = ?
                """, (calculated_hash, block_index))
                fixed_blocks += 1
                logger.info(f"Corrigido hash do bloco {block_index}")
            
            previous_hash = calculated_hash
            
        if fixed_blocks > 0:
            conn.commit()
            logger.info(f"Corrigidos {fixed_blocks} blocos")
        else:
            logger.info("Cadeia de blocos íntegra")
            
    finally:
        cursor.close()
        conn.close()

def verify_and_fix_transactions():
    """Verify and fix transactions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Find orphaned transactions
        cursor.execute("""
            SELECT t.id, t.tx_hash
            FROM transactions t
            LEFT JOIN blocks b ON t.block_hash = b.hash
            WHERE b.hash IS NULL
        """)
        orphans = cursor.fetchall()
        
        if orphans:
            logger.warning(f"Encontradas {len(orphans)} transações órfãs")
            for orphan in orphans:
                cursor.execute("DELETE FROM transactions WHERE id = ?", (orphan[0],))
            conn.commit()
            logger.info("Transações órfãs removidas")
            
        # Find duplicate transactions
        cursor.execute("""
            SELECT tx_hash, COUNT(*) as count
            FROM transactions
            GROUP BY tx_hash
            HAVING count > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            logger.warning(f"Encontradas {len(duplicates)} transações duplicadas")
            for dup in duplicates:
                cursor.execute("""
                    DELETE FROM transactions 
                    WHERE tx_hash = ? 
                    AND id NOT IN (
                        SELECT MIN(id) 
                        FROM transactions 
                        WHERE tx_hash = ?
                    )
                """, (dup[0], dup[0]))
            conn.commit()
            logger.info("Transações duplicadas removidas")
            
    finally:
        cursor.close()
        conn.close()

def rebuild_wallets():
    """Rebuild wallets table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Clear wallets table
        cursor.execute("DELETE FROM wallets")
        
        # Get all unique addresses
        cursor.execute("""
            SELECT DISTINCT address FROM (
                SELECT from_address as address FROM transactions
                WHERE from_address != ?
                UNION
                SELECT to_address as address FROM transactions
                WHERE to_address IS NOT NULL
            )
        """, (ZERO_ADDRESS,))
        addresses = [addr[0] for addr in cursor.fetchall()]
        
        logger.info(f"Reconstruindo {len(addresses)} carteiras...")
        
        for address in addresses:
            # Calculate received amount (excluding mining rewards)
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
                AND tx_type != 'mining_reward'
            """, (address,))
            received = cursor.fetchone()[0]
            
            # Calculate sent amount
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE from_address = ?
                AND tx_type != 'mining_reward'
            """, (address,))
            sent = cursor.fetchone()[0]
            
            # Calculate mining rewards
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
                AND tx_type = 'mining_reward'
            """, (address,))
            rewards = cursor.fetchone()[0]
            
            # Calculate balance
            balance = received - sent + rewards
            
            # Get timestamps
            cursor.execute("""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM transactions
                WHERE from_address = ? OR to_address = ?
            """, (address, address))
            created_at, last_updated = cursor.fetchone()
            
            # Insert wallet
            cursor.execute("""
                INSERT INTO wallets (
                    address, public_key, balance, created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                address,
                address,  # Using address as public_key for now
                balance,
                created_at,
                last_updated
            ))
            
            logger.info(f"Carteira {address}: {balance} LOGI")
            
        conn.commit()
        logger.info("Carteiras reconstruídas")
        
    finally:
        cursor.close()
        conn.close()

def verify_mining_rewards():
    """Verify mining rewards distribution"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT m.miner_address,
                   COUNT(*) as blocks_mined,
                   COUNT(*) * ? as expected_reward,
                   COALESCE(SUM(t.amount), 0) as actual_reward
            FROM blocks m
            LEFT JOIN transactions t ON t.block_hash = m.hash 
                AND t.tx_type = 'mining_reward'
                AND t.from_address = ?
            WHERE m.miner_address IS NOT NULL
            AND m.block_index > 0
            GROUP BY m.miner_address
        """, (BLOCK_REWARD, ZERO_ADDRESS))
        
        rewards = cursor.fetchall()
        
        logger.info("\nVerificando recompensas de mineração:")
        for miner, blocks, expected, actual in rewards:
            logger.info(f"\nMinerador: {miner}")
            logger.info(f"Blocos minerados: {blocks}")
            logger.info(f"Recompensa esperada: {expected} LOGI")
            logger.info(f"Recompensa recebida: {actual} LOGI")
            
            if abs(expected - actual) > 0.00001:
                logger.warning(f"Discrepância nas recompensas! Diferença: {expected - actual} LOGI")
                
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Iniciando validação e correção da blockchain...")
    
    # 1. Initialize/fix database schema
    logger.info("\n1. Verificando schema do banco de dados...")
    init_database()
    
    # 2. Verify/fix genesis block
    logger.info("\n2. Verificando bloco gênesis...")
    verify_and_fix_genesis()
    
    # 3. Verify/fix blockchain integrity
    logger.info("\n3. Verificando integridade da cadeia...")
    verify_and_fix_chain()
    
    # 4. Verify/fix transactions
    logger.info("\n4. Verificando transações...")
    verify_and_fix_transactions()
    
    # 5. Rebuild wallets
    logger.info("\n5. Reconstruindo carteiras...")
    rebuild_wallets()
    
    # 6. Verify mining rewards
    logger.info("\n6. Verificando recompensas de mineração...")
    verify_mining_rewards()
    
    logger.info("\nValidação e correção concluídas!")

if __name__ == "__main__":
    main() 