#!/usr/bin/env python3
"""
Script to initialize environment for LogiChain
"""
import os
import sys
import argparse
from pathlib import Path
import subprocess
import secrets
import base64
from typing import Dict, Any
import json
import hashlib
from datetime import datetime

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("Python 3.8 or higher is required")
        sys.exit(1)

def check_dependencies():
    """Check if required system dependencies are installed"""
    required = ['openssl', 'python3', 'pip3']
    missing = []
    
    for cmd in required:
        try:
            subprocess.run([cmd, '--version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
        except FileNotFoundError:
            missing.append(cmd)
    
    if missing:
        print(f"Missing required dependencies: {', '.join(missing)}")
        sys.exit(1)

def create_directory_structure():
    """Create required directory structure"""
    directories = [
        "config",
        "config/backups",
        "data",
        "data/blockchain",
        "data/contracts",
        "data/logs",
        "data/keys",
        "data/web",
        "data/ssl",
        "data/static",
        "data/templates",
        "data/backups"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

def generate_ssl_certificates():
    """Generate SSL certificates for HTTPS"""
    ssl_dir = Path("data/ssl")
    key_path = ssl_dir / "key.pem"
    cert_path = ssl_dir / "cert.pem"
    
    if not key_path.exists() or not cert_path.exists():
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:4096",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "365",
            "-nodes",
            "-subj", "/C=BR/ST=SP/L=Sao Paulo/O=LogiChain/CN=localhost"
        ])
        print("Generated SSL certificates")

def install_python_dependencies():
    """Install required Python packages"""
    requirements = [
        "cryptography>=3.4.7",
        "python-dotenv>=0.19.0",
        "pycryptodome>=3.10.1",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "aiohttp>=3.8.0",
        "sqlalchemy>=1.4.23",
        "pydantic>=1.8.2",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "aioredis>=2.0.0",
        "prometheus-client>=0.11.0",
        "structlog>=21.1.0"
    ]
    
    with open("requirements.txt", "w") as f:
        for req in requirements:
            f.write(f"{req}\n")
    
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "-r", "requirements.txt"
    ])
    print("Installed Python dependencies")

def setup_environment():
    """Run environment setup scripts"""
    scripts = [
        ("scripts/generate_env.py", "Generate environment variables"),
        ("scripts/manage_env.py", "Setup environment manager"),
    ]
    
    for script, description in scripts:
        if Path(script).exists():
            print(f"Running: {description}")
            subprocess.run([sys.executable, script])

def create_env_template():
    """Create template for environment variables"""
    template = {
        "# Network Ports": {
            "API_PORT": "5000",
            "P2P_PORT": "30303",
            "P2P_DISCOVERY_PORT": "30304",
            "WEB_PORT": "8080",
            "INTEGRATED_PORT": "8000",
            "VALIDATOR_PORT": "6000",
            "EXECUTOR_PORT": "7000",
            "ESTABLISHMENT_PORT": "8000"
        },
        "# Network Configuration": {
            "P2P_MAX_PEERS": "50",
            "P2P_BOOTSTRAP_NODES": "[]",
            "API_MAX_CONNECTIONS": "100",
            "API_RATE_LIMIT": "100/minute"
        },
        "# Data Directories": {
            "DATA_ROOT": "/data",
            "BLOCKCHAIN_DIR": "/data/blockchain",
            "CONTRACTS_DIR": "/data/contracts",
            "LOGS_DIR": "/data/logs",
            "KEYS_DIR": "/data/keys",
            "WEB_DIR": "/data/web",
            "STATIC_DIR": "/data/static",
            "TEMPLATES_DIR": "/data/templates"
        }
    }
    
    with open("config/.env.template", "w") as f:
        for section, variables in template.items():
            f.write(f"{section}\n")
            for key, value in variables.items():
                f.write(f"{key}={value}\n")
            f.write("\n")
    
    print("Created environment template")

def main():
    parser = argparse.ArgumentParser(description="Initialize LogiChain environment")
    parser.add_argument('--force', action='store_true',
                      help="Force initialization even if already initialized")
    parser.add_argument('--skip-deps', action='store_true',
                      help="Skip installing dependencies")
    parser.add_argument('--skip-ssl', action='store_true',
                      help="Skip generating SSL certificates")
    
    args = parser.parse_args()
    
    # Check if already initialized
    if Path("config/.initialized").exists() and not args.force:
        print("Environment already initialized. Use --force to reinitialize.")
        sys.exit(0)
    
    print("Initializing LogiChain environment...")
    
    # Run checks
    check_python_version()
    if not args.skip_deps:
        check_dependencies()
    
    # Create directory structure
    create_directory_structure()
    
    # Generate SSL certificates
    if not args.skip_ssl:
        generate_ssl_certificates()
    
    # Install Python dependencies
    if not args.skip_deps:
        install_python_dependencies()
    
    # Create environment template
    create_env_template()
    
    # Setup environment
    setup_environment()
    
    # Mark as initialized
    Path("config/.initialized").touch()
    
    print("\nEnvironment initialization complete!")
    print("\nNext steps:")
    print("1. Review and edit config/.env.production")
    print("2. Generate secure keys using scripts/generate_env.py")
    print("3. Start the system using docker-compose up")

if __name__ == "__main__":
    main() 