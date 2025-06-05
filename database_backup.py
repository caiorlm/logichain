"""
Database backup and integrity verification system
"""

import sqlite3
import shutil
import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseBackup:
    def __init__(self, db_path: str = "data/blockchain/chain.db"):
        self.db_path = db_path
        self.backup_dir = "data/backups"
        self.snapshot_dir = "data/snapshots"
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
    def create_backup(self) -> str:
        """Create a full database backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.backup_dir}/chain_{timestamp}.db"
        
        try:
            # Create backup
            shutil.copy2(self.db_path, backup_path)
            
            # Verify backup integrity
            if self.verify_backup(backup_path):
                logger.info(f"Backup created successfully: {backup_path}")
                return backup_path
            else:
                os.remove(backup_path)
                raise Exception("Backup verification failed")
                
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return ""
            
    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup database integrity"""
        try:
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            required_tables = {'blocks', 'transactions', 'wallets'}
            
            if not required_tables.issubset(tables):
                logger.error("Missing required tables in backup")
                return False
                
            # Check block count matches
            cursor.execute("SELECT COUNT(*) FROM blocks")
            backup_blocks = cursor.fetchone()[0]
            
            orig_conn = sqlite3.connect(self.db_path)
            orig_cursor = orig_conn.cursor()
            orig_cursor.execute("SELECT COUNT(*) FROM blocks")
            orig_blocks = orig_cursor.fetchone()[0]
            
            if backup_blocks != orig_blocks:
                logger.error("Block count mismatch in backup")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
            
        finally:
            if 'conn' in locals():
                conn.close()
            if 'orig_conn' in locals():
                orig_conn.close()
                
    def create_snapshot(self) -> str:
        """Create a chain snapshot with essential data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get chain metadata
            cursor.execute("""
                SELECT COUNT(*), MAX(timestamp), MIN(timestamp)
                FROM blocks
            """)
            block_count, latest_time, earliest_time = cursor.fetchone()
            
            # Get latest blocks
            cursor.execute("""
                SELECT hash, previous_hash, timestamp, miner_address
                FROM blocks
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            latest_blocks = [{
                'hash': row[0],
                'previous_hash': row[1],
                'timestamp': row[2],
                'miner': row[3]
            } for row in cursor.fetchall()]
            
            # Get active miners
            cursor.execute("""
                SELECT miner_address, COUNT(*) as blocks
                FROM blocks
                GROUP BY miner_address
                ORDER BY blocks DESC
                LIMIT 10
            """)
            top_miners = [{
                'address': row[0],
                'blocks': row[1]
            } for row in cursor.fetchall()]
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'block_count': block_count,
                'latest_time': latest_time,
                'earliest_time': earliest_time,
                'latest_blocks': latest_blocks,
                'top_miners': top_miners
            }
            
            # Save snapshot
            snapshot_path = f"{self.snapshot_dir}/snapshot_{int(time.time())}.json"
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot, f, indent=2)
                
            logger.info(f"Chain snapshot created: {snapshot_path}")
            return snapshot_path
            
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return ""
            
        finally:
            if 'conn' in locals():
                conn.close()
                
    def restore_from_backup(self, backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            # Verify backup first
            if not self.verify_backup(backup_path):
                raise Exception("Backup verification failed")
                
            # Create temporary backup of current db
            temp_backup = f"{self.backup_dir}/pre_restore_{int(time.time())}.db"
            shutil.copy2(self.db_path, temp_backup)
            
            # Restore from backup
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"Database restored from: {backup_path}")
            logger.info(f"Previous database backed up to: {temp_backup}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
            
    def cleanup_old_backups(self, days: int = 7):
        """Remove backups older than specified days"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            for filename in os.listdir(self.backup_dir):
                if not filename.endswith('.db'):
                    continue
                    
                filepath = os.path.join(self.backup_dir, filename)
                modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if modified < cutoff:
                    os.remove(filepath)
                    logger.info(f"Removed old backup: {filename}")
                    
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

def main():
    """Main backup routine"""
    backup = DatabaseBackup()
    
    # Create backup
    backup_path = backup.create_backup()
    if backup_path:
        logger.info("Database backup successful")
    else:
        logger.error("Database backup failed")
        
    # Create snapshot
    snapshot_path = backup.create_snapshot()
    if snapshot_path:
        logger.info("Chain snapshot successful")
    else:
        logger.error("Chain snapshot failed")
        
    # Cleanup old backups
    backup.cleanup_old_backups()

if __name__ == "__main__":
    main() 