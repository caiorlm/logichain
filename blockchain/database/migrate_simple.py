"""
Script de migração simplificado
Foca apenas nas tabelas essenciais (blocks e transactions)
"""

import sqlite3
import os
import json
from datetime import datetime

# Caminho do banco de dados
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'blockchain', 'chain.db')
BACKUP_PATH = DB_PATH + '.bak'

def backup_database():
    """Cria backup do banco de dados atual"""
    if os.path.exists(DB_PATH):
        import shutil
        os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"Backup criado em {BACKUP_PATH}")

def table_exists(cursor, table_name):
    """Verifica se uma tabela existe"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def migrate_database():
    """Migra o banco de dados para o novo esquema"""
    try:
        # Cria diretório se não existir
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Cria backup se o banco existir
        if os.path.exists(DB_PATH):
            backup_database()
        
        # Conecta ao banco
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Salva dados atuais se as tabelas existirem
        old_blocks = []
        old_transactions = []
        
        if table_exists(cursor, 'blocks'):
            cursor.execute("SELECT * FROM blocks")
            old_blocks = cursor.fetchall()
            
        if table_exists(cursor, 'transactions'):
            cursor.execute("SELECT * FROM transactions")
            old_transactions = cursor.fetchall()
        
        # Dropa tabelas se existirem
        cursor.execute("DROP TABLE IF EXISTS transactions")  # Drop transactions first due to foreign key
        cursor.execute("DROP TABLE IF EXISTS blocks")
        
        # Cria novas tabelas
        cursor.execute("""
            CREATE TABLE blocks (
                hash TEXT PRIMARY KEY,
                block_index INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                previous_hash TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 4,
                nonce INTEGER NOT NULL DEFAULT 0,
                miner_address TEXT,
                mining_reward REAL DEFAULT 0.0,
                UNIQUE(block_index)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE transactions (
                tx_hash TEXT PRIMARY KEY,
                block_hash TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                from_address TEXT NOT NULL,
                to_address TEXT,
                amount REAL NOT NULL DEFAULT 0.0,
                timestamp REAL NOT NULL,
                data TEXT,
                FOREIGN KEY (block_hash) REFERENCES blocks(hash)
            )
        """)
        
        # Cria bloco genesis
        genesis_block = {
            'hash': '0000000000000000000000000000000000000000000000000000000000000000',
            'index': 0,
            'timestamp': 0,
            'previous_hash': '0' * 64,
            'difficulty': 4,
            'nonce': 0,
            'miner_address': '0' * 40,
            'mining_reward': 0.0
        }
        
        cursor.execute("""
            INSERT INTO blocks (
                hash, block_index, timestamp, previous_hash,
                difficulty, nonce, miner_address, mining_reward
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            genesis_block['hash'],
            genesis_block['index'],
            genesis_block['timestamp'],
            genesis_block['previous_hash'],
            genesis_block['difficulty'],
            genesis_block['nonce'],
            genesis_block['miner_address'],
            genesis_block['mining_reward']
        ))
        
        # Insere transação genesis
        genesis_tx = {
            'tx_hash': '0' * 64,
            'block_hash': genesis_block['hash'],
            'tx_type': 'genesis',
            'from_address': '0' * 40,
            'to_address': '0' * 40,
            'amount': 0,
            'timestamp': 0,
            'data': json.dumps({'message': 'Bloco Genesis da LogiChain'})
        }
        
        cursor.execute("""
            INSERT INTO transactions (
                tx_hash, block_hash, tx_type, from_address,
                to_address, amount, timestamp, data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            genesis_tx['tx_hash'],
            genesis_tx['block_hash'],
            genesis_tx['tx_type'],
            genesis_tx['from_address'],
            genesis_tx['to_address'],
            genesis_tx['amount'],
            genesis_tx['timestamp'],
            genesis_tx['data']
        ))
        
        # Migra blocos antigos (exceto genesis)
        if old_blocks:
            for block in old_blocks:
                if block[0] != genesis_block['hash']:  # Pula bloco genesis antigo
                    try:
                        cursor.execute("""
                            INSERT INTO blocks (
                                hash, block_index, timestamp, previous_hash,
                                difficulty, nonce, miner_address, mining_reward
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            block[0],  # hash
                            block[1] if block[1] is not None else 0,  # index
                            block[2],  # timestamp
                            block[3],  # previous_hash
                            4,         # difficulty (default)
                            block[4] if block[4] is not None else 0,  # nonce
                            block[5] if block[5] is not None else '0' * 40,  # miner_address
                            0.0       # mining_reward (default)
                        ))
                    except sqlite3.IntegrityError:
                        print(f"Erro ao migrar bloco {block[0]}: possível duplicata")
                        continue
        
        # Migra transações antigas (exceto genesis)
        if old_transactions:
            for tx in old_transactions:
                if tx[0] != genesis_tx['tx_hash']:  # Pula tx genesis antiga
                    try:
                        cursor.execute("""
                            INSERT INTO transactions (
                                tx_hash, block_hash, tx_type, from_address,
                                to_address, amount, timestamp, data
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            tx[0],  # tx_hash
                            tx[1],  # block_hash
                            'transfer',  # tx_type default
                            tx[2] if tx[2] is not None else '0' * 40,  # from_address
                            tx[3] if tx[3] is not None else '0' * 40,  # to_address
                            tx[4] if tx[4] is not None else 0.0,  # amount
                            tx[5],  # timestamp
                            None    # data
                        ))
                    except sqlite3.IntegrityError:
                        print(f"Erro ao migrar transação {tx[0]}: possível duplicata")
                        continue
        
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