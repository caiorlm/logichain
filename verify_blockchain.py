"""
Blockchain Verification Script
"""

import sqlite3
import logging
import hashlib
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
DIFFICULTY = 4
BLOCK_REWARD = 50.0

def verify_block_hash(block_data):
    """Verify if block hash is correct"""
    block_string = f"{block_data['timestamp']}{block_data['transactions']}{block_data['previous_hash']}{block_data['nonce']}"
    calculated_hash = hashlib.sha256(block_string.encode()).hexdigest()
    return calculated_hash == block_data['hash']

def verify_blockchain():
    """Verify blockchain integrity"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all blocks ordered by index
        cursor.execute("""
            SELECT block_index, hash, previous_hash, timestamp, 
                   difficulty, nonce, mining_reward, miner_address
            FROM blocks 
            ORDER BY block_index ASC
        """)
        blocks = cursor.fetchall()
        
        if not blocks:
            logger.error("Blockchain vazia!")
            return
            
        total_blocks = len(blocks)
        invalid_pow = 0
        invalid_hash = 0
        invalid_chain = 0
        invalid_reward = 0
        
        logger.info(f"Verificando {total_blocks} blocos...")
        
        for i, block in enumerate(blocks):
            (block_index, block_hash, previous_hash, timestamp,
             difficulty, nonce, mining_reward, miner_address) = block
             
            # Get block transactions
            cursor.execute("""
                SELECT tx_type, from_address, to_address, amount
                FROM transactions
                WHERE block_hash = ?
            """, (block_hash,))
            transactions = cursor.fetchall()
            
            # 1. Verify block hash starts with correct number of zeros
            if not block_hash.startswith('0' * DIFFICULTY):
                invalid_pow += 1
                logger.warning(f"Bloco {block_index} não tem proof of work válido: {block_hash}")
            
            # 2. Verify chain linkage (except genesis)
            if i > 0:
                if previous_hash != blocks[i-1][1]:  # previous block's hash
                    invalid_chain += 1
                    logger.warning(f"Bloco {block_index} tem hash anterior inválido")
            
            # 3. Verify mining reward transaction
            reward_tx = None
            for tx in transactions:
                if tx[0] == 'mining_reward' and tx[1] == '0' * 64:
                    reward_tx = tx
                    break
                    
            if reward_tx:
                if reward_tx[3] != BLOCK_REWARD:
                    invalid_reward += 1
                    logger.warning(f"Bloco {block_index} tem recompensa incorreta: {reward_tx[3]} (esperado: {BLOCK_REWARD})")
            else:
                invalid_reward += 1
                logger.warning(f"Bloco {block_index} não tem transação de recompensa")
            
            # 4. Verify block hash calculation
            block_data = {
                'timestamp': timestamp,
                'transactions': transactions,
                'previous_hash': previous_hash,
                'nonce': nonce,
                'hash': block_hash
            }
            if not verify_block_hash(block_data):
                invalid_hash += 1
                logger.warning(f"Bloco {block_index} tem hash inválido")
                
        # Print summary
        logger.info("\nResumo da verificação:")
        logger.info(f"Total de blocos: {total_blocks}")
        logger.info(f"Blocos com PoW inválido: {invalid_pow}")
        logger.info(f"Blocos com hash inválido: {invalid_hash}")
        logger.info(f"Blocos com encadeamento inválido: {invalid_chain}")
        logger.info(f"Blocos com recompensa inválida: {invalid_reward}")
        
        if invalid_pow == 0 and invalid_hash == 0 and invalid_chain == 0 and invalid_reward == 0:
            logger.info("\nBlockchain está íntegra! ✓")
        else:
            logger.warning("\nBlockchain tem problemas de integridade! ✗")
            
    finally:
        cursor.close()
        conn.close()

def verify_mining_rewards():
    """Verify mining rewards distribution"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get mining rewards by miner
        cursor.execute("""
            SELECT m.miner_address,
                   COUNT(*) as blocks_mined,
                   COUNT(*) * ? as expected_reward,
                   COALESCE(SUM(t.amount), 0) as actual_reward
            FROM blocks m
            LEFT JOIN transactions t ON t.block_hash = m.hash 
                AND t.tx_type = 'mining_reward'
                AND t.from_address = ?
            WHERE m.miner_address IS NOT NULL
            GROUP BY m.miner_address
        """, (BLOCK_REWARD, '0' * 64))
        
        rewards = cursor.fetchall()
        
        logger.info("\nVerificando recompensas de mineração:")
        for miner, blocks, expected, actual in rewards:
            logger.info(f"\nMinerador: {miner}")
            logger.info(f"Blocos minerados: {blocks}")
            logger.info(f"Recompensa esperada: {expected} LOGI")
            logger.info(f"Recompensa recebida: {actual} LOGI")
            
            if expected != actual:
                logger.warning(f"Discrepância nas recompensas! Diferença: {expected - actual} LOGI")
                
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function"""
    logger.info("Iniciando verificação da blockchain...")
    verify_blockchain()
    
    logger.info("\nVerificando distribuição de recompensas...")
    verify_mining_rewards()

if __name__ == "__main__":
    main() 