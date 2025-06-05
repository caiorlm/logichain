"""
Script de migração para adicionar colunas faltantes
"""

import os
import sys
from pathlib import Path
import logging
import sqlite3
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

def backup_database():
    """Cria backup do banco antes da migração"""
    try:
        # Paths
        data_dir = ROOT_DIR / 'data' / 'blockchain'
        db_path = data_dir / 'chain.db'
        backup_path = data_dir / f'chain_backup_{int(time.time())}.db'
        
        # Cria backup
        if db_path.exists():
            import shutil
            shutil.copy2(db_path, backup_path)
            logging.info(f"Backup criado em: {backup_path}")
            
        return True
        
    except Exception as e:
        logging.error(f"Erro ao criar backup: {str(e)}")
        return False

def add_missing_columns():
    """Adiciona colunas faltantes à tabela blocks"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Lista de colunas a serem adicionadas com seus valores padrão
        columns = {
            'version': 'INTEGER DEFAULT 1',
            'state': "TEXT DEFAULT 'confirmed'",
            'total_transactions': 'INTEGER DEFAULT 0',
            'size_bytes': 'INTEGER DEFAULT 0'
        }
        
        # Verifica colunas existentes
        cursor.execute("PRAGMA table_info(blocks)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        # Adiciona colunas faltantes
        for column, type_def in columns.items():
            if column not in existing_columns:
                sql = f"ALTER TABLE blocks ADD COLUMN {column} {type_def}"
                cursor.execute(sql)
                logging.info(f"✅ Coluna {column} adicionada")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Erro ao adicionar colunas: {str(e)}")
        return False

def verify_migration():
    """Verifica se a migração foi bem sucedida"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica estrutura
        cursor.execute("PRAGMA table_info(blocks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Lista de colunas esperadas
        expected_columns = [
            'version', 'state', 'total_transactions', 'size_bytes'
        ]
        
        # Verifica se todas as colunas existem
        for column in expected_columns:
            assert column in columns, f"Coluna {column} não encontrada"
        
        # Verifica alguns blocos
        cursor.execute("""
            SELECT block_index, version, state, total_transactions, size_bytes
            FROM blocks 
            LIMIT 5
        """)
        blocks = cursor.fetchall()
        
        for block in blocks:
            logging.info(f"""
Bloco {block[0]}:
  - version: {block[1]}
  - state: {block[2]}
  - transactions: {block[3]}
  - size: {block[4]} bytes
""")
        
        conn.close()
        logging.info("✅ Migração verificada com sucesso")
        return True
        
    except Exception as e:
        logging.error(f"Erro na verificação: {str(e)}")
        return False

def main():
    """Executa migração"""
    try:
        logging.info("🔄 Iniciando migração do banco...")
        
        # Cria backup
        if not backup_database():
            logging.error("❌ Falha ao criar backup, abortando migração")
            return
        
        # Adiciona colunas
        if not add_missing_columns():
            logging.error("❌ Falha ao adicionar colunas")
            return
        
        # Verifica migração
        if not verify_migration():
            logging.error("❌ Falha na verificação da migração")
            return
        
        logging.info("✅ Migração concluída com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro durante migração: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 