"""
Check Wallets Table Script
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

def check_wallets_table():
    """Check if wallets table exists and show its structure"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='wallets'
        """)
        if not cursor.fetchone():
            logger.error("Tabela 'wallets' não existe!")
            return
            
        # Show table structure
        logger.info("Estrutura da tabela 'wallets':")
        cursor.execute("PRAGMA table_info(wallets)")
        for col in cursor.fetchall():
            logger.info(f"  {col[1]} ({col[2]})")
            
        # Count records
        cursor.execute("SELECT COUNT(*) FROM wallets")
        count = cursor.fetchone()[0]
        logger.info(f"\nTotal de carteiras: {count}")
        
        # Show all wallets if any exist
        if count > 0:
            cursor.execute("SELECT * FROM wallets")
            wallets = cursor.fetchall()
            logger.info("\nCarteiras encontradas:")
            for wallet in wallets:
                logger.info(f"  {wallet}")
                
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Verificando tabela de carteiras...")
    check_wallets_table()

if __name__ == "__main__":
    main() 