"""
Script para resetar toda a blockchain e reinicializar do zero
"""

import os
import sys
import shutil
from pathlib import Path
import logging
import time
import sqlite3

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from blockchain.database.db_manager import get_db_connection
from blockchain.wallet.key_manager import KeyManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def backup_existing():
    """Faz backup dos dados existentes"""
    try:
        # Paths
        data_dir = ROOT_DIR / 'data' / 'blockchain'
        backup_dir = data_dir / 'backups' / time.strftime('%Y%m%d_%H%M%S')
        
        if data_dir.exists():
            # Cria diretório de backup
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Move arquivos existentes para backup
            for file in data_dir.glob('*'):
                if file.is_file():
                    shutil.copy2(file, backup_dir / file.name)
            
            logging.info(f"✅ Backup criado em: {backup_dir}")
        
        return True
        
    except Exception as e:
        logging.error(f"Erro ao criar backup: {str(e)}")
        return False

def clean_data_dir():
    """Limpa diretório de dados"""
    try:
        data_dir = ROOT_DIR / 'data' / 'blockchain'
        
        # Remove arquivos do banco
        for file in data_dir.glob('chain*.db*'):
            file.unlink()
        
        # Remove arquivos de wallet
        for file in data_dir.glob('wallet*.dat'):
            file.unlink()
            
        logging.info("✅ Diretório de dados limpo")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao limpar diretório: {str(e)}")
        return False

def init_database():
    """Inicializa banco de dados do zero"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Carrega e executa schema
        schema_path = ROOT_DIR / 'blockchain' / 'database' / 'schema.sql'
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        cursor.executescript(schema_sql)
        conn.commit()
        
        # Verifica tabelas criadas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        logging.info("\nTabelas criadas:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            logging.info(f"  - {table[0]}: {count} registros")
        
        conn.close()
        logging.info("✅ Banco de dados inicializado")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao inicializar banco: {str(e)}")
        return False

def init_wallet():
    """Inicializa sistema de carteiras"""
    try:
        # Define paths
        data_dir = ROOT_DIR / 'data' / 'blockchain'
        db_path = data_dir / 'chain.db'
        wallet_dir = data_dir / 'wallets'
        
        # Cria diretório de carteiras
        wallet_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializa KeyManager
        key_manager = KeyManager(str(db_path), str(wallet_dir))
        
        # Inicializa criptografia
        key_manager.init_encryption("default_password")  # Senha padrão para testes
        
        # Gera nova carteira
        wallet = key_manager.create_wallet()
        
        logging.info("\nNova carteira criada:")
        logging.info(f"  Endereço: {wallet['address']}")
        logging.info(f"  Mnemonic: {wallet['mnemonic']}")
        
        # Verifica se foi salva
        loaded = key_manager.load_wallet(wallet['address'])
        assert loaded is not None, "Carteira não foi salva corretamente"
        
        logging.info("✅ Sistema de carteiras inicializado")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao inicializar carteiras: {str(e)}")
        return False

def verify_system():
    """Verifica se o sistema está pronto"""
    try:
        # Verifica banco
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica tabelas
        required_tables = ['blocks', 'transactions', 'wallets', 'mempool', 'peers']
        for table in required_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logging.info(f"Tabela {table}: {count} registros")
        
        # Verifica índices
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = cursor.fetchall()
        logging.info(f"\nÍndices criados: {len(indices)}")
        
        # Verifica carteira
        data_dir = ROOT_DIR / 'data' / 'blockchain'
        db_path = data_dir / 'chain.db'
        wallet_dir = data_dir / 'wallets'
        
        key_manager = KeyManager(str(db_path), str(wallet_dir))
        key_manager.load_encryption("default_password")
        
        # Tenta carregar primeira carteira
        cursor.execute("SELECT address FROM wallets LIMIT 1")
        address = cursor.fetchone()[0]
        
        wallet = key_manager.load_wallet(address)
        assert wallet is not None, "Não foi possível carregar carteira"
        
        logging.info("✅ Sistema verificado com sucesso")
        
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Erro na verificação: {str(e)}")
        return False

def main():
    """Executa reset completo"""
    try:
        logging.info("🔄 Iniciando reset completo do sistema...")
        
        # Backup
        if not backup_existing():
            logging.error("❌ Falha ao criar backup, abortando")
            return
        
        # Limpa dados
        if not clean_data_dir():
            logging.error("❌ Falha ao limpar diretório")
            return
        
        # Inicializa banco
        if not init_database():
            logging.error("❌ Falha ao inicializar banco")
            return
        
        # Inicializa carteiras
        if not init_wallet():
            logging.error("❌ Falha ao inicializar carteiras")
            return
        
        # Verifica sistema
        if not verify_system():
            logging.error("❌ Falha na verificação final")
            return
        
        logging.info("\n✅ Reset completo concluído com sucesso!")
        logging.info("Sistema pronto para mineração")
        
    except Exception as e:
        logging.error(f"❌ Erro durante reset: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 