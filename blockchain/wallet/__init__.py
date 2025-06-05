"""
Módulo de carteiras da blockchain
"""

import os
from pathlib import Path
from .key_manager import KeyManager

# Configuração de caminhos
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / 'data' / 'blockchain'
WALLET_DIR = DATA_DIR / 'wallets'
DB_PATH = DATA_DIR / 'chain.db'

# Instância global do KeyManager
key_manager = KeyManager(str(DB_PATH), str(WALLET_DIR))

def init_wallet_system(password: str = None) -> bool:
    """
    Inicializa o sistema de carteiras
    
    Args:
        password: Senha opcional para criptografia
        
    Returns:
        True se inicializado com sucesso
    """
    try:
        # Cria diretórios se necessário
        WALLET_DIR.mkdir(parents=True, exist_ok=True)
        
        # Inicializa criptografia se senha fornecida
        if password:
            if not key_manager.load_encryption(password):
                key_manager.init_encryption(password)
        
        return True
        
    except Exception as e:
        print(f"Erro ao inicializar sistema de carteiras: {e}")
        return False

def get_key_manager() -> KeyManager:
    """
    Retorna instância do KeyManager
    
    Returns:
        Instância global do KeyManager
    """
    return key_manager 