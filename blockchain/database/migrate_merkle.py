"""
Script de migração para adicionar coluna merkle_root
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

def add_merkle_root_column():
    """Adiciona coluna merkle_root à tabela blocks"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica se a coluna já existe
        cursor.execute("PRAGMA table_info(blocks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'merkle_root' not in columns:
            # Adiciona a coluna
            cursor.execute("""
                ALTER TABLE blocks
                ADD COLUMN merkle_root TEXT
            """)
            
            # Atualiza registros existentes
            cursor.execute("""
                UPDATE blocks
                SET merkle_root = NULL
                WHERE merkle_root IS NULL
            """)
            
            conn.commit()
            logging.info("✅ Coluna merkle_root adicionada com sucesso")
        else:
            logging.info("✅ Coluna merkle_root já existe")
        
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Erro ao adicionar coluna: {str(e)}")
        return False

def verify_migration():
    """Verifica se a migração foi bem sucedida"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica estrutura
        cursor.execute("PRAGMA table_info(blocks)")
        columns = [col[1] for col in cursor.fetchall()]
        assert 'merkle_root' in columns, "Coluna merkle_root não encontrada"
        
        # Verifica alguns blocos
        cursor.execute("""
            SELECT block_index, merkle_root 
            FROM blocks 
            LIMIT 5
        """)
        blocks = cursor.fetchall()
        
        for block in blocks:
            logging.info(f"Bloco {block[0]}: merkle_root = {block[1]}")
        
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
        
        # Adiciona coluna
        if not add_merkle_root_column():
            logging.error("❌ Falha ao adicionar coluna merkle_root")
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