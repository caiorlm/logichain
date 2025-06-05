"""
List Database Tables Script
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

def list_tables():
    """List all tables in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not tables:
            logger.error("Nenhuma tabela encontrada no banco de dados!")
            return
            
        logger.info("Tabelas encontradas:")
        for table in tables:
            logger.info(f"  - {table[0]}")
            # Show number of records
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            logger.info(f"    Registros: {count}")
            
            # Show first record as example
            cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1")
            example = cursor.fetchone()
            if example:
                logger.info(f"    Exemplo: {example}")
            
            logger.info("")
            
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Listando tabelas do banco de dados...")
    list_tables()

if __name__ == "__main__":
    main() 