#!/usr/bin/env python3
"""
Script to clean up LogiChain system
"""
import os
import sys
import argparse
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import docker
from typing import List, Dict, Any

class SystemCleaner:
    def __init__(self, log_file: str = "data/logs/cleanup.log"):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize Docker client
        self.docker = docker.from_env()
    
    def clean_logs(self, days: int = 30) -> int:
        """Clean old log files"""
        log_dir = Path("data/logs")
        cutoff_date = datetime.now() - timedelta(days=days)
        count = 0
        
        for log_file in log_dir.glob("*.log*"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    log_file.unlink()
                    count += 1
                    self.logger.info(f"Removed old log file: {log_file}")
            except Exception as e:
                self.logger.error(f"Failed to process {log_file}: {str(e)}")
        
        return count
    
    def clean_backups(self, days: int = 30) -> int:
        """Clean old backup files"""
        backup_dir = Path("backups")
        cutoff_date = datetime.now() - timedelta(days=days)
        count = 0
        
        for backup_file in backup_dir.glob("logichain_backup_*.tar.gz"):
            try:
                # Extract date from filename
                date_str = backup_file.stem.split("_")[-1]
                backup_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                
                if backup_date < cutoff_date:
                    backup_file.unlink()
                    count += 1
                    self.logger.info(f"Removed old backup: {backup_file}")
            except Exception as e:
                self.logger.error(f"Failed to process {backup_file}: {str(e)}")
        
        return count
    
    def clean_temp_files(self) -> int:
        """Clean temporary files"""
        temp_patterns = [
            "*.tmp",
            "*.temp",
            "*.bak",
            "*.swp",
            "*.swo"
        ]
        count = 0
        
        for pattern in temp_patterns:
            for temp_file in Path().rglob(pattern):
                try:
                    temp_file.unlink()
                    count += 1
                    self.logger.info(f"Removed temp file: {temp_file}")
                except Exception as e:
                    self.logger.error(f"Failed to remove {temp_file}: {str(e)}")
        
        return count
    
    def clean_docker(self) -> Dict[str, int]:
        """Clean Docker resources"""
        results = {
            "containers": 0,
            "images": 0,
            "volumes": 0,
            "networks": 0
        }
        
        try:
            # Remove stopped containers
            containers = self.docker.containers.list(
                all=True,
                filters={"status": "exited"}
            )
            for container in containers:
                container.remove()
                results["containers"] += 1
                self.logger.info(f"Removed container: {container.name}")
            
            # Remove unused images
            images = self.docker.images.prune()
            results["images"] = len(images["ImagesDeleted"] or [])
            
            # Remove unused volumes
            volumes = self.docker.volumes.prune()
            results["volumes"] = len(volumes["VolumesDeleted"] or [])
            
            # Remove unused networks
            networks = self.docker.networks.prune()
            results["networks"] = len(networks["NetworksDeleted"] or [])
            
        except Exception as e:
            self.logger.error(f"Docker cleanup error: {str(e)}")
        
        return results
    
    def clean_blockchain_data(self, days: int = 30) -> int:
        """Clean old blockchain data files"""
        data_dir = Path("data/blockchain")
        cutoff_date = datetime.now() - timedelta(days=days)
        count = 0
        
        # Clean old block files
        for block_file in data_dir.glob("block_*.json"):
            try:
                mtime = datetime.fromtimestamp(block_file.stat().st_mtime)
                if mtime < cutoff_date:
                    block_file.unlink()
                    count += 1
                    self.logger.info(f"Removed old block file: {block_file}")
            except Exception as e:
                self.logger.error(f"Failed to process {block_file}: {str(e)}")
        
        return count
    
    def clean_contract_data(self, days: int = 30) -> int:
        """Clean expired contract data"""
        contracts_dir = Path("data/contracts")
        cutoff_date = datetime.now() - timedelta(days=days)
        count = 0
        
        for contract_file in contracts_dir.glob("*.json"):
            try:
                # Read contract metadata
                with open(contract_file) as f:
                    contract = json.load(f)
                
                # Check if contract is expired
                expiry = datetime.fromisoformat(contract.get("expiry_date", ""))
                if expiry < cutoff_date:
                    contract_file.unlink()
                    count += 1
                    self.logger.info(f"Removed expired contract: {contract_file}")
            except Exception as e:
                self.logger.error(f"Failed to process {contract_file}: {str(e)}")
        
        return count
    
    def vacuum_database(self) -> bool:
        """Vacuum SQLite database"""
        db_file = Path("data/blockchain/chain.db")
        if not db_file.exists():
            return False
        
        try:
            import sqlite3
            conn = sqlite3.connect(db_file)
            conn.execute("VACUUM")
            conn.close()
            self.logger.info("Vacuumed database")
            return True
        except Exception as e:
            self.logger.error(f"Database vacuum error: {str(e)}")
            return False
    
    def clean_all(self, days: int = 30) -> Dict[str, Any]:
        """Run all cleanup operations"""
        results = {
            "logs_removed": self.clean_logs(days),
            "backups_removed": self.clean_backups(days),
            "temp_files_removed": self.clean_temp_files(),
            "docker": self.clean_docker(),
            "blockchain_files_removed": self.clean_blockchain_data(days),
            "contracts_removed": self.clean_contract_data(days),
            "database_vacuumed": self.vacuum_database()
        }
        
        return results

def main():
    parser = argparse.ArgumentParser(description="Clean up LogiChain system")
    parser.add_argument('--days', type=int, default=30,
                      help="Number of days to keep files")
    parser.add_argument('--log-file', default="data/logs/cleanup.log",
                      help="Log file path")
    parser.add_argument('--skip-docker', action='store_true',
                      help="Skip Docker cleanup")
    parser.add_argument('--skip-blockchain', action='store_true',
                      help="Skip blockchain data cleanup")
    parser.add_argument('--skip-contracts', action='store_true',
                      help="Skip contracts cleanup")
    parser.add_argument('--skip-database', action='store_true',
                      help="Skip database vacuum")
    
    args = parser.parse_args()
    
    cleaner = SystemCleaner(args.log_file)
    
    results = {
        "logs_removed": cleaner.clean_logs(args.days),
        "backups_removed": cleaner.clean_backups(args.days),
        "temp_files_removed": cleaner.clean_temp_files()
    }
    
    if not args.skip_docker:
        results["docker"] = cleaner.clean_docker()
    
    if not args.skip_blockchain:
        results["blockchain_files_removed"] = cleaner.clean_blockchain_data(args.days)
    
    if not args.skip_contracts:
        results["contracts_removed"] = cleaner.clean_contract_data(args.days)
    
    if not args.skip_database:
        results["database_vacuumed"] = cleaner.vacuum_database()
    
    print("\nCleanup Results:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main() 