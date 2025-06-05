"""
Script de verificação do núcleo da blockchain
"""

import os
import sys
from pathlib import Path
import logging
import sqlite3
import json
from datetime import datetime

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from blockchain.database.db_manager import get_db_connection

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def verify_block_count():
    """Verifica quantidade de blocos na blockchain"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM blocks")
    total_blocks = cursor.fetchone()[0]
    
    if total_blocks == 0:
        logging.error("❌ ERRO: Nenhum bloco encontrado no banco!")
        logging.error("   Possíveis causas:")
        logging.error("   1. Banco de dados vazio ou corrompido")
        logging.error("   2. Erro na migração/inicialização")
        logging.error("   3. Problema no carregamento dos blocos")
    else:
        logging.info(f"✅ Total de blocos: {total_blocks}")
    
    conn.close()
    return total_blocks

def verify_block_structure():
    """Verifica estrutura dos blocos"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtém amostra de blocos (últimos 10)
    cursor.execute("""
        SELECT hash, block_index, timestamp, previous_hash, 
               difficulty, nonce, miner_address, mining_reward,
               merkle_root, version, state, total_transactions
        FROM blocks 
        ORDER BY block_index DESC 
        LIMIT 10
    """)
    
    blocks = cursor.fetchall()
    issues = []
    
    for block in blocks:
        block_dict = {
            'hash': block[0],
            'block_index': block[1],
            'timestamp': block[2],
            'previous_hash': block[3],
            'difficulty': block[4],
            'nonce': block[5],
            'miner_address': block[6],
            'mining_reward': block[7],
            'merkle_root': block[8],
            'version': block[9],
            'state': block[10],
            'total_transactions': block[11]
        }
        
        # Verifica campos obrigatórios
        if not block_dict['hash'] or len(block_dict['hash']) != 64:
            issues.append(f"Bloco {block_dict['block_index']}: Hash inválido")
            
        if not block_dict['miner_address']:
            issues.append(f"Bloco {block_dict['block_index']}: Sem endereço do minerador")
            
        if block_dict['mining_reward'] is None or block_dict['mining_reward'] <= 0:
            issues.append(f"Bloco {block_dict['block_index']}: Recompensa inválida")
            
        if not block_dict['previous_hash'] and block_dict['block_index'] > 0:
            issues.append(f"Bloco {block_dict['block_index']}: Hash anterior ausente")
            
        # Verifica formato do hash (deve ser hexadecimal de 64 caracteres)
        if not all(c in '0123456789abcdef' for c in block_dict['hash'].lower()):
            issues.append(f"Bloco {block_dict['block_index']}: Hash não está em formato hexadecimal")
        
        logging.info(f"Analisando bloco {block_dict['block_index']}:")
        logging.info(f"  Hash: {block_dict['hash'][:8]}...")
        logging.info(f"  Minerador: {block_dict['miner_address']}")
        logging.info(f"  Recompensa: {block_dict['mining_reward']}")
        logging.info(f"  Timestamp: {datetime.fromtimestamp(block_dict['timestamp'])}")
        logging.info("-" * 50)
    
    if issues:
        logging.error("❌ Problemas encontrados:")
        for issue in issues:
            logging.error(f"   - {issue}")
    else:
        logging.info("✅ Estrutura dos blocos verificada com sucesso")
    
    conn.close()
    return len(issues) == 0

def verify_mining_rewards():
    """Verifica distribuição de recompensas de mineração"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Analisa recompensas por minerador
    cursor.execute("""
        SELECT miner_address, 
               COUNT(*) as total_blocks,
               SUM(mining_reward) as total_rewards,
               MIN(mining_reward) as min_reward,
               MAX(mining_reward) as max_reward,
               AVG(mining_reward) as avg_reward
        FROM blocks
        WHERE miner_address IS NOT NULL
        GROUP BY miner_address
    """)
    
    miners = cursor.fetchall()
    
    if not miners:
        logging.error("❌ Nenhuma recompensa de mineração encontrada!")
        return False
    
    logging.info("\nDistribuição de recompensas por minerador:")
    logging.info("-" * 50)
    
    for miner in miners:
        address, blocks, total, min_r, max_r, avg = miner
        logging.info(f"Minerador: {address}")
        logging.info(f"  Blocos minerados: {blocks}")
        logging.info(f"  Total recebido: {total:.2f}")
        logging.info(f"  Min/Média/Max: {min_r:.2f}/{avg:.2f}/{max_r:.2f}")
        logging.info("-" * 30)
    
    # Verifica se há blocos sem recompensa
    cursor.execute("SELECT COUNT(*) FROM blocks WHERE mining_reward IS NULL OR mining_reward <= 0")
    invalid_rewards = cursor.fetchone()[0]
    
    if invalid_rewards > 0:
        logging.error(f"❌ Encontrados {invalid_rewards} blocos com recompensa inválida!")
    else:
        logging.info("✅ Todas as recompensas estão válidas")
    
    conn.close()
    return invalid_rewards == 0

def main():
    """Executa verificações"""
    try:
        logging.info("🔍 Iniciando verificação do núcleo da blockchain...")
        
        # Verifica contagem de blocos
        total_blocks = verify_block_count()
        if total_blocks == 0:
            return
        
        # Verifica estrutura dos blocos
        blocks_ok = verify_block_structure()
        
        # Verifica recompensas
        rewards_ok = verify_mining_rewards()
        
        # Resumo
        logging.info("\n📊 Resumo da verificação:")
        logging.info(f"Total de blocos: {'✅' if total_blocks > 0 else '❌'} ({total_blocks})")
        logging.info(f"Estrutura dos blocos: {'✅' if blocks_ok else '❌'}")
        logging.info(f"Recompensas de mineração: {'✅' if rewards_ok else '❌'}")
        
    except Exception as e:
        logging.error(f"❌ Erro durante verificação: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 