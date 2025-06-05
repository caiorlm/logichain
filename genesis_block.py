"""
Bloco Genesis - Referência Global do Sistema
Este arquivo define o bloco genesis que será usado como referência em toda a rede.
Uma vez criado, este bloco NUNCA deve ser alterado.
"""

import hashlib
import json
import time
from typing import Dict, Tuple

# Definições fixas do Genesis
GENESIS_TIMESTAMP: float = 0
GENESIS_COORDINATES: Tuple[float, float] = (0.0, 0.0)
GENESIS_CONTRACT_ID: str = "GENESIS_BLOCK_V1"
GENESIS_PREVIOUS_HASH: str = "0" * 64
GENESIS_PROOF: str = "GENESIS_PROOF_V1"

class GenesisBlock:
    """Classe que define o bloco genesis imutável"""
    
    @staticmethod
    def get_genesis_data() -> Dict:
        """Retorna os dados do bloco genesis"""
        block_data = {
            'timestamp': GENESIS_TIMESTAMP,
            'start_coords': GENESIS_COORDINATES,
            'end_coords': GENESIS_COORDINATES,
            'delivery_hash': GENESIS_PROOF,
            'previous_hash': GENESIS_PREVIOUS_HASH,
            'contract_id': GENESIS_CONTRACT_ID
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

# Criar o hash do genesis uma vez e armazenar como constante
GENESIS_HASH: str = GenesisBlock.calculate_genesis_hash()

# Informações públicas do bloco genesis
GENESIS_INFO: Dict = {
    'hash': GENESIS_HASH,
    'timestamp': GENESIS_TIMESTAMP,
    'coordinates': GENESIS_COORDINATES,
    'contract_id': GENESIS_CONTRACT_ID,
    'proof': GENESIS_PROOF,
    'previous_hash': GENESIS_PREVIOUS_HASH,
    'created_at': 1710633600  # 17/Mar/2024 00:00:00 UTC (exemplo)
}

if __name__ == "__main__":
    print("\n=== Bloco Genesis - Referência Global ===")
    print(f"Hash: {GENESIS_HASH}")
    print(f"Timestamp: {GENESIS_TIMESTAMP}")
    print(f"Coordenadas: {GENESIS_COORDINATES}")
    print(f"Contract ID: {GENESIS_CONTRACT_ID}")
    print(f"Proof: {GENESIS_PROOF}")
    print(f"Previous Hash: {GENESIS_PREVIOUS_HASH}")
    print("\nEste é o bloco genesis oficial do sistema.")
    print("Este bloco NUNCA deve ser alterado.") 