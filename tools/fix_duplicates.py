"""
Script para corrigir duplicatas de block_index
"""

import os
import sys
from pathlib import Path
import logging
import time
import sqlite3
from datetime import datetime

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent
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
            logging.info(f"✅ Backup criado em: {backup_path}")
            
        return True
        
    except Exception as e:
        logging.error(f"Erro ao criar backup: {str(e)}")
        return False

def analyze_duplicates():
    """Analisa duplicatas na tabela blocks"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Encontra duplicatas
        cursor.execute("""
            SELECT block_index, COUNT(*) as count,
                   GROUP_CONCAT(hash) as hashes,
                   GROUP_CONCAT(timestamp) as timestamps
            FROM blocks
            GROUP BY block_index
            HAVING count > 1
            ORDER BY block_index ASC
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            logging.info("✅ Nenhuma duplicata encontrada")
            return True
            
        logging.warning(f"\n⚠️ Encontradas {len(duplicates)} duplicatas:")
        for dup in duplicates:
            block_index = dup[0]
            count = dup[1]
            hashes = dup[2].split(',')
            timestamps = [float(ts) for ts in dup[3].split(',')]
            
            logging.warning(f"""
Bloco {block_index}:
  Total: {count} duplicatas
  Hashes: {[h[:8] + '...' for h in hashes]}
  Timestamps: {[datetime.fromtimestamp(ts) for ts in timestamps]}
""")
        
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Erro ao analisar duplicatas: {str(e)}")
        return False

def fix_duplicates():
    """Corrige duplicatas mantendo apenas o bloco mais recente"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Remove tabela temporária se existir
        cursor.execute("DROP TABLE IF EXISTS blocks_new")
        
        # Cria nova tabela com estrutura correta
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
        
        # Insere blocos sem duplicatas
        cursor.execute("""
            INSERT INTO blocks_new (
                hash, block_index, timestamp, previous_hash,
                difficulty, nonce, miner_address, mining_reward,
                merkle_root, version, state, total_transactions,
                size_bytes
            )
            SELECT 
                hash, block_index, timestamp, previous_hash,
                difficulty, nonce, miner_address, mining_reward,
                merkle_root, version, state, total_transactions,
                size_bytes
            FROM blocks b1
            WHERE timestamp = (
                SELECT MAX(timestamp)
                FROM blocks b2
                WHERE b2.block_index = b1.block_index
            )
            ORDER BY block_index ASC
        """)
        
        # Verifica se inserção foi bem sucedida
        cursor.execute("SELECT COUNT(*) FROM blocks")
        old_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM blocks_new")
        new_count = cursor.fetchone()[0]
        
        logging.info(f"""
📊 Resultados:
  Blocos originais: {old_count}
  Blocos após correção: {new_count}
  Duplicatas removidas: {old_count - new_count}
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
        
        logging.info("✅ Duplicatas corrigidas com sucesso")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao corrigir duplicatas: {str(e)}")
        return False

def verify_fix():
    """Verifica se correção foi bem sucedida"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica se ainda há duplicatas
        cursor.execute("""
            SELECT block_index, COUNT(*) as count
            FROM blocks
            GROUP BY block_index
            HAVING count > 1
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            logging.error(f"❌ Ainda existem {len(duplicates)} duplicatas!")
            return False
            
        # Verifica sequência de blocos
        cursor.execute("""
            SELECT b1.block_index, b1.hash, b2.previous_hash
            FROM blocks b1
            JOIN blocks b2 ON b2.block_index = b1.block_index + 1
            WHERE b1.hash != b2.previous_hash
        """)
        
        broken_chain = cursor.fetchall()
        if broken_chain:
            logging.error(f"❌ Encontrados {len(broken_chain)} blocos com hash quebrado!")
            return False
            
        # Verifica transações
        cursor.execute("""
            SELECT COUNT(*) FROM transactions t
            LEFT JOIN blocks b ON b.hash = t.block_hash
            WHERE b.hash IS NULL
        """)
        
        orphan_txs = cursor.fetchone()[0]
        if orphan_txs > 0:
            logging.error(f"❌ Encontradas {orphan_txs} transações órfãs!")
            return False
        
        conn.close()
        logging.info("✅ Verificação concluída com sucesso")
        return True
        
    except Exception as e:
        logging.error(f"Erro na verificação: {str(e)}")
        return False

def main():
    """Executa correção de duplicatas"""
    try:
        logging.info("🔄 Iniciando correção de duplicatas...")
        
        # Cria backup
        if not backup_database():
            logging.error("❌ Falha ao criar backup, abortando")
            return
        
        # Analisa duplicatas
        if not analyze_duplicates():
            logging.error("❌ Falha ao analisar duplicatas")
            return
        
        # Corrige duplicatas
        if not fix_duplicates():
            logging.error("❌ Falha ao corrigir duplicatas")
            return
        
        # Verifica correção
        if not verify_fix():
            logging.error("❌ Falha na verificação")
            return
        
        logging.info("✅ Correção de duplicatas concluída com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro durante correção: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 