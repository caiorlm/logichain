"""
Script para verificar carteiras, transações e saldos
"""

import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
BLOCK_REWARD = 50.0

def check_wallets():
    """Verifica todas as carteiras"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Lista todas as carteiras
        cursor.execute("SELECT address FROM wallets")
        wallets = cursor.fetchall()
        
        logger.info(f"\nTotal de carteiras: {len(wallets)}")
        
        for wallet in wallets:
            address = wallet[0]
            
            # Verifica formato do endereço
            if not address.startswith("LOGI"):
                logger.error(f"Endereço inválido: {address} (deve começar com LOGI)")
                continue
                
            # Calcula saldo baseado em transações
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
            """, (address,))
            total_received = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE from_address = ?
                AND from_address != ?
            """, (address, '0' * 64))
            total_sent = cursor.fetchone()[0] or 0
            
            # Calcula recompensas de mineração
            cursor.execute("""
                SELECT COUNT(*)
                FROM blocks
                WHERE miner_address = ?
            """, (address,))
            blocks_mined = cursor.fetchone()[0] or 0
            mining_rewards = blocks_mined * BLOCK_REWARD
            
            # Saldo calculado
            calculated_balance = total_received - total_sent + mining_rewards
            
            # Saldo registrado
            cursor.execute("SELECT balance FROM wallets WHERE address = ?", (address,))
            stored_balance = cursor.fetchone()[0] or 0
            
            logger.info(f"\nCarteira: {address}")
            logger.info(f"Blocos minerados: {blocks_mined}")
            logger.info(f"Total recebido: {total_received} LOGI")
            logger.info(f"Total enviado: {total_sent} LOGI")
            logger.info(f"Recompensas mineração: {mining_rewards} LOGI")
            logger.info(f"Saldo calculado: {calculated_balance} LOGI")
            logger.info(f"Saldo armazenado: {stored_balance} LOGI")
            
            if abs(calculated_balance - stored_balance) > 0.00001:
                logger.error(f"Discrepância no saldo!")
                
    except Exception as e:
        logger.error(f"Erro verificando carteiras: {e}")
    finally:
        conn.close()

def check_transactions():
    """Verifica todas as transações"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verifica transações duplicadas
        cursor.execute("""
            SELECT tx_hash, COUNT(*)
            FROM transactions
            GROUP BY tx_hash
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            logger.error(f"Transações duplicadas encontradas: {duplicates}")
            
        # Verifica transações órfãs (sem bloco)
        cursor.execute("""
            SELECT tx_hash
            FROM transactions t
            LEFT JOIN blocks b ON t.block_hash = b.hash
            WHERE b.hash IS NULL
        """)
        orphans = cursor.fetchall()
        if orphans:
            logger.error(f"Transações órfãs encontradas: {orphans}")
            
        # Verifica transações de recompensa
        cursor.execute("""
            SELECT b.hash, b.mining_reward, t.amount
            FROM blocks b
            LEFT JOIN transactions t ON b.hash = t.block_hash
            WHERE t.from_address = ?
            AND t.amount != b.mining_reward
        """, ('0' * 64,))
        invalid_rewards = cursor.fetchall()
        if invalid_rewards:
            logger.error(f"Recompensas inválidas encontradas: {invalid_rewards}")
            
        logger.info("\nVerificação de transações concluída")
        
    except Exception as e:
        logger.error(f"Erro verificando transações: {e}")
    finally:
        conn.close()

def main():
    """Função principal"""
    logger.info("Iniciando verificação completa...")
    check_wallets()
    check_transactions()
    logger.info("\nVerificação concluída!")

if __name__ == "__main__":
    main() 