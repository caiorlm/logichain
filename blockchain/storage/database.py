"""
Gerenciamento do banco de dados da blockchain.
"""

import sqlite3
import json
import logging
from typing import Any, List, Dict, Optional
from pathlib import Path

logger = logging.getLogger('blockchain.db')

class BlockchainDB:
    """Gerencia conexões e operações no banco de dados SQLite."""
    
    def __init__(self, db_path: str):
        """
        Inicializa conexão com o banco.
        
        Args:
            db_path: Caminho para o arquivo do banco
        """
        self.db_path = db_path
        
        # Criar diretório se não existir
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Inicializar conexão
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        logger.info(f"Banco de dados inicializado: {db_path}")
        
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Executa uma query SQL.
        
        Args:
            query: Query SQL
            params: Parâmetros da query
            
        Returns:
            Cursor com resultado
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"Erro ao executar query: {e}")
            self.conn.rollback()
            raise
            
    def executemany(self, query: str, params: List[tuple]) -> sqlite3.Cursor:
        """
        Executa uma query SQL múltiplas vezes.
        
        Args:
            query: Query SQL
            params: Lista de parâmetros
            
        Returns:
            Cursor com resultado
        """
        try:
            cursor = self.conn.cursor()
            cursor.executemany(query, params)
            self.conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"Erro ao executar query múltipla: {e}")
            self.conn.rollback()
            raise
            
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Busca uma única linha do banco.
        
        Args:
            query: Query SQL
            params: Parâmetros da query
            
        Returns:
            Dicionário com resultado ou None
        """
        try:
            cursor = self.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao buscar linha: {e}")
            return None
            
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Busca múltiplas linhas do banco.
        
        Args:
            query: Query SQL
            params: Parâmetros da query
            
        Returns:
            Lista de dicionários com resultados
        """
        try:
            cursor = self.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar linhas: {e}")
            return []
            
    def create_tables(self, tables: Dict[str, str]):
        """
        Cria tabelas no banco.
        
        Args:
            tables: Dicionário com nome e schema das tabelas
        """
        try:
            for name, schema in tables.items():
                self.execute(f"CREATE TABLE IF NOT EXISTS {name} ({schema})")
            logger.info("Tabelas criadas com sucesso")
        except Exception as e:
            logger.error(f"Erro ao criar tabelas: {e}")
            raise
            
    def backup(self, backup_path: str):
        """
        Faz backup do banco.
        
        Args:
            backup_path: Caminho para salvar backup
        """
        try:
            backup_conn = sqlite3.connect(backup_path)
            self.conn.backup(backup_conn)
            backup_conn.close()
            logger.info(f"Backup criado: {backup_path}")
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
            raise
            
    def vacuum(self):
        """Otimiza o banco removendo espaço não utilizado."""
        try:
            self.execute("VACUUM")
            logger.info("Banco otimizado")
        except Exception as e:
            logger.error(f"Erro ao otimizar banco: {e}")
            raise
            
    def close(self):
        """Fecha conexão com o banco."""
        try:
            self.conn.close()
            logger.info("Conexão fechada")
        except Exception as e:
            logger.error(f"Erro ao fechar conexão: {e}")
            raise
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 