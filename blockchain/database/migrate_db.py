"""
Script de migração do banco de dados da blockchain
"""

import os
import sqlite3
import json
import shutil
from datetime import datetime
from pathlib import Path
import logging
import time

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuração de caminhos
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / 'data' / 'blockchain'
DB_PATH = DATA_DIR / 'chain.db'
BACKUP_DIR = DATA_DIR / 'backups'
NEW_DB_PATH = DATA_DIR / 'chain_new.db'
SCHEMA_PATH = ROOT_DIR / 'blockchain' / 'database' / 'schema.sql'

def backup_database():
    """Cria backup do banco de dados atual"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f'chain_backup_{timestamp}.db'
    
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_path)
        logging.info(f"Backup criado em: {backup_path}")
    return backup_path

def create_new_schema():
    """Cria novo schema do banco de dados"""
    with sqlite3.connect(NEW_DB_PATH) as conn:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        logging.info("Novo schema criado com sucesso")

def migrate_data():
    """Migra dados do banco antigo para o novo"""
    try:
        with sqlite3.connect(DB_PATH) as old_conn, \
             sqlite3.connect(NEW_DB_PATH) as new_conn:
            
            # Migra blocos
            blocks = old_conn.execute("""
                SELECT hash, block_index, timestamp, previous_hash, 
                       difficulty, nonce, miner_address, mining_reward
                FROM blocks
            """).fetchall()
            
            if blocks:
                new_conn.executemany("""
                    INSERT INTO blocks (
                        hash, block_index, timestamp, previous_hash,
                        difficulty, nonce, miner_address, mining_reward,
                        version, state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'confirmed')
                """, [(
                    block[0], block[1], block[2], block[3],
                    block[4] if block[4] is not None else 4,
                    block[5] if block[5] is not None else 0,
                    block[6],
                    block[7] if block[7] is not None else 50.0
                ) for block in blocks])
                
                logging.info(f"Migrados {len(blocks)} blocos")

            # Migra transações
            txs = old_conn.execute("""
                SELECT tx_hash, block_hash, tx_type, from_address,
                       to_address, amount, timestamp, data
                FROM transactions
            """).fetchall()
            
            if txs:
                new_conn.executemany("""
                    INSERT INTO transactions (
                        tx_hash, block_hash, tx_type, from_address,
                        to_address, amount, timestamp, data,
                        status, nonce
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', 0)
                """, txs)
                
                logging.info(f"Migradas {len(txs)} transações")

            # Atualiza contagem de transações nos blocos
            new_conn.execute("""
                UPDATE blocks 
                SET total_transactions = (
                    SELECT COUNT(*) 
                    FROM transactions 
                    WHERE transactions.block_hash = blocks.hash
                )
            """)

            # Inicializa carteiras baseado em endereços existentes
            new_conn.execute("""
                INSERT INTO wallets (
                    address, public_key, balance, last_updated,
                    created_at, status
                )
                SELECT DISTINCT 
                    miner_address,
                    '',  -- public_key vazio por enquanto
                    0.0, -- balance será recalculado depois
                    ?,   -- last_updated
                    ?,   -- created_at
                    'active'
                FROM blocks 
                WHERE miner_address IS NOT NULL
                AND miner_address NOT IN (SELECT address FROM wallets)
            """, (time.time(), time.time()))

            new_conn.execute("""
                INSERT INTO wallets (
                    address, public_key, balance, last_updated,
                    created_at, status
                )
                SELECT DISTINCT 
                    from_address,
                    '',  -- public_key vazio por enquanto
                    0.0, -- balance será recalculado depois
                    ?,   -- last_updated
                    ?,   -- created_at
                    'active'
                FROM transactions
                WHERE from_address NOT IN (SELECT address FROM wallets)
            """, (time.time(), time.time()))

            new_conn.execute("""
                INSERT INTO wallets (
                    address, public_key, balance, last_updated,
                    created_at, status
                )
                SELECT DISTINCT 
                    to_address,
                    '',  -- public_key vazio por enquanto
                    0.0, -- balance será recalculado depois
                    ?,   -- last_updated
                    ?,   -- created_at
                    'active'
                FROM transactions
                WHERE to_address IS NOT NULL
                AND to_address NOT IN (SELECT address FROM wallets)
            """, (time.time(), time.time()))

            new_conn.commit()
            
    except sqlite3.Error as e:
        logging.error(f"Erro durante migração: {e}")
        raise

def calculate_balances():
    """Recalcula todos os saldos baseado no histórico de transações"""
    with sqlite3.connect(NEW_DB_PATH) as conn:
        # Reseta todos os saldos
        conn.execute("UPDATE wallets SET balance = 0.0")
        
        # Adiciona recompensas de mineração
        conn.execute("""
            UPDATE wallets 
            SET balance = balance + (
                SELECT COALESCE(SUM(mining_reward), 0)
                FROM blocks
                WHERE blocks.miner_address = wallets.address
            ),
            last_updated = ?
        """, (time.time(),))
        
        # Subtrai valores enviados
        conn.execute("""
            UPDATE wallets 
            SET balance = balance - (
                SELECT COALESCE(SUM(amount + COALESCE(fee, 0)), 0)
                FROM transactions
                WHERE transactions.from_address = wallets.address
            ),
            last_updated = ?
        """, (time.time(),))
        
        # Adiciona valores recebidos
        conn.execute("""
            UPDATE wallets 
            SET balance = balance + (
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE transactions.to_address = wallets.address
            ),
            last_updated = ?
        """, (time.time(),))
        
        conn.commit()
        logging.info("Saldos recalculados com sucesso")

def validate_migration():
    """Valida a migração dos dados"""
    with sqlite3.connect(DB_PATH) as old_conn, \
         sqlite3.connect(NEW_DB_PATH) as new_conn:
        
        # Verifica contagem de blocos
        old_blocks = old_conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
        new_blocks = new_conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
        assert old_blocks == new_blocks, f"Contagem de blocos difere: antigo={old_blocks}, novo={new_blocks}"
        
        # Verifica contagem de transações
        old_txs = old_conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        new_txs = new_conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert old_txs == new_txs, f"Contagem de transações difere: antigo={old_txs}, novo={new_txs}"
        
        # Verifica saldos negativos
        negative_balances = new_conn.execute("""
            SELECT address, balance 
            FROM wallets 
            WHERE balance < 0
        """).fetchall()
        
        if negative_balances:
            logging.warning(f"Encontrados {len(negative_balances)} saldos negativos")
            for address, balance in negative_balances:
                logging.warning(f"Endereço {address}: {balance}")
        
        # Verifica integridade referencial
        orphan_txs = new_conn.execute("""
            SELECT tx_hash, block_hash
            FROM transactions t
            LEFT JOIN blocks b ON t.block_hash = b.hash
            WHERE b.hash IS NULL
        """).fetchall()
        
        if orphan_txs:
            logging.warning(f"Encontradas {len(orphan_txs)} transações órfãs")
            for tx_hash, block_hash in orphan_txs:
                logging.warning(f"Transação {tx_hash} referencia bloco inexistente {block_hash}")
        
        logging.info("Validação da migração concluída com sucesso")

def finalize_migration():
    """Finaliza a migração substituindo o banco antigo pelo novo"""
    try:
        if NEW_DB_PATH.exists():
            if DB_PATH.exists():
                DB_PATH.unlink()
            NEW_DB_PATH.rename(DB_PATH)
            logging.info("Migração finalizada com sucesso")
    except PermissionError:
        logging.error("Erro ao finalizar migração: banco de dados em uso")
        logging.info("Por favor, feche todas as conexões com o banco e execute novamente")
        raise

def main():
    try:
        logging.info("Iniciando processo de migração")
        backup_database()
        create_new_schema()
        migrate_data()
        calculate_balances()
        validate_migration()
        finalize_migration()
        logging.info("Processo de migração concluído com sucesso")
    except Exception as e:
        logging.error(f"Erro durante o processo de migração: {e}")
        raise

if __name__ == "__main__":
    main() 