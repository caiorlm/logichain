"""
Gerenciador de conexão com o banco de dados
"""

import os
import sqlite3
from pathlib import Path
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuração do banco de dados
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / 'data' / 'blockchain'
DB_PATH = DATA_DIR / 'chain.db'

def init_database():
    """Inicializa o banco de dados se necessário"""
    try:
        # Cria diretório de dados se não existir
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Verifica se precisa criar o banco
        if not DB_PATH.exists():
            # Carrega e executa schema
            schema_path = ROOT_DIR / 'blockchain' / 'database' / 'schema.sql'
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.executescript(schema_sql)
            
            logging.info(f"Banco de dados criado em {DB_PATH}")
        
        return True
        
    except Exception as e:
        logging.error(f"Erro ao inicializar banco: {str(e)}")
        return False

def get_db_connection():
    """Retorna uma conexão com o banco de dados"""
    try:
        # Garante que o banco existe
        init_database()
        
        # Estabelece conexão
        conn = sqlite3.connect(DB_PATH)
        
        # Configura para retornar rows como dicionários
        conn.row_factory = sqlite3.Row
        
        return conn
        
    except Exception as e:
        logging.error(f"Erro ao conectar ao banco: {str(e)}")
        raise

def execute_query(query, params=None):
    """Executa uma query no banco"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            return cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Erro ao executar query: {str(e)}")
        logging.error(f"Query: {query}")
        logging.error(f"Params: {params}")
        raise

def execute_script(script):
    """Executa um script SQL"""
    try:
        with get_db_connection() as conn:
            conn.executescript(script)
            
    except Exception as e:
        logging.error(f"Erro ao executar script: {str(e)}")
        logging.error(f"Script: {script}")
        raise

# Inicializa banco na importação do módulo
init_database() 