#!/usr/bin/env python3
"""
Script to manage backups of LogiChain system
"""
import os
import sys
import argparse
from pathlib import Path
import shutil
import tarfile
import json
from datetime import datetime, timedelta
import hashlib
import logging
from typing import List, Dict

class BackupManager:
    def __init__(self, 
                 data_dir: str = "data",
                 backup_dir: str = "backups",
                 retention_days: int = 30):
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def create_manifest(self, backup_files: List[Path]) -> Dict:
        """Create backup manifest with metadata"""
        manifest = {
            "timestamp": datetime.utcnow().isoformat(),
            "files": []
        }
        
        for file_path in backup_files:
            if file_path.is_file():
                manifest["files"].append({
                    "path": str(file_path.relative_to(self.data_dir)),
                    "size": file_path.stat().st_size,
                    "checksum": self.calculate_checksum(file_path)
                })
        
        return manifest
    
    def create_backup(self, include_dirs: List[str] = None) -> Path:
        """Create a new backup"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"logichain_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        # Default directories to backup
        if not include_dirs:
            include_dirs = [
                "blockchain",
                "contracts",
                "keys",
                "ssl"
            ]
        
        # Collect files to backup
        backup_files = []
        for dir_name in include_dirs:
            dir_path = self.data_dir / dir_name
            if dir_path.exists():
                backup_files.extend(dir_path.rglob("*"))
        
        # Create manifest
        manifest = self.create_manifest(backup_files)
        
        # Create backup archive
        archive_path = backup_path.with_suffix(".tar.gz")
        with tarfile.open(archive_path, "w:gz") as tar:
            # Add manifest
            manifest_path = backup_path.with_name(f"{backup_name}_manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            tar.add(manifest_path, arcname=manifest_path.name)
            
            # Add data files
            for file_path in backup_files:
                if file_path.is_file():
                    tar.add(file_path, 
                           arcname=str(file_path.relative_to(self.data_dir)))
            
            # Add environment files
            env_files = [
                Path("config/.env.production"),
                Path("config/.env.template")
            ]
            for env_file in env_files:
                if env_file.exists():
                    tar.add(env_file, 
                           arcname=f"config/{env_file.name}")
        
        # Cleanup manifest file
        manifest_path.unlink()
        
        self.logger.info(f"Created backup: {archive_path}")
        return archive_path
    
    def restore_backup(self, backup_path: Path) -> bool:
        """Restore from backup"""
        if not backup_path.exists():
            self.logger.error(f"Backup file not found: {backup_path}")
            return False
        
        # Create temporary directory for restoration
        temp_dir = self.backup_dir / "temp_restore"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Extract backup
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)
            
            # Load and verify manifest
            manifest_file = next(temp_dir.glob("*_manifest.json"))
            with open(manifest_file) as f:
                manifest = json.load(f)
            
            # Verify files
            for file_info in manifest["files"]:
                file_path = temp_dir / file_info["path"]
                if not file_path.exists():
                    raise ValueError(f"Missing file in backup: {file_info['path']}")
                
                checksum = self.calculate_checksum(file_path)
                if checksum != file_info["checksum"]:
                    raise ValueError(
                        f"Checksum mismatch for {file_info['path']}"
                    )
            
            # Restore files
            for file_info in manifest["files"]:
                src_path = temp_dir / file_info["path"]
                dst_path = self.data_dir / file_info["path"]
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
            
            # Restore environment files
            env_files = temp_dir.glob("config/.env.*")
            for env_file in env_files:
                dst_path = Path("config") / env_file.name
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(env_file, dst_path)
            
            self.logger.info(f"Successfully restored from backup: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {str(e)}")
            return False
            
        finally:
            # Cleanup
            shutil.rmtree(temp_dir)
    
    def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        for backup_file in self.backup_dir.glob("logichain_backup_*.tar.gz"):
            try:
                # Extract timestamp from filename
                timestamp_str = backup_file.stem.split("_")[-1]
                backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if backup_date < cutoff_date:
                    backup_file.unlink()
                    self.logger.info(f"Removed old backup: {backup_file}")
            
            except (ValueError, IndexError):
                self.logger.warning(
                    f"Could not parse date from backup file: {backup_file}"
                )
    
    def list_backups(self) -> List[Dict]:
        """List available backups with details"""
        backups = []
        
        for backup_file in self.backup_dir.glob("logichain_backup_*.tar.gz"):
            try:
                # Extract backup details
                timestamp_str = backup_file.stem.split("_")[-1]
                backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                backups.append({
                    "file": backup_file.name,
                    "date": backup_date.isoformat(),
                    "size": backup_file.stat().st_size,
                    "path": str(backup_file)
                })
            
            except (ValueError, IndexError):
                self.logger.warning(
                    f"Could not parse backup file: {backup_file}"
                )
        
        return sorted(backups, key=lambda x: x["date"], reverse=True)

def main():
    parser = argparse.ArgumentParser(description="Manage LogiChain backups")
    parser.add_argument('--action', choices=['create', 'restore', 'list', 'cleanup'],
                      required=True, help="Action to perform")
    parser.add_argument('--data-dir', default="data",
                      help="Data directory to backup")
    parser.add_argument('--backup-dir', default="backups",
                      help="Directory for backups")
    parser.add_argument('--retention-days', type=int, default=30,
                      help="Number of days to retain backups")
    parser.add_argument('--backup-file',
                      help="Backup file to restore from")
    parser.add_argument('--include-dirs', nargs='+',
                      help="Specific directories to include in backup")
    
    args = parser.parse_args()
    
    manager = BackupManager(
        data_dir=args.data_dir,
        backup_dir=args.backup_dir,
        retention_days=args.retention_days
    )
    
    if args.action == 'create':
        backup_path = manager.create_backup(args.include_dirs)
        print(f"Created backup: {backup_path}")
    
    elif args.action == 'restore':
        if not args.backup_file:
            print("Error: --backup-file required for restore")
            sys.exit(1)
        
        success = manager.restore_backup(Path(args.backup_file))
        if not success:
            sys.exit(1)
    
    elif args.action == 'list':
        backups = manager.list_backups()
        if not backups:
            print("No backups found")
        else:
            print("\nAvailable backups:")
            for backup in backups:
                size_mb = backup["size"] / (1024 * 1024)
                print(f"\nFile: {backup['file']}")
                print(f"Date: {backup['date']}")
                print(f"Size: {size_mb:.2f} MB")
                print(f"Path: {backup['path']}")
    
    elif args.action == 'cleanup':
        manager.cleanup_old_backups()
        print("Cleaned up old backups")

if __name__ == "__main__":
    main() 