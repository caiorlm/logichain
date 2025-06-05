"""
Script para recalcular saldos das carteiras a partir do histórico da blockchain
"""

import os
import sys
import sqlite3
from pathlib import Path
import logging
import time

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from blockchain.database.db_manager import get_db_connection

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_all_addresses():
    """Obtém todos os endereços únicos da blockchain"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    addresses = set()
    
    # Endereços de mineradores
    cursor.execute("SELECT DISTINCT miner_address FROM blocks WHERE miner_address IS NOT NULL")
    addresses.update(row[0] for row in cursor.fetchall())
    
    # Endereços de remetentes
    cursor.execute("SELECT DISTINCT from_address FROM transactions WHERE from_address IS NOT NULL")
    addresses.update(row[0] for row in cursor.fetchall())
    
    # Endereços de destinatários
    cursor.execute("SELECT DISTINCT to_address FROM transactions WHERE to_address IS NOT NULL")
    addresses.update(row[0] for row in cursor.fetchall())
    
    conn.close()
    return addresses

def ensure_wallet_exists(address):
    """Garante que existe um registro de carteira para o endereço"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR IGNORE INTO wallets (
            address, public_key, balance, last_updated, created_at, status
        ) VALUES (?, '', 0.0, ?, ?, 'active')
    """, (address, time.time(), time.time()))
    
    conn.commit()
    conn.close()

def calculate_mining_rewards(address):
    """Calcula total de recompensas de mineração"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COALESCE(SUM(mining_reward), 0)
        FROM blocks
        WHERE miner_address = ?
    """, (address,))
    
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total

def calculate_sent_amount(address):
    """Calcula total enviado em transações"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COALESCE(SUM(amount + COALESCE(fee, 0)), 0)
        FROM transactions
        WHERE from_address = ?
    """, (address,))
    
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total

def calculate_received_amount(address):
    """Calcula total recebido em transações"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE to_address = ?
    """, (address,))
    
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total

def update_wallet_balance(address, balance):
    """Atualiza saldo da carteira"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE wallets
        SET balance = ?,
            last_updated = ?
        WHERE address = ?
    """, (balance, time.time(), address))
    
    conn.commit()
    conn.close()

def main():
    """Executa recálculo de saldos"""
    try:
        logging.info("Iniciando recálculo de saldos...")
        
        # Obtém todos os endereços
        addresses = get_all_addresses()
        logging.info(f"Encontrados {len(addresses)} endereços únicos")
        
        # Processa cada endereço
        for i, address in enumerate(addresses, 1):
            # Garante que existe registro da carteira
            ensure_wallet_exists(address)
            
            # Calcula componentes do saldo
            mining_rewards = calculate_mining_rewards(address)
            sent_amount = calculate_sent_amount(address)
            received_amount = calculate_received_amount(address)
            
            # Calcula saldo final
            balance = mining_rewards - sent_amount + received_amount
            
            # Atualiza saldo
            update_wallet_balance(address, balance)
            
            logging.info(f"[{i}/{len(addresses)}] Atualizado saldo de {address}: {balance:.2f}")
            
        logging.info("✅ Recálculo de saldos concluído com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro ao recalcular saldos: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 