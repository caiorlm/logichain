"""
Blockchain System Initialization and Validation Script
"""

import logging
import os
import time
import shutil
from datetime import datetime
from typing import Optional
from block import Block, Transaction
from wallet_manager import WalletManager
from mining_manager import MiningManager
from transaction_manager import TransactionManager
from blockchain_monitor import BlockchainMonitor
from blockchain_validator import BlockchainValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlockchainInitializer:
    def __init__(self):
        self.wallet_manager = WalletManager()
        self.mining_manager = MiningManager()
        self.transaction_manager = TransactionManager()
        self.blockchain_monitor = BlockchainMonitor()
        self.validator = BlockchainValidator()
        
    def setup_directories(self):
        """Setup required directories"""
        dirs = [
            'data/blockchain',
            'data/reports',
            'data/logs',
            'data/backups',  # New directory for backups
            'data/wallets'   # Directory for wallet keys
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                logger.info(f"Diretório criado: {dir_path}")
                
    def create_backup(self) -> Optional[str]:
        """Create backup of blockchain database"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'data/backups/chain_{timestamp}.db'
        
        try:
            # Copy database file
            shutil.copy2('data/blockchain/chain.db', backup_path)
            logger.info(f"Backup criado: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Erro ao criar backup: {str(e)}")
            return None
            
    def restore_from_backup(self, backup_path: str) -> bool:
        """Restore blockchain from backup"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup não encontrado: {backup_path}")
                return False
                
            # Stop any running processes
            # TODO: Implement proper shutdown
            
            # Restore database
            shutil.copy2(backup_path, 'data/blockchain/chain.db')
            logger.info(f"Blockchain restaurada do backup: {backup_path}")
            
            # Validate restored chain
            audit = self.validator.audit_blockchain()
            if not audit['success']:
                logger.error("Falha na validação após restauração")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Erro ao restaurar backup: {str(e)}")
            return False
            
    def initialize_system(self) -> bool:
        """Initialize the blockchain system"""
        logger.info("Iniciando inicialização do sistema...")
        
        # 1. Setup directories
        self.setup_directories()
        
        # 2. Create backup before initialization
        self.create_backup()
        
        # 3. Initialize database schema
        logger.info("\n1. Inicializando schema do banco de dados...")
        self.wallet_manager.setup_database()
        
        # 4. Verify genesis block
        logger.info("\n2. Verificando bloco gênesis...")
        conn = self.wallet_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM blocks 
                WHERE block_index = 0
            """)
            has_genesis = cursor.fetchone()[0] > 0
            
            if not has_genesis:
                logger.info("Criando bloco gênesis...")
                genesis_block = Block.create_genesis_block()
                
                # Insert genesis block
                block_data = genesis_block.to_dict()
                cursor.execute("""
                    INSERT INTO blocks (
                        hash, block_index, timestamp,
                        previous_hash, merkle_root,
                        difficulty, nonce,
                        miner_address, mining_reward,
                        state
                    ) VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
                """, (
                    block_data['hash'],
                    block_data['timestamp'],
                    block_data['previous_hash'],
                    block_data['merkle_root'],
                    block_data['difficulty'],
                    block_data['nonce'],
                    block_data['miner_address'],
                    block_data['mining_reward']
                ))
                
                # Insert genesis transaction
                genesis_tx = genesis_block.transactions[0]
                cursor.execute("""
                    INSERT INTO transactions (
                        tx_hash, block_hash, tx_type,
                        from_address, to_address, amount,
                        timestamp, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')
                """, (
                    genesis_tx.tx_hash,
                    genesis_block.hash,
                    genesis_tx.tx_type,
                    genesis_tx.from_address,
                    genesis_tx.to_address,
                    genesis_tx.amount,
                    genesis_tx.timestamp
                ))
                
                conn.commit()
                logger.info("Bloco gênesis criado")
                
        finally:
            cursor.close()
            conn.close()
            
        # 5. Run full validation and correction
        logger.info("\n3. Executando validação completa...")
        validation_result = self.validator.validate_and_fix_blockchain()
        
        if not validation_result['success']:
            logger.error("Falha na validação inicial")
            # Try to restore from backup
            latest_backup = self._get_latest_backup()
            if latest_backup and self.restore_from_backup(latest_backup):
                logger.info("Sistema restaurado do último backup")
            else:
                logger.error("Não foi possível restaurar o sistema")
                return False
                
        # 6. Create new backup after initialization
        self.create_backup()
        
        logger.info("\nInicialização concluída!")
        return True
        
    def _get_latest_backup(self) -> Optional[str]:
        """Get path of latest backup file"""
        backup_dir = 'data/backups'
        if not os.path.exists(backup_dir):
            return None
            
        backups = [f for f in os.listdir(backup_dir) if f.startswith('chain_')]
        if not backups:
            return None
            
        latest = max(backups)
        return os.path.join(backup_dir, latest)
        
    def cleanup_old_backups(self, keep_days: int = 7):
        """Remove backups older than specified days"""
        backup_dir = 'data/backups'
        if not os.path.exists(backup_dir):
            return
            
        current_time = time.time()
        max_age = keep_days * 24 * 3600
        
        for backup in os.listdir(backup_dir):
            if not backup.startswith('chain_'):
                continue
                
            backup_path = os.path.join(backup_dir, backup)
            file_age = current_time - os.path.getmtime(backup_path)
            
            if file_age > max_age:
                try:
                    os.remove(backup_path)
                    logger.info(f"Backup antigo removido: {backup}")
                except Exception as e:
                    logger.error(f"Erro ao remover backup {backup}: {str(e)}")
                    
def main():
    """Main function"""
    initializer = BlockchainInitializer()
    
    # Initialize system
    if not initializer.initialize_system():
        logger.error("Falha na inicialização do sistema")
        return
        
    # Cleanup old backups
    initializer.cleanup_old_backups()

if __name__ == "__main__":
    main() 