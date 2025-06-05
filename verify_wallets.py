"""
Wallet Balance Verification Script
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

def verify_wallet_balances():
    """Verify all wallet balances"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all wallets
        cursor.execute("SELECT address, balance FROM wallets")
        wallets = cursor.fetchall()
        
        if not wallets:
            logger.error("Nenhuma carteira encontrada!")
            return
            
        logger.info(f"Verificando {len(wallets)} carteiras...")
        
        for wallet_address, stored_balance in wallets:
            # Calculate received amount (excluding mining rewards)
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
                AND tx_type != 'mining_reward'
            """, (wallet_address,))
            received = cursor.fetchone()[0]
            
            # Calculate sent amount
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE from_address = ?
                AND tx_type != 'mining_reward'
            """, (wallet_address,))
            sent = cursor.fetchone()[0]
            
            # Calculate mining rewards
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
                AND tx_type = 'mining_reward'
            """, (wallet_address,))
            rewards = cursor.fetchone()[0]
            
            # Calculate expected balance
            expected_balance = received - sent + rewards
            
            logger.info(f"\nCarteira: {wallet_address}")
            logger.info(f"Saldo armazenado: {stored_balance} LOGI")
            logger.info(f"Recebido: {received} LOGI")
            logger.info(f"Enviado: {sent} LOGI")
            logger.info(f"Recompensas mineração: {rewards} LOGI")
            logger.info(f"Saldo calculado: {expected_balance} LOGI")
            
            if abs(stored_balance - expected_balance) > 0.00001:  # Use small epsilon for float comparison
                logger.error(f"Discrepância no saldo! Diferença: {stored_balance - expected_balance} LOGI")
                
            if expected_balance < 0:
                logger.critical(f"ERRO GRAVE: Saldo negativo detectado! ({expected_balance} LOGI)")
                
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Iniciando verificação de carteiras...")
    verify_wallet_balances()

if __name__ == "__main__":
    main() 