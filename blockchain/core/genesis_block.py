"""
Bloco Genesis - Referência Global do Sistema
Este arquivo define o bloco genesis que será usado como referência em toda a rede.
Uma vez criado, este bloco NUNCA deve ser alterado.
"""

import hashlib
import json
import time
from typing import Dict, List
from datetime import datetime

# Definições fixas do Genesis
GENESIS_TIMESTAMP: float = 0
GENESIS_PREVIOUS_HASH: str = "0" * 64
GENESIS_DIFFICULTY: int = 4  # Dificuldade inicial
GENESIS_NONCE: int = 0
GENESIS_MINER: str = "0" * 40  # Endereço do minerador do bloco genesis
GENESIS_REWARD: float = 0  # Não há recompensa no bloco genesis

class GenesisBlock:
    """Classe que define o bloco genesis imutável"""
    
    @staticmethod
    def get_genesis_data() -> Dict:
        """Retorna os dados do bloco genesis"""
        genesis_tx = {
            "tx_id": "genesis",
            "tx_type": "genesis",
            "from_address": GENESIS_MINER,
            "to_address": GENESIS_MINER,
            "amount": 0,
            "timestamp": GENESIS_TIMESTAMP,
            "data": {"message": "Bloco Genesis da LogiChain"}
        }
        
        block_data = {
            'index': 0,
            'timestamp': GENESIS_TIMESTAMP,
            'transactions': [genesis_tx],
            'previous_hash': GENESIS_PREVIOUS_HASH,
            'difficulty': GENESIS_DIFFICULTY,
            'nonce': GENESIS_NONCE,
            'miner_address': GENESIS_MINER,
            'mining_reward': GENESIS_REWARD
        }
        return block_data

    @staticmethod
    def calculate_genesis_hash() -> str:
        """Calcula o hash do bloco genesis"""
        block_string = json.dumps(GenesisBlock.get_genesis_data(), sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    @staticmethod
    def get_genesis_block() -> Dict:
        """Retorna o bloco genesis completo com seu hash"""
        block_data = GenesisBlock.get_genesis_data()
        block_data['hash'] = GenesisBlock.calculate_genesis_hash()
        return block_data

    @staticmethod
    def verify_genesis_hash(hash_to_verify: str) -> bool:
        """Verifica se um hash corresponde ao hash do genesis"""
        return hash_to_verify == GenesisBlock.calculate_genesis_hash()

    @staticmethod
    def verify_genesis_block(block: Dict) -> bool:
        """Verifica se um bloco é o bloco genesis válido"""
        genesis_data = GenesisBlock.get_genesis_block()
        
        # Verifica campos obrigatórios
        required_fields = [
            'index', 'timestamp', 'transactions', 'previous_hash',
            'difficulty', 'nonce', 'miner_address', 'mining_reward', 'hash'
        ]
        
        for field in required_fields:
            if field not in block:
                return False
        
        # Verifica valores
        if (block['index'] != 0 or
            block['timestamp'] != GENESIS_TIMESTAMP or
            block['previous_hash'] != GENESIS_PREVIOUS_HASH or
            block['difficulty'] != GENESIS_DIFFICULTY or
            block['nonce'] != GENESIS_NONCE or
            block['miner_address'] != GENESIS_MINER or
            block['mining_reward'] != GENESIS_REWARD or
            block['hash'] != genesis_data['hash']):
            return False
            
        return True 