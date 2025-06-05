"""
Rebuild Wallets Table Script
"""

import sqlite3
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "data/blockchain/chain.db"

def rebuild_wallets():
    """Rebuild wallets table from transactions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Clear wallets table
        cursor.execute("DELETE FROM wallets")
        
        # Get all unique addresses from transactions
        cursor.execute("""
            SELECT DISTINCT address FROM (
                SELECT from_address as address FROM transactions
                WHERE from_address != '0000000000000000000000000000000000000000000000000000000000000000'
                UNION
                SELECT to_address as address FROM transactions
                WHERE to_address IS NOT NULL
            )
        """)
        addresses = [addr[0] for addr in cursor.fetchall()]
        
        logger.info(f"Encontrados {len(addresses)} endereços únicos")
        
        # For each address
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
            
            # Get first transaction timestamp for this address
            cursor.execute("""
                SELECT MIN(timestamp)
                FROM transactions
                WHERE from_address = ? OR to_address = ?
            """, (address, address))
            created_at = cursor.fetchone()[0]
            
            # Get last transaction timestamp for this address
            cursor.execute("""
                SELECT MAX(timestamp)
                FROM transactions
                WHERE from_address = ? OR to_address = ?
            """, (address, address))
            last_updated = cursor.fetchone()[0]
            
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
            
            logger.info(f"\nCarteira: {address}")
            logger.info(f"  Recebido: {received} LOGI")
            logger.info(f"  Enviado: {sent} LOGI")
            logger.info(f"  Recompensas: {rewards} LOGI")
            logger.info(f"  Saldo final: {balance} LOGI")
            
            if balance < 0:
                logger.critical(f"  ERRO GRAVE: Saldo negativo detectado!")
        
        conn.commit()
        logger.info("\nReconstrução da tabela de carteiras concluída!")
        
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Iniciando reconstrução da tabela de carteiras...")
    rebuild_wallets()

if __name__ == "__main__":
    main() 