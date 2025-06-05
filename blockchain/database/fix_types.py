"""
Script para corrigir tipos de dados na tabela blocks
"""

import os
import sys
from pathlib import Path
import logging
import sqlite3
import time
import json

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
    """Cria backup do banco antes da correção"""
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

def fix_data_types():
    """Corrige tipos de dados na tabela blocks"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Remove tabela temporária se existir
        cursor.execute("DROP TABLE IF EXISTS blocks_new")
        
        # Verifica duplicatas
        cursor.execute("""
            SELECT block_index, COUNT(*) as count
            FROM blocks
            GROUP BY block_index
            HAVING count > 1
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            logging.warning("⚠️ Encontradas duplicatas de block_index:")
            for block_index, count in duplicates:
                logging.warning(f"  - Índice {block_index}: {count} blocos")
                
                # Mantém apenas o bloco mais recente
                cursor.execute("""
                    DELETE FROM blocks 
                    WHERE block_index = ? 
                    AND timestamp < (
                        SELECT MAX(timestamp) 
                        FROM blocks 
                        WHERE block_index = ?
                    )
                """, (block_index, block_index))
            
            conn.commit()
            logging.info("✅ Duplicatas removidas")
        
        # Cria tabela temporária com estrutura correta
        cursor.execute("""
            CREATE TABLE blocks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                block_index INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                previous_hash TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 4,
                nonce INTEGER NOT NULL DEFAULT 0,
                miner_address TEXT,
                mining_reward REAL DEFAULT 50.0,
                merkle_root TEXT,
                version INTEGER DEFAULT 1,
                state TEXT DEFAULT 'confirmed',
                total_transactions INTEGER DEFAULT 0,
                size_bytes INTEGER DEFAULT 0,
                UNIQUE(block_index)
            )
        """)
        
        # Copia dados convertendo tipos
        cursor.execute("""
            INSERT INTO blocks_new (
                hash, block_index, timestamp, previous_hash,
                difficulty, nonce, miner_address, mining_reward,
                merkle_root, version, state, total_transactions,
                size_bytes
            )
            SELECT 
                hash,
                CAST(CASE 
                    WHEN block_index = '' THEN '0'
                    WHEN block_index IS NULL THEN '0'
                    ELSE block_index
                END AS INTEGER) as block_index,
                CAST(CASE 
                    WHEN timestamp = '' THEN '0'
                    WHEN timestamp IS NULL THEN '0'
                    ELSE timestamp
                END AS REAL) as timestamp,
                previous_hash,
                CAST(CASE 
                    WHEN difficulty = '' THEN '4'
                    WHEN difficulty IS NULL THEN '4'
                    ELSE difficulty
                END AS INTEGER) as difficulty,
                CAST(CASE 
                    WHEN nonce = '' THEN '0'
                    WHEN nonce IS NULL THEN '0'
                    ELSE nonce
                END AS INTEGER) as nonce,
                miner_address,
                CAST(CASE 
                    WHEN mining_reward = '' THEN '50.0'
                    WHEN mining_reward IS NULL THEN '50.0'
                    ELSE mining_reward
                END AS REAL) as mining_reward,
                merkle_root,
                CAST(COALESCE(version, 1) AS INTEGER) as version,
                COALESCE(state, 'confirmed') as state,
                CAST(COALESCE(total_transactions, 0) AS INTEGER) as total_transactions,
                CAST(COALESCE(size_bytes, 0) AS INTEGER) as size_bytes
            FROM blocks
            ORDER BY block_index ASC
        """)
        
        # Remove tabela antiga
        cursor.execute("DROP TABLE blocks")
        
        # Renomeia nova tabela
        cursor.execute("ALTER TABLE blocks_new RENAME TO blocks")
        
        # Recria índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_index ON blocks(block_index)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_miner ON blocks(miner_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_time ON blocks(timestamp)")
        
        conn.commit()
        conn.close()
        
        logging.info("✅ Tipos de dados corrigidos com sucesso")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao corrigir tipos: {str(e)}")
        return False

def verify_types():
    """Verifica se os tipos de dados estão corretos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtém informações das colunas
        cursor.execute("PRAGMA table_info(blocks)")
        columns = cursor.fetchall()
        
        logging.info("\nEstrutura da tabela blocks:")
        for col in columns:
            logging.info(f"  {col[1]}: {col[2]}")
        
        # Verifica alguns registros
        cursor.execute("""
            SELECT block_index, timestamp, difficulty, nonce, 
                   mining_reward, version, total_transactions
            FROM blocks 
            LIMIT 5
        """)
        blocks = cursor.fetchall()
        
        logging.info("\nAmostra de registros:")
        for block in blocks:
            logging.info(f"""
Bloco {block[0]}:
  - timestamp: {block[1]} ({type(block[1]).__name__})
  - difficulty: {block[2]} ({type(block[2]).__name__})
  - nonce: {block[3]} ({type(block[3]).__name__})
  - mining_reward: {block[4]} ({type(block[4]).__name__})
  - version: {block[5]} ({type(block[5]).__name__})
  - total_transactions: {block[6]} ({type(block[6]).__name__})
""")
        
        conn.close()
        logging.info("✅ Verificação de tipos concluída")
        return True
        
    except Exception as e:
        logging.error(f"Erro na verificação: {str(e)}")
        return False

def main():
    """Executa correção de tipos"""
    try:
        logging.info("🔄 Iniciando correção de tipos...")
        
        # Cria backup
        if not backup_database():
            logging.error("❌ Falha ao criar backup, abortando correção")
            return
        
        # Corrige tipos
        if not fix_data_types():
            logging.error("❌ Falha ao corrigir tipos")
            return
        
        # Verifica correção
        if not verify_types():
            logging.error("❌ Falha na verificação")
            return
        
        logging.info("✅ Correção de tipos concluída com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro durante correção: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 