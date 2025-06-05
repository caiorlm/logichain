from __future__ import annotations
import os
import json
import sqlite3
import threading
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import shutil
import gzip
import base64

from .block import Block
from .transaction import Transaction

class BlockchainStorage:
    """
    Gerencia o armazenamento persistente da blockchain usando SQLite.
    Implementa backup automático e compactação de dados.
    """
    
    def __init__(self, db_path: str):
        """
        Inicializa o armazenamento.
        
        Args:
            db_path: Caminho para o diretório de dados
        """
        self.db_path = os.path.expanduser(db_path)
        self.db_file = os.path.join(self.db_path, 'blockchain.db')
        self.backup_dir = os.path.join(self.db_path, 'backups')
        
        # Criar diretórios necessários
        os.makedirs(self.db_path, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Inicializar banco de dados
        self._init_database()
        
        # Iniciar tarefas em background
        self._start_background_tasks()
        
        logging.info("Blockchain storage initialized")

    def _init_database(self):
        """Inicializa o esquema do banco de dados."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Tabela de blocos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    previous_hash TEXT NOT NULL,
                    merkle_root TEXT NOT NULL,
                    nonce INTEGER NOT NULL,
                    difficulty INTEGER NOT NULL,
                    transactions TEXT NOT NULL,
                    height INTEGER NOT NULL,
                    compressed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Tabela de transações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    hash TEXT PRIMARY KEY,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    nonce INTEGER NOT NULL,
                    gas_price INTEGER NOT NULL,
                    gas_limit INTEGER NOT NULL,
                    data TEXT,
                    timestamp INTEGER NOT NULL,
                    signature TEXT,
                    block_hash TEXT,
                    FOREIGN KEY (block_hash) REFERENCES blocks(hash)
                )
            ''')
            
            # Índices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_block ON transactions(block_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_address)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_address)')
            
            conn.commit()

    def _start_background_tasks(self):
        """Inicia tarefas em background para manutenção."""
        def backup_task():
            while True:
                try:
                    self._create_backup()
                    self._compress_old_data()
                except Exception as e:
                    logging.error(f"Error in backup task: {e}")
                finally:
                    # Executar backup a cada 6 horas
                    threading.Event().wait(21600)
        
        threading.Thread(target=backup_task, daemon=True).start()

    def save_block(self, block: Block, height: int) -> bool:
        """
        Salva um bloco no banco de dados.
        
        Args:
            block: O bloco a ser salvo
            height: Altura do bloco na chain
            
        Returns:
            bool: True se salvo com sucesso
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Salvar bloco
                cursor.execute('''
                    INSERT INTO blocks (
                        hash, version, timestamp, previous_hash,
                        merkle_root, nonce, difficulty, transactions,
                        height, compressed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    block.hash,
                    block.version,
                    block.timestamp,
                    block.previous_hash,
                    block.merkle_root,
                    block.nonce,
                    block.difficulty,
                    json.dumps(block.transactions),
                    height,
                    False
                ))
                
                # Salvar transações
                for tx in block.transactions:
                    tx_obj = Transaction.from_dict(tx)
                    cursor.execute('''
                        INSERT INTO transactions (
                            hash, from_address, to_address, amount,
                            nonce, gas_price, gas_limit, data,
                            timestamp, signature, block_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        tx_obj.hash,
                        tx_obj.from_address,
                        tx_obj.to_address,
                        tx_obj.amount,
                        tx_obj.nonce,
                        tx_obj.gas_price,
                        tx_obj.gas_limit,
                        tx_obj.data,
                        tx_obj.timestamp,
                        tx_obj.signature,
                        block.hash
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error saving block: {e}")
            return False

    def load_block(self, block_hash: str) -> Optional[Block]:
        """
        Carrega um bloco do banco de dados.
        
        Args:
            block_hash: Hash do bloco
            
        Returns:
            Block ou None se não encontrado
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT version, timestamp, previous_hash,
                           merkle_root, nonce, difficulty,
                           transactions, compressed
                    FROM blocks WHERE hash = ?
                ''', (block_hash,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                    
                version, timestamp, previous_hash, merkle_root, nonce, difficulty, transactions_json, compressed = row
                
                # Descomprimir dados se necessário
                if compressed:
                    transactions_json = gzip.decompress(base64.b64decode(transactions_json)).decode()
                
                transactions = json.loads(transactions_json)
                
                block = Block(
                    timestamp=timestamp,
                    previous_hash=previous_hash,
                    transactions=transactions,
                    nonce=nonce,
                    difficulty=difficulty,
                    version=version
                )
                block.merkle_root = merkle_root
                block.hash = block_hash
                
                return block
                
        except Exception as e:
            logging.error(f"Error loading block: {e}")
            return None

    def load_chain(self, start_height: int = 0, limit: int = 1000) -> List[Block]:
        """
        Carrega uma parte da blockchain.
        
        Args:
            start_height: Altura inicial
            limit: Número máximo de blocos
            
        Returns:
            Lista de blocos
        """
        blocks = []
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT hash FROM blocks
                    WHERE height >= ?
                    ORDER BY height ASC
                    LIMIT ?
                ''', (start_height, limit))
                
                for (block_hash,) in cursor.fetchall():
                    block = self.load_block(block_hash)
                    if block:
                        blocks.append(block)
                        
            return blocks
            
        except Exception as e:
            logging.error(f"Error loading chain: {e}")
            return blocks

    def _create_backup(self):
        """Cria um backup do banco de dados."""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(self.backup_dir, f'blockchain_{timestamp}.db')
            
            # Criar backup
            shutil.copy2(self.db_file, backup_file)
            
            # Comprimir backup
            with open(backup_file, 'rb') as f_in:
                with gzip.open(f'{backup_file}.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    
            # Remover arquivo não comprimido
            os.remove(backup_file)
            
            # Manter apenas os últimos 5 backups
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.endswith('.gz')],
                reverse=True
            )
            
            for old_backup in backups[5:]:
                os.remove(os.path.join(self.backup_dir, old_backup))
                
            logging.info(f"Backup created: blockchain_{timestamp}.db.gz")
            
        except Exception as e:
            logging.error(f"Error creating backup: {e}")

    def _compress_old_data(self):
        """Comprime dados antigos para economizar espaço."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Pegar altura atual
                cursor.execute('SELECT MAX(height) FROM blocks')
                max_height = cursor.fetchone()[0] or 0
                
                # Comprimir blocos mais antigos que 10000 blocos
                if max_height > 10000:
                    compress_height = max_height - 10000
                    
                    cursor.execute('''
                        SELECT hash, transactions FROM blocks
                        WHERE height < ? AND NOT compressed
                    ''', (compress_height,))
                    
                    for block_hash, transactions_json in cursor.fetchall():
                        # Comprimir dados
                        compressed = base64.b64encode(
                            gzip.compress(transactions_json.encode())
                        ).decode()
                        
                        # Atualizar registro
                        cursor.execute('''
                            UPDATE blocks
                            SET transactions = ?, compressed = TRUE
                            WHERE hash = ?
                        ''', (compressed, block_hash))
                    
                    conn.commit()
                    logging.info(f"Compressed blocks up to height {compress_height}")
                    
        except Exception as e:
            logging.error(f"Error compressing data: {e}")

    def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Busca uma transação pelo hash.
        
        Args:
            tx_hash: Hash da transação
            
        Returns:
            Dados da transação ou None se não encontrada
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT from_address, to_address, amount,
                           nonce, gas_price, gas_limit, data,
                           timestamp, signature, block_hash
                    FROM transactions WHERE hash = ?
                ''', (tx_hash,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                    
                return {
                    'hash': tx_hash,
                    'from': row[0],
                    'to': row[1],
                    'amount': row[2],
                    'nonce': row[3],
                    'gas_price': row[4],
                    'gas_limit': row[5],
                    'data': row[6],
                    'timestamp': row[7],
                    'signature': row[8],
                    'block_hash': row[9]
                }
                
        except Exception as e:
            logging.error(f"Error getting transaction: {e}")
            return None

    def get_address_transactions(
        self,
        address: str,
        start_block: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Busca transações de um endereço.
        
        Args:
            address: Endereço para buscar
            start_block: Altura inicial do bloco
            limit: Número máximo de transações
            
        Returns:
            Lista de transações
        """
        transactions = []
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT t.hash, t.from_address, t.to_address,
                           t.amount, t.nonce, t.gas_price,
                           t.gas_limit, t.data, t.timestamp,
                           t.signature, t.block_hash
                    FROM transactions t
                    JOIN blocks b ON t.block_hash = b.hash
                    WHERE (t.from_address = ? OR t.to_address = ?)
                    AND b.height >= ?
                    ORDER BY b.height DESC, t.timestamp DESC
                    LIMIT ?
                ''', (address, address, start_block, limit))
                
                for row in cursor.fetchall():
                    transactions.append({
                        'hash': row[0],
                        'from': row[1],
                        'to': row[2],
                        'amount': row[3],
                        'nonce': row[4],
                        'gas_price': row[5],
                        'gas_limit': row[6],
                        'data': row[7],
                        'timestamp': row[8],
                        'signature': row[9],
                        'block_hash': row[10]
                    })
                    
            return transactions
            
        except Exception as e:
            logging.error(f"Error getting address transactions: {e}")
            return transactions 