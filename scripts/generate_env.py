#!/usr/bin/env python3
"""
Script to generate secure .env.production file for LogiChain
"""
import os
import secrets
import base64
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

def generate_private_key() -> str:
    """Generate a new RSA private key and return PEM string"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    return pem.decode('utf-8')

def generate_strong_password(length: int = 32) -> str:
    """Generate a cryptographically secure password"""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_jwt_secret() -> str:
    """Generate a secure JWT secret key"""
    return base64.b64encode(secrets.token_bytes(32)).decode('utf-8')

def main():
    # Create output directory if it doesn't exist
    output_dir = Path("config")
    output_dir.mkdir(exist_ok=True)
    
    # Generate secure values
    env_vars = {
        # Security Keys
        "ADMIN_PRIVATE_KEY": generate_private_key(),
        "VALIDATOR_PRIVATE_KEY": generate_private_key(),
        "EXECUTOR_PRIVATE_KEY": generate_private_key(),
        "ESTABLISHMENT_PRIVATE_KEY": generate_private_key(),
        
        # Admin Credentials
        "ADMIN_PASSWORD": generate_strong_password(32),
        
        # JWT Configuration
        "JWT_SECRET_KEY": generate_jwt_secret(),
        
        # Network Ports (using default values)
        "API_PORT": "5000",
        "P2P_PORT": "30303",
        "P2P_DISCOVERY_PORT": "30304",
        "WEB_PORT": "8080",
        "INTEGRATED_PORT": "8000",
        "VALIDATOR_PORT": "6000",
        "EXECUTOR_PORT": "7000",
        "ESTABLISHMENT_PORT": "8000",
        
        # Data Directories
        "DATA_ROOT": "/data",
        "BLOCKCHAIN_DIR": "/data/blockchain",
        "CONTRACTS_DIR": "/data/contracts",
        "LOGS_DIR": "/data/logs",
        "KEYS_DIR": "/data/keys",
        "WEB_DIR": "/data/web",
        "STATIC_DIR": "/data/static",
        "TEMPLATES_DIR": "/data/templates",
        
        # Network Configuration
        "P2P_MAX_PEERS": "50",
        "P2P_BOOTSTRAP_NODES": "[]",
        "API_MAX_CONNECTIONS": "100",
        "API_RATE_LIMIT": "100/minute",
        
        # Database Configuration
        "DB_TYPE": "sqlite",
        "DB_PATH": "/data/blockchain/chain.db",
        "DB_BACKUP_PATH": "/data/backups",
        
        # Blockchain Configuration
        "CHAIN_ID": "1337",
        "NETWORK_ID": "1",
        "NETWORK_NAME": "LogiChain_Mainnet",
        "GENESIS_BLOCK_HASH": "0" * 64,
        
        # Mining/Validation
        "BLOCK_TIME": "600",
        "DIFFICULTY": "4",
        "MIN_STAKE_AMOUNT": "1000.0",
        "MAX_BLOCK_SIZE": "1048576",
        "MAX_CONTRACT_SIZE": "102400",
        
        # Security Settings
        "SSL_ENABLED": "true",
        "SSL_CERT_PATH": "/data/ssl/cert.pem",
        "SSL_KEY_PATH": "/data/ssl/key.pem",
        "ALLOWED_HOSTS": '["127.0.0.1", "localhost"]',
        "CORS_ORIGINS": '["http://localhost:8080"]',
        
        # Feature Flags
        "OFFLINE_MODE": "true",
        "DEBUG_MODE": "false",
        "MAINTENANCE_MODE": "false",
        "ENABLE_METRICS": "true",
        
        # Node Identity
        "NODE_ID": "mainnet_node_01",
        "NODE_TYPE": "validator",
        "NODE_REGION": "us-east-1"
    }
    
    # Write to .env.production
    with open(output_dir / ".env.production", "w") as f:
        for key, value in env_vars.items():
            if isinstance(value, str) and "\n" in value:
                # Handle multiline values (like private keys)
                f.write(f'{key}="""\n{value}\n"""\n\n')
            else:
                f.write(f'{key}={value}\n')
    
    print("Generated .env.production with secure values")
    print("\nIMPORTANT: Keep this file secure and never commit it to version control!")
    print("Make sure to backup the private keys and credentials securely.")

if __name__ == "__main__":
    main() 