#!/usr/bin/env python3
"""
Script to manage environment variables for LogiChain
"""
import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any
import secrets
import base64
from cryptography.fernet import Fernet

class EnvManager:
    def __init__(self, env_file: str = ".env.production"):
        self.env_file = Path(env_file)
        self.env_vars: Dict[str, str] = {}
        self.load_env()
    
    def load_env(self):
        """Load environment variables from file"""
        if not self.env_file.exists():
            return
        
        current_key = None
        current_value = []
        
        with open(self.env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '"""' in line and current_key is None:
                    # Start of multiline value
                    key, _ = line.split('=', 1)
                    current_key = key.strip()
                    continue
                
                if current_key is not None:
                    if '"""' in line:
                        # End of multiline value
                        self.env_vars[current_key] = '\n'.join(current_value)
                        current_key = None
                        current_value = []
                    else:
                        current_value.append(line)
                else:
                    key, value = line.split('=', 1)
                    self.env_vars[key.strip()] = value.strip()
    
    def save_env(self):
        """Save environment variables to file"""
        with open(self.env_file, 'w') as f:
            for key, value in self.env_vars.items():
                if '\n' in str(value):
                    f.write(f'{key}="""\n{value}\n"""\n\n')
                else:
                    f.write(f'{key}={value}\n')
    
    def get_value(self, key: str, default: str = "") -> str:
        """Get value of environment variable"""
        return self.env_vars.get(key, default)
    
    def set_value(self, key: str, value: str):
        """Set value of environment variable"""
        self.env_vars[key] = value
        self.save_env()
    
    def encrypt_secrets(self, password: str):
        """Encrypt sensitive values using Fernet"""
        key = base64.urlsafe_b64encode(
            hashlib.sha256(password.encode()).digest()
        )
        f = Fernet(key)
        
        sensitive_keys = [
            "ADMIN_PRIVATE_KEY",
            "VALIDATOR_PRIVATE_KEY",
            "EXECUTOR_PRIVATE_KEY",
            "ESTABLISHMENT_PRIVATE_KEY",
            "ADMIN_PASSWORD",
            "JWT_SECRET_KEY"
        ]
        
        for key in sensitive_keys:
            if key in self.env_vars:
                encrypted = f.encrypt(self.env_vars[key].encode())
                self.env_vars[key] = f"ENC[{encrypted.decode()}]"
        
        self.save_env()
    
    def decrypt_secrets(self, password: str):
        """Decrypt sensitive values using Fernet"""
        key = base64.urlsafe_b64encode(
            hashlib.sha256(password.encode()).digest()
        )
        f = Fernet(key)
        
        for key, value in self.env_vars.items():
            if value.startswith("ENC[") and value.endswith("]"):
                encrypted = value[4:-1].encode()
                decrypted = f.decrypt(encrypted)
                self.env_vars[key] = decrypted.decode()
        
        self.save_env()
    
    def backup_env(self, backup_dir: str = "config/backups"):
        """Create backup of environment file"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f".env.production.{timestamp}"
        
        with open(backup_file, 'w') as f:
            for key, value in self.env_vars.items():
                if '\n' in str(value):
                    f.write(f'{key}="""\n{value}\n"""\n\n')
                else:
                    f.write(f'{key}={value}\n')
    
    def validate_env(self) -> bool:
        """Validate required environment variables"""
        required_keys = [
            "ADMIN_PRIVATE_KEY",
            "VALIDATOR_PRIVATE_KEY",
            "EXECUTOR_PRIVATE_KEY",
            "ESTABLISHMENT_PRIVATE_KEY",
            "ADMIN_PASSWORD",
            "JWT_SECRET_KEY"
        ]
        
        missing = [key for key in required_keys if not self.env_vars.get(key)]
        if missing:
            print(f"Missing required environment variables: {', '.join(missing)}")
            return False
        return True

def main():
    parser = argparse.ArgumentParser(description="Manage LogiChain environment variables")
    parser.add_argument('--env-file', default=".env.production",
                      help="Environment file to manage")
    parser.add_argument('--action', choices=['encrypt', 'decrypt', 'backup', 'validate'],
                      required=True, help="Action to perform")
    parser.add_argument('--password', help="Password for encryption/decryption")
    parser.add_argument('--backup-dir', default="config/backups",
                      help="Directory for backups")
    
    args = parser.parse_args()
    
    manager = EnvManager(args.env_file)
    
    if args.action == 'encrypt':
        if not args.password:
            print("Password required for encryption")
            sys.exit(1)
        manager.encrypt_secrets(args.password)
        print("Encrypted sensitive values")
    
    elif args.action == 'decrypt':
        if not args.password:
            print("Password required for decryption")
            sys.exit(1)
        manager.decrypt_secrets(args.password)
        print("Decrypted sensitive values")
    
    elif args.action == 'backup':
        manager.backup_env(args.backup_dir)
        print(f"Created backup in {args.backup_dir}")
    
    elif args.action == 'validate':
        if manager.validate_env():
            print("All required environment variables are present")
        else:
            sys.exit(1)

if __name__ == "__main__":
    main() 