"""
Constantes e configurações do bloco gênesis
"""

# Parâmetros fixos do bloco gênesis
GENESIS_TIMESTAMP = 0
GENESIS_COORDS = (0.0, 0.0)
GENESIS_CONTRACT_ID = "GENESIS_BLOCK_V1"
GENESIS_PREVIOUS_HASH = "0" * 64

# Hash fixa do bloco gênesis (calculada uma vez)
GENESIS_HASH = "b6bcc7dc4f4fc7d0f6adac75cd86193695c68f7d6022a7fadf8f94e0c1f132c4"

# Informações do bloco gênesis
GENESIS_INFO = {
    'contract_id': GENESIS_CONTRACT_ID,
    'timestamp': GENESIS_TIMESTAMP,
    'coords': GENESIS_COORDS,
    'hash': GENESIS_HASH,
    'previous_hash': GENESIS_PREVIOUS_HASH
}

def verify_genesis_block(block):
    """
    Verifica se um bloco é o bloco gênesis válido
    
    Args:
        block: O bloco a ser verificado
        
    Returns:
        bool: True se for o bloco gênesis válido, False caso contrário
    """
    if not block:
        return False
        
    # Verifica os campos obrigatórios
    required_fields = ['contract_id', 'timestamp', 'coords', 'hash', 'previous_hash']
    if not all(field in block for field in required_fields):
        return False
    
    # Verifica se os valores correspondem ao bloco gênesis
    return (
        block['contract_id'] == GENESIS_CONTRACT_ID and
        block['timestamp'] == GENESIS_TIMESTAMP and
        block['coords'] == GENESIS_COORDS and
        block['hash'] == GENESIS_HASH and
        block['previous_hash'] == GENESIS_PREVIOUS_HASH
    ) 