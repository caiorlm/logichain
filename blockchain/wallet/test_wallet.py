"""
Test script para validar funcionalidade da carteira
"""

import os
import sys
import sqlite3
from pathlib import Path
import logging

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from blockchain.wallet.key_manager import KeyManager
from blockchain.database.db_manager import get_db_connection

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_wallet_creation():
    """Testa criação de carteira com mnemonic"""
    key_manager = KeyManager()
    
    # Gera nova carteira
    wallet = key_manager.generate_new_wallet()
    logging.info(f"Nova carteira criada com endereço: {wallet['address']}")
    
    # Verifica se mnemonic gera mesmas chaves
    restored_wallet = key_manager.restore_from_mnemonic(wallet['mnemonic'])
    assert wallet['address'] == restored_wallet['address'], "Endereço restaurado não corresponde"
    assert wallet['public_key'] == restored_wallet['public_key'], "Chave pública restaurada não corresponde"
    logging.info("✅ Restauração via mnemonic validada com sucesso")
    
    return wallet

def test_wallet_storage(wallet):
    """Testa armazenamento da carteira no banco"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verifica se carteira foi salva
    cursor.execute("""
        SELECT address, public_key, encrypted_private_key, mnemonic
        FROM wallets 
        WHERE address = ?
    """, (wallet['address'],))
    
    stored_wallet = cursor.fetchone()
    assert stored_wallet is not None, "Carteira não encontrada no banco"
    
    address, public_key, encrypted_private_key, mnemonic = stored_wallet
    assert address == wallet['address'], "Endereço armazenado não corresponde"
    assert public_key == wallet['public_key'], "Chave pública armazenada não corresponde"
    assert mnemonic == wallet['mnemonic'], "Mnemonic armazenado não corresponde"
    
    logging.info("✅ Armazenamento no banco validado com sucesso")
    
    conn.close()

def main():
    """Executa todos os testes"""
    try:
        logging.info("Iniciando testes da carteira...")
        
        # Testa criação e restauração
        wallet = test_wallet_creation()
        
        # Testa armazenamento
        test_wallet_storage(wallet)
        
        logging.info("✅ Todos os testes concluídos com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro nos testes: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 