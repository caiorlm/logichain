"""
Implementação da blockchain
"""

import sqlite3
import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from .genesis import (
    GENESIS_HASH,
    GENESIS_INFO,
    GENESIS_TIMESTAMP,
    GENESIS_COORDS,
    GENESIS_CONTRACT_ID,
    GENESIS_PREVIOUS_HASH
)
from .coordinates import Coordinates

class BlockChain:
    """
    Implementação da blockchain com suporte a contratos
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.initialize_db()
        self._ensure_genesis_block()

    def initialize_db(self):
        """
        Inicializa banco de dados
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabela de blocos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    timestamp REAL,
                    start_lat REAL,
                    start_lon REAL,
                    end_lat REAL,
                    end_lon REAL,
                    delivery_hash TEXT,
                    previous_hash TEXT,
                    contract_id TEXT,
                    created_at REAL
                )
            ''')
            
            # Tabela de contratos pendentes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_contracts (
                    contract_id TEXT PRIMARY KEY,
                    start_lat REAL,
                    start_lon REAL,
                    end_lat REAL,
                    end_lon REAL,
                    timestamp REAL,
                    status TEXT,
                    metadata TEXT
                )
            ''')
            
            conn.commit()

    def _ensure_genesis_block(self):
        """
        Garante que o bloco genesis existe e está correto
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT hash FROM blocks WHERE contract_id = ?', 
                         (GENESIS_INFO['contract_id'],))
            existing = cursor.fetchone()

            if not existing:
                # Criar genesis
                self.create_genesis_block()
            elif existing[0] != GENESIS_HASH:
                raise ValueError(
                    f"Hash do Genesis inválido!\n"
                    f"Esperado: {GENESIS_HASH}\n"
                    f"Encontrado: {existing[0]}"
                )

    def create_genesis_block(self):
        """
        Cria o bloco genesis
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO blocks (
                    hash, timestamp, start_lat, start_lon,
                    end_lat, end_lon, delivery_hash,
                    previous_hash, contract_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                GENESIS_HASH,
                GENESIS_TIMESTAMP,
                GENESIS_COORDS[0],
                GENESIS_COORDS[1],
                GENESIS_COORDS[0],
                GENESIS_COORDS[1],
                self.calculate_genesis_delivery_hash(),
                GENESIS_PREVIOUS_HASH,
                GENESIS_CONTRACT_ID,
                time.time()
            ))
            conn.commit()

    def calculate_genesis_delivery_hash(self) -> str:
        """
        Calcula hash da entrega do bloco gênesis
        Usa parâmetros fixos para garantir reprodutibilidade
        """
        delivery_data = {
            'timestamp': GENESIS_TIMESTAMP,
            'coords': GENESIS_COORDS,
            'contract_id': GENESIS_CONTRACT_ID,
            'type': 'genesis'
        }
        delivery_string = json.dumps(delivery_data, sort_keys=True)
        return hashlib.sha256(delivery_string.encode()).hexdigest()

    def create_block(
        self,
        timestamp: float,
        start_coords: Coordinates,
        end_coords: Coordinates,
        delivery_hash: str,
        contract_id: str
    ) -> Dict:
        """
        Cria novo bloco
        """
        # Pegar hash do último bloco
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT hash FROM blocks ORDER BY timestamp DESC LIMIT 1')
            last_block = cursor.fetchone()
            previous_hash = last_block[0] if last_block else GENESIS_HASH

        # Criar bloco
        block_data = {
            'timestamp': timestamp,
            'start_coords': start_coords.to_dict(),
            'end_coords': end_coords.to_dict(),
            'delivery_hash': delivery_hash,
            'previous_hash': previous_hash,
            'contract_id': contract_id
        }

        # Calcular hash
        block_string = json.dumps(block_data, sort_keys=True)
        block_hash = hashlib.sha256(block_string.encode()).hexdigest()
        block_data['hash'] = block_hash

        return block_data

    def add_block(self, block: Dict) -> bool:
        """
        Adiciona bloco à chain
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO blocks (
                        hash, timestamp, start_lat, start_lon,
                        end_lat, end_lon, delivery_hash,
                        previous_hash, contract_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    block['hash'],
                    block['timestamp'],
                    block['start_coords']['latitude'],
                    block['start_coords']['longitude'],
                    block['end_coords']['latitude'],
                    block['end_coords']['longitude'],
                    block['delivery_hash'],
                    block['previous_hash'],
                    block['contract_id'],
                    time.time()
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def verify_chain(self) -> bool:
        """
        Verifica integridade da chain
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks ORDER BY timestamp')
            blocks = cursor.fetchall()

            # Verificar genesis
            if not blocks or blocks[0][8] != GENESIS_INFO['contract_id']:
                return False

            # Verificar cadeia
            previous_hash = GENESIS_HASH
            for block in blocks[1:]:
                block_data = {
                    'timestamp': block[1],
                    'start_coords': (block[2], block[3]),
                    'end_coords': (block[4], block[5]),
                    'delivery_hash': block[6],
                    'previous_hash': block[7],
                    'contract_id': block[8]
                }
                
                # Verificar link
                if block[7] != previous_hash:
                    return False
                
                # Verificar hash
                block_string = json.dumps(block_data, sort_keys=True)
                calculated_hash = hashlib.sha256(block_string.encode()).hexdigest()
                if calculated_hash != block[0]:
                    return False
                
                previous_hash = block[0]

            return True

    def calculate_hash(self, data: str) -> str:
        """
        Calcula hash SHA256
        """
        return hashlib.sha256(data.encode()).hexdigest()

    def add_pending_contract(self, contract: Dict) -> bool:
        """
        Adiciona contrato pendente
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO pending_contracts (
                        contract_id, start_lat, start_lon,
                        end_lat, end_lon, timestamp,
                        status, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    contract['id'],
                    contract['pickup_location'][0],
                    contract['pickup_location'][1],
                    contract['delivery_location'][0],
                    contract['delivery_location'][1],
                    contract['timestamp'],
                    'pending',
                    json.dumps(contract.get('metadata', {}))
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def get_pending_contracts_in_region(
        self,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float
    ) -> List[Dict]:
        """
        Retorna contratos pendentes em uma região
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM pending_contracts 
                WHERE start_lat BETWEEN ? AND ?
                AND start_lon BETWEEN ? AND ?
                AND status = 'pending'
            ''', (min_lat, max_lat, min_lon, max_lon))
            
            contracts = []
            for row in cursor.fetchall():
                contract = {
                    'id': row[0],
                    'pickup_location': (row[1], row[2]),
                    'delivery_location': (row[3], row[4]),
                    'timestamp': row[5],
                    'status': row[6],
                    'metadata': json.loads(row[7])
                }
                contracts.append(contract)
            
            return contracts 