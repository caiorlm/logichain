"""
Script para corrigir problemas no banco de dados da blockchain
"""

import os
import sqlite3
import json
import shutil
from datetime import datetime
from pathlib import Path

# Configura caminhos
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / 'data' / 'blockchain'
DB_PATH = DATA_DIR / 'chain.db'
BACKUP_DIR = DATA_DIR / 'backups'
SCHEMA_PATH = ROOT_DIR / 'blockchain' / 'database' / 'schema.sql'

def create_backup():
    """Cria backup do banco de dados"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f'chain_{timestamp}.db'
    
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backup criado em: {backup_path}")
    return backup_path

def init_database():
    """Inicializa o banco de dados com o schema correto"""
    # Garante que o arquivo não existe
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Carrega e executa schema
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())
    
    conn.commit()
    conn.close()
    print("Schema inicializado com sucesso")

def migrate_data(backup_path):
    """Migra dados do backup para o novo schema"""
    # Conecta aos bancos
    old_conn = sqlite3.connect(backup_path)
    new_conn = sqlite3.connect(DB_PATH)
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    try:
        # Migra blocos
        old_cursor.execute("SELECT * FROM blocks")
        blocks = old_cursor.fetchall()
        
        for block in blocks:
            new_cursor.execute("""
                INSERT INTO blocks (
                    hash, block_index, timestamp, previous_hash,
                    difficulty, nonce, miner_address, mining_reward
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block[0],  # hash
                block[1],  # block_index (antigo index)
                block[2],  # timestamp
                block[3],  # previous_hash
                block[4] if len(block) > 4 else 4,  # difficulty
                block[5] if len(block) > 5 else 0,  # nonce
                block[6] if len(block) > 6 else None,  # miner_address
                block[7] if len(block) > 7 else 0.0  # mining_reward
            ))
        
        # Migra transações
        old_cursor.execute("SELECT * FROM transactions")
        transactions = old_cursor.fetchall()
        
        for tx in transactions:
            new_cursor.execute("""
                INSERT INTO transactions (
                    tx_hash, block_hash, tx_type, from_address,
                    to_address, amount, timestamp, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx[0],  # tx_hash
                tx[1],  # block_hash
                tx[2] if len(tx) > 2 else 'transfer',  # tx_type
                tx[3],  # from_address
                tx[4],  # to_address
                tx[5],  # amount
                tx[6],  # timestamp
                tx[7] if len(tx) > 7 else None  # data
            ))
        
        new_conn.commit()
        print("Dados migrados com sucesso")
        
    except Exception as e:
        print(f"Erro na migração: {e}")
        new_conn.rollback()
        raise
    finally:
        old_conn.close()
        new_conn.close()

def verify_integrity():
    """Verifica integridade do banco de dados"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verifica contagem
        cursor.execute("SELECT COUNT(*) FROM blocks")
        block_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        tx_count = cursor.fetchone()[0]
        
        print(f"\nEstatísticas:")
        print(f"- Total de blocos: {block_count}")
        print(f"- Total de transações: {tx_count}")
        
        # Verifica sequência de blocos
        cursor.execute("""
            SELECT b1.block_index, b1.hash, b1.previous_hash, b2.hash
            FROM blocks b1
            LEFT JOIN blocks b2 ON b1.previous_hash = b2.hash
            WHERE b1.block_index > 0
            AND b2.hash IS NULL
        """)
        orphans = cursor.fetchall()
        
        if orphans:
            print("\nBlocos órfãos encontrados:")
            for orphan in orphans:
                print(f"- Bloco #{orphan[0]} ({orphan[1]}) aponta para bloco inexistente ({orphan[2]})")
        
        # Verifica transações
        cursor.execute("""
            SELECT tx_hash, block_hash 
            FROM transactions t
            LEFT JOIN blocks b ON t.block_hash = b.hash
            WHERE b.hash IS NULL
        """)
        invalid_txs = cursor.fetchall()
        
        if invalid_txs:
            print("\nTransações inválidas encontradas:")
            for tx in invalid_txs:
                print(f"- Transação {tx[0]} referencia bloco inexistente ({tx[1]})")
        
        # Verifica saldos
        cursor.execute("SELECT DISTINCT miner_address FROM blocks WHERE miner_address IS NOT NULL")
        addresses = cursor.fetchall()
        
        print("\nSaldos por endereço:")
        for address in addresses:
            addr = address[0]
            
            # Recompensas de mineração
            cursor.execute("SELECT SUM(mining_reward) FROM blocks WHERE miner_address = ?", (addr,))
            rewards = cursor.fetchone()[0] or 0
            
            # Transações recebidas
            cursor.execute("""
                SELECT SUM(amount) 
                FROM transactions 
                WHERE to_address = ? AND tx_type != 'mining_reward'
            """, (addr,))
            received = cursor.fetchone()[0] or 0
            
            # Transações enviadas
            cursor.execute("SELECT SUM(amount) FROM transactions WHERE from_address = ?", (addr,))
            sent = cursor.fetchone()[0] or 0
            
            balance = rewards + received - sent
            print(f"- {addr}: {balance:.2f} LOGI")
        
    finally:
        conn.close()

def main():
    """Função principal de correção"""
    print("Iniciando correção do banco de dados...")
    
    # Cria diretórios se necessário
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Backup
    backup_path = create_backup()
    
    try:
        # Inicializa novo banco
        init_database()
        
        # Migra dados
        migrate_data(backup_path)
        
        # Verifica integridade
        verify_integrity()
        
        print("\nCorreção concluída com sucesso!")
        
    except Exception as e:
        print(f"\nErro durante correção: {e}")
        print("Restaurando backup...")
        if DB_PATH.exists():
            try:
                DB_PATH.unlink()
            except PermissionError:
                print("Não foi possível excluir o arquivo do banco de dados. Feche todas as conexões e tente novamente.")
        shutil.copy2(backup_path, DB_PATH)
        print("Backup restaurado!")
        raise

if __name__ == '__main__':
    main() 