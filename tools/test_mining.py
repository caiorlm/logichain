"""
Script para testar funcionalidade de mineração
"""

import os
import sys
from pathlib import Path
import logging
import time
import json
from datetime import datetime

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from blockchain.database.db_manager import get_db_connection
from blockchain.wallet.key_manager import KeyManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def verify_mining_prerequisites():
    """Verifica pré-requisitos para mineração"""
    try:
        # Define paths
        data_dir = ROOT_DIR / 'data' / 'blockchain'
        db_path = data_dir / 'chain.db'
        wallet_dir = data_dir / 'wallets'
        
        # Verifica banco
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica carteira
        key_manager = KeyManager(str(db_path), str(wallet_dir))
        key_manager.load_encryption("default_password")
        
        # Obtém primeira carteira
        cursor.execute("SELECT address FROM wallets LIMIT 1")
        result = cursor.fetchone()
        
        if not result:
            logging.error("❌ Nenhuma carteira encontrada")
            return False
            
        address = result[0]
        wallet = key_manager.load_wallet(address)
        
        if not wallet:
            logging.error("❌ Falha ao carregar carteira")
            return False
            
        logging.info(f"✅ Carteira carregada: {address}")
        
        # Verifica estado do banco
        cursor.execute("SELECT COUNT(*) FROM blocks")
        total_blocks = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT hash, block_index, timestamp
            FROM blocks
            ORDER BY block_index DESC
            LIMIT 1
        """)
        last_block = cursor.fetchone()
        
        if last_block:
            logging.info(f"""
Último bloco:
  Hash: {last_block[0][:8]}...
  Índice: {last_block[1]}
  Timestamp: {datetime.fromtimestamp(last_block[2])}
""")
        
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Erro ao verificar pré-requisitos: {str(e)}")
        return False

def monitor_mining(duration=60):
    """Monitora processo de mineração"""
    try:
        start_time = time.time()
        initial_blocks = 0
        
        # Obtém contagem inicial
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM blocks")
        initial_blocks = cursor.fetchone()[0]
        conn.close()
        
        logging.info(f"Iniciando monitoramento ({duration}s)...")
        logging.info(f"Blocos iniciais: {initial_blocks}")
        
        while (time.time() - start_time) < duration:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verifica novos blocos
            cursor.execute("SELECT COUNT(*) FROM blocks")
            current_blocks = cursor.fetchone()[0]
            
            if current_blocks > initial_blocks:
                # Analisa novos blocos
                cursor.execute("""
                    SELECT hash, block_index, timestamp, 
                           difficulty, nonce, miner_address, mining_reward
                    FROM blocks
                    WHERE block_index > ?
                    ORDER BY block_index ASC
                """, (initial_blocks,))
                
                new_blocks = cursor.fetchall()
                
                for block in new_blocks:
                    logging.info(f"""
🎉 Novo bloco minerado!
  Hash: {block[0][:8]}...
  Índice: {block[1]}
  Timestamp: {datetime.fromtimestamp(block[2])}
  Dificuldade: {block[3]}
  Nonce: {block[4]}
  Minerador: {block[5]}
  Recompensa: {block[6]}
""")
                    
                    # Verifica transação de recompensa
                    cursor.execute("""
                        SELECT tx_hash, amount
                        FROM transactions
                        WHERE block_hash = ?
                        AND tx_type = 'reward'
                    """, (block[0],))
                    
                    reward_tx = cursor.fetchone()
                    if reward_tx:
                        logging.info(f"""
💰 Transação de recompensa:
  Hash: {reward_tx[0][:8]}...
  Valor: {reward_tx[1]}
""")
                    else:
                        logging.error("❌ Transação de recompensa não encontrada!")
                
                initial_blocks = current_blocks
            
            conn.close()
            time.sleep(1)
        
        return True
        
    except Exception as e:
        logging.error(f"Erro ao monitorar mineração: {str(e)}")
        return False

def verify_mining_results():
    """Verifica resultados da mineração"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica blocos minerados
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT miner_address) as miners,
                   MIN(mining_reward) as min_reward,
                   MAX(mining_reward) as max_reward,
                   AVG(mining_reward) as avg_reward
            FROM blocks
        """)
        
        stats = cursor.fetchone()
        
        logging.info(f"""
📊 Estatísticas de mineração:
  Total de blocos: {stats[0]}
  Mineradores únicos: {stats[1]}
  Recompensa min/max/média: {stats[2]:.2f}/{stats[3]:.2f}/{stats[4]:.2f}
""")
        
        # Verifica transações de recompensa
        cursor.execute("""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE tx_type = 'reward'
        """)
        
        reward_txs = cursor.fetchone()[0]
        logging.info(f"Total de transações de recompensa: {reward_txs}")
        
        # Verifica integridade
        assert stats[0] == reward_txs, "Número de blocos não corresponde ao número de recompensas"
        
        conn.close()
        logging.info("✅ Verificação concluída com sucesso")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao verificar resultados: {str(e)}")
        return False

def main():
    """Executa teste de mineração"""
    try:
        logging.info("🔄 Iniciando teste de mineração...")
        
        # Verifica pré-requisitos
        if not verify_mining_prerequisites():
            logging.error("❌ Falha nos pré-requisitos")
            return
        
        # Monitora mineração
        if not monitor_mining(duration=60):
            logging.error("❌ Falha no monitoramento")
            return
        
        # Verifica resultados
        if not verify_mining_results():
            logging.error("❌ Falha na verificação")
            return
        
        logging.info("✅ Teste de mineração concluído com sucesso!")
        
    except Exception as e:
        logging.error(f"❌ Erro durante teste: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 