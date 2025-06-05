"""
Script de verificação do banco de dados
Verifica a consistência dos dados e estrutura
"""

import sqlite3
import os
import json
from typing import List, Dict, Tuple
from datetime import datetime

# Caminho do banco de dados
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'blockchain', 'chain.db')

def verify_database():
    """Verifica a consistência do banco de dados"""
    try:
        if not os.path.exists(DB_PATH):
            print(f"\nERRO: Banco de dados não encontrado em {DB_PATH}")
            return
            
        # Conecta ao banco
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("\n=== Verificação do Banco de Dados ===")
        print(f"Caminho: {DB_PATH}")
        
        # Verifica estrutura das tabelas
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table'
        """)
        tables = cursor.fetchall()
        print("\nTabelas encontradas:")
        for table in tables:
            print(f"- {table[0]}")
            
            # Mostra estrutura da tabela
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            print("  Colunas:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
        
        # Verifica bloco genesis
        cursor.execute("""
            SELECT * FROM blocks 
            WHERE block_index = 0
        """)
        genesis = cursor.fetchone()
        
        if genesis:
            print("\nBloco Genesis:")
            print(f"- Hash: {genesis[0]}")
            print(f"- Índice: {genesis[1]}")
            print(f"- Timestamp: {genesis[2]}")
            print(f"- Previous Hash: {genesis[3]}")
            print(f"- Difficulty: {genesis[4]}")
        else:
            print("\nERRO: Bloco genesis não encontrado!")
        
        # Verifica sequência de blocos
        cursor.execute("""
            SELECT b1.hash, b1.block_index, b1.previous_hash, b2.hash
            FROM blocks b1
            LEFT JOIN blocks b2 ON b1.previous_hash = b2.hash
            WHERE b1.block_index > 0
            ORDER BY b1.block_index
        """)
        chain = cursor.fetchall()
        
        print("\nVerificação da cadeia:")
        broken_links = []
        for block in chain:
            if not block[3]:  # previous block not found
                broken_links.append(block[0])
                print(f"ERRO: Bloco {block[0]} (índice {block[1]}) referencia hash anterior inexistente: {block[2]}")
        
        if not broken_links:
            print("- Sequência de blocos OK")
        
        # Verifica transações
        cursor.execute("""
            SELECT t.tx_hash, t.block_hash, b.hash
            FROM transactions t
            LEFT JOIN blocks b ON t.block_hash = b.hash
        """)
        transactions = cursor.fetchall()
        
        print("\nVerificação de transações:")
        orphan_txs = []
        for tx in transactions:
            if not tx[2]:  # block not found
                orphan_txs.append(tx[0])
                print(f"ERRO: Transação {tx[0]} referencia bloco inexistente: {tx[1]}")
        
        if not orphan_txs:
            print("- Todas as transações têm blocos válidos")
        
        # Estatísticas
        cursor.execute("SELECT COUNT(*) FROM blocks")
        total_blocks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        
        print("\nEstatísticas:")
        print(f"- Total de blocos: {total_blocks}")
        print(f"- Total de transações: {total_transactions}")
        if total_blocks > 0:
            print(f"- Média de transações por bloco: {total_transactions/total_blocks:.2f}")
        
        # Verifica índices únicos
        cursor.execute("""
            SELECT block_index, COUNT(*) 
            FROM blocks 
            GROUP BY block_index 
            HAVING COUNT(*) > 1
        """)
        duplicate_indices = cursor.fetchall()
        
        if duplicate_indices:
            print("\nERRO: Índices duplicados encontrados:")
            for idx in duplicate_indices:
                print(f"- Índice {idx[0]} aparece {idx[1]} vezes")
        
        conn.close()
        print("\nVerificação concluída!")
        
    except Exception as e:
        print(f"\nErro durante verificação: {e}")
        raise

if __name__ == '__main__':
    verify_database() 