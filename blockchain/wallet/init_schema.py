"""
Script para inicializar o schema das carteiras
"""

import sqlite3
import logging
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuração de caminhos
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / 'data' / 'blockchain'
DB_PATH = DATA_DIR / 'chain.db'

def init_wallet_schema():
    """Inicializa o schema das carteiras"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript("""
                -- Tabela de carteiras
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    encrypted_private_key TEXT,
                    balance REAL NOT NULL DEFAULT 0.0,
                    nonce INTEGER NOT NULL DEFAULT 0,
                    last_updated REAL NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at REAL NOT NULL
                );

                -- Índices para melhor performance
                CREATE INDEX IF NOT EXISTS idx_wallets_balance ON wallets(balance);
                CREATE INDEX IF NOT EXISTS idx_wallets_status ON wallets(status);
                CREATE INDEX IF NOT EXISTS idx_wallets_created ON wallets(created_at);
            """)
            
            logging.info("Schema das carteiras inicializado com sucesso")
            
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar schema: {e}")
        raise

if __name__ == "__main__":
    init_wallet_schema() 