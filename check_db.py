"""
Database structure verification script
"""

import sqlite3
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "data/blockchain/chain.db"

def check_tables():
    """Check which tables exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        logger.info(f"Tabelas existentes: {tables}")
        
        # Expected tables
        expected = {'blocks', 'transactions', 'wallets', 'mempool', 'peers'}
        missing = expected - set(tables)
        if missing:
            logger.warning(f"Tabelas faltando: {missing}")
            
        # Check schema for each existing table
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            logger.info(f"\nSchema da tabela {table}:")
            for col in columns:
                logger.info(f"  {col[1]} ({col[2]})")
                
    finally:
        cursor.close()
        conn.close()

def check_genesis_block():
    """Check if genesis block exists and is correct"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT hash, previous_hash, block_index, mining_reward
            FROM blocks 
            WHERE block_index = 0
        """)
        genesis = cursor.fetchone()
        
        if genesis:
            logger.info("\nBloco Genesis encontrado:")
            logger.info(f"  hash: {genesis[0]}")
            logger.info(f"  previous_hash: {genesis[1]}")
            logger.info(f"  block_index: {genesis[2]}")
            logger.info(f"  mining_reward: {genesis[3]}")
            
            # Check if values are correct
            zero_hash = '0' * 64
            if genesis[0] != zero_hash:
                logger.warning(f"Genesis hash incorreto: {genesis[0]}")
            if genesis[1] != zero_hash:
                logger.warning(f"Genesis previous_hash incorreto: {genesis[1]}")
            if genesis[2] != 0:
                logger.warning(f"Genesis block_index incorreto: {genesis[2]}")
            if genesis[3] != 0.0:
                logger.warning(f"Genesis mining_reward incorreto: {genesis[3]}")
        else:
            logger.warning("Bloco Genesis não encontrado!")
            
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Verificando estrutura do banco de dados...")
    check_tables()
    
    logger.info("\nVerificando bloco genesis...")
    check_genesis_block()

if __name__ == "__main__":
    main() 