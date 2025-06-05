"""
Blockchain Monitoring System
"""

import time
import logging
import schedule
from wallet_manager import WalletManager
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='data/logs/blockchain_monitor.log'
)
logger = logging.getLogger(__name__)

class BlockchainMonitor:
    def __init__(self):
        self.wallet_manager = WalletManager()
        
    def verify_chain_integrity(self):
        """Verify blockchain integrity"""
        conn = self.wallet_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all blocks ordered by index
            cursor.execute("""
                SELECT block_index, hash, previous_hash, difficulty
                FROM blocks
                ORDER BY block_index ASC
            """)
            blocks = cursor.fetchall()
            
            issues = []
            previous_hash = "0" * 64  # Genesis previous hash
            
            for block in blocks:
                block_index, block_hash, prev_hash, difficulty = block
                
                # Skip genesis block
                if block_index == 0:
                    if block_hash != "0" * 64 or prev_hash != "0" * 64:
                        issues.append(f"Bloco gênesis inválido")
                    continue
                
                # Verify chain linkage
                if prev_hash != previous_hash:
                    issues.append(
                        f"Quebra de encadeamento no bloco {block_index}"
                    )
                
                # Verify proof of work
                if not block_hash.startswith("0" * difficulty):
                    issues.append(
                        f"PoW inválido no bloco {block_index}"
                    )
                    
                previous_hash = block_hash
                
            return issues
            
        finally:
            cursor.close()
            conn.close()
            
    def verify_transactions(self):
        """Verify transaction integrity"""
        conn = self.wallet_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            issues = []
            
            # Find orphaned transactions
            cursor.execute("""
                SELECT t.tx_hash
                FROM transactions t
                LEFT JOIN blocks b ON t.block_hash = b.hash
                WHERE b.hash IS NULL
                AND t.tx_type != 'mining_reward'
            """)
            orphans = cursor.fetchall()
            
            if orphans:
                issues.append(
                    f"Encontradas {len(orphans)} transações órfãs"
                )
                
            # Find duplicate transactions
            cursor.execute("""
                SELECT tx_hash, COUNT(*) as count
                FROM transactions
                GROUP BY tx_hash
                HAVING count > 1
            """)
            duplicates = cursor.fetchall()
            
            if duplicates:
                issues.append(
                    f"Encontradas {len(duplicates)} transações duplicadas"
                )
                
            # Verify mining rewards
            cursor.execute("""
                SELECT b.block_index, b.mining_reward, t.amount
                FROM blocks b
                LEFT JOIN transactions t ON t.block_hash = b.hash 
                    AND t.tx_type = 'mining_reward'
                WHERE b.block_index > 0
                AND (t.amount IS NULL OR t.amount != b.mining_reward)
            """)
            invalid_rewards = cursor.fetchall()
            
            if invalid_rewards:
                issues.append(
                    f"Encontrados {len(invalid_rewards)} blocos com recompensa incorreta"
                )
                
            return issues
            
        finally:
            cursor.close()
            conn.close()
            
    def generate_daily_report(self):
        """Generate daily blockchain report"""
        logger.info("Gerando relatório diário...")
        
        # Generate reports
        self.wallet_manager.generate_wallet_report()
        self.wallet_manager.generate_mining_report()
        
        # Get last 24h transactions
        yesterday = time.time() - 86400  # 24 hours ago
        self.wallet_manager.generate_transaction_report(
            start_time=yesterday,
            end_time=time.time()
        )
        
    def monitor_task(self):
        """Main monitoring task"""
        logger.info("Iniciando verificação da blockchain...")
        
        # Verify chain integrity
        chain_issues = self.verify_chain_integrity()
        if chain_issues:
            logger.error("Problemas encontrados na cadeia:")
            for issue in chain_issues:
                logger.error(f"  - {issue}")
        else:
            logger.info("Cadeia de blocos íntegra")
            
        # Verify transactions
        tx_issues = self.verify_transactions()
        if tx_issues:
            logger.error("Problemas encontrados nas transações:")
            for issue in tx_issues:
                logger.error(f"  - {issue}")
        else:
            logger.info("Transações verificadas e corretas")
            
        # Recalculate balances
        self.wallet_manager.recalculate_all_balances()
        
def main():
    """Main function"""
    monitor = BlockchainMonitor()
    
    # Schedule tasks
    schedule.every(10).minutes.do(monitor.monitor_task)
    schedule.every().day.at("00:00").do(monitor.generate_daily_report)
    
    # Run initial check
    monitor.monitor_task()
    monitor.generate_daily_report()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 