"""
Script de migração do banco de dados
Atualiza o esquema e corrige inconsistências
"""

import sqlite3
import os
import json
from typing import List, Dict, Tuple
from datetime import datetime
from ..core.genesis_block import GenesisBlock

DB_PATH = os.path.join(os.path.dirname(__file__), 'blockchain.db')
BACKUP_PATH = os.path.join(os.path.dirname(__file__), 'blockchain.db.bak')

def backup_database():
    """Cria backup do banco de dados atual"""
    if os.path.exists(DB_PATH):
        import shutil
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"Backup criado em {BACKUP_PATH}")

def get_current_schema(cursor) -> List[str]:
    """Retorna o schema atual das tabelas"""
    tables = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    for table in cursor.fetchall():
        cursor.execute(f"PRAGMA table_info({table[0]});")
        tables[table[0]] = cursor.fetchall()
    return tables

def migrate_database():
    """Migra o banco de dados para o novo esquema"""
    try:
        # Cria backup
        backup_database()
        
        # Conecta ao banco
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Salva dados atuais
        cursor.execute("SELECT * FROM blocks")
        old_blocks = cursor.fetchall()
        
        cursor.execute("SELECT * FROM transactions")
        old_transactions = cursor.fetchall()
        
        # Dropa tabelas antigas
        cursor.execute("DROP TABLE IF EXISTS blocks")
        cursor.execute("DROP TABLE IF EXISTS transactions")
        
        # Carrega novo esquema
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql')) as f:
            cursor.executescript(f.read())
        
        # Cria bloco genesis correto
        genesis = GenesisBlock.get_genesis_block()
        cursor.execute("""
            INSERT INTO blocks (
                hash, index, timestamp, previous_hash, 
                difficulty, nonce, miner_address, mining_reward
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            genesis['hash'],
            genesis['index'],
            genesis['timestamp'],
            genesis['previous_hash'],
            genesis['difficulty'],
            genesis['nonce'],
            genesis['miner_address'],
            genesis['mining_reward']
        ))
        
        # Insere transação genesis
        cursor.execute("""
            INSERT INTO transactions (
                tx_hash, block_hash, tx_type, from_address,
                to_address, amount, timestamp, data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            genesis['transactions'][0]['tx_id'],
            genesis['hash'],
            genesis['transactions'][0]['tx_type'],
            genesis['transactions'][0]['from_address'],
            genesis['transactions'][0]['to_address'],
            genesis['transactions'][0]['amount'],
            genesis['transactions'][0]['timestamp'],
            json.dumps(genesis['transactions'][0]['data'])
        ))
        
        # Migra blocos antigos (exceto genesis)
        for block in old_blocks:
            if block[0] != genesis['hash']:  # Pula bloco genesis antigo
                cursor.execute("""
                    INSERT INTO blocks (
                        hash, index, timestamp, previous_hash,
                        difficulty, nonce, miner_address, mining_reward
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    block[0],  # hash
                    block[1],  # index
                    block[2],  # timestamp
                    block[3],  # previous_hash
                    4,         # difficulty (default)
                    block[4],  # nonce
                    block[5],  # miner_address
                    0.0       # mining_reward (default)
                ))
        
        # Migra transações antigas (exceto genesis)
        for tx in old_transactions:
            if tx[0] != genesis['transactions'][0]['tx_id']:  # Pula tx genesis antiga
                cursor.execute("""
                    INSERT INTO transactions (
                        tx_hash, block_hash, tx_type, from_address,
                        to_address, amount, timestamp, data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx[0],  # tx_hash
                    tx[1],  # block_hash
                    'transfer',  # tx_type default
                    tx[2],  # from_address
                    tx[3],  # to_address
                    tx[4],  # amount
                    tx[5],  # timestamp
                    None    # data
                ))
        
        # Verifica consistência
        cursor.execute("SELECT COUNT(*) FROM blocks")
        block_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        tx_count = cursor.fetchone()[0]
        
        print(f"\nMigração concluída:")
        print(f"- Total de blocos: {block_count}")
        print(f"- Total de transações: {tx_count}")
        
        conn.commit()
        conn.close()
        print("\nBanco de dados atualizado com sucesso!")
        
    except Exception as e:
        print(f"\nErro durante migração: {e}")
        if os.path.exists(BACKUP_PATH):
            print("\nRestaurando backup...")
            import shutil
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print("Backup restaurado!")
        raise

if __name__ == '__main__':
    migrate_database() 