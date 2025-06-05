"""
Environment configuration loader for LogiChain
"""
import os
from typing import List, Dict, Any
import json

def get_env_str(key: str, default: str = "") -> str:
    """Get string environment variable with default"""
    return os.getenv(key, default)

def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable with default"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_float(key: str, default: float = 0.0) -> float:
    """Get float environment variable with default"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable with default"""
    return str(os.getenv(key, str(default))).lower() in ('true', '1', 'yes')

def get_env_list(key: str, default: List = None) -> List:
    """Get list environment variable with default"""
    try:
        value = os.getenv(key)
        if value:
            return json.loads(value)
        return default or []
    except:
        return default or []

def get_env_dict(key: str, default: Dict = None) -> Dict:
    """Get dictionary environment variable with default"""
    try:
        value = os.getenv(key)
        if value:
            return json.loads(value)
        return default or {}
    except:
        return default or {}

# Network Ports
API_PORT = get_env_int("API_PORT", 5000)
P2P_PORT = get_env_int("P2P_PORT", 30303)
P2P_DISCOVERY_PORT = get_env_int("P2P_DISCOVERY_PORT", 30304)
WEB_PORT = get_env_int("WEB_PORT", 8080)
INTEGRATED_PORT = get_env_int("INTEGRATED_PORT", 8000)
VALIDATOR_PORT = get_env_int("VALIDATOR_PORT", 6000)
EXECUTOR_PORT = get_env_int("EXECUTOR_PORT", 7000)
ESTABLISHMENT_PORT = get_env_int("ESTABLISHMENT_PORT", 8000)

# Network Configuration
P2P_MAX_PEERS = get_env_int("P2P_MAX_PEERS", 50)
P2P_BOOTSTRAP_NODES = get_env_list("P2P_BOOTSTRAP_NODES", [])
API_MAX_CONNECTIONS = get_env_int("API_MAX_CONNECTIONS", 100)
API_RATE_LIMIT = get_env_str("API_RATE_LIMIT", "100/minute")

# Data Directories
DATA_ROOT = get_env_str("DATA_ROOT", "/data")
BLOCKCHAIN_DIR = get_env_str("BLOCKCHAIN_DIR", "/data/blockchain")
CONTRACTS_DIR = get_env_str("CONTRACTS_DIR", "/data/contracts")
LOGS_DIR = get_env_str("LOGS_DIR", "/data/logs")
KEYS_DIR = get_env_str("KEYS_DIR", "/data/keys")
WEB_DIR = get_env_str("WEB_DIR", "/data/web")
STATIC_DIR = get_env_str("STATIC_DIR", "/data/static")
TEMPLATES_DIR = get_env_str("TEMPLATES_DIR", "/data/templates")

# Security Keys
ADMIN_PRIVATE_KEY = get_env_str("ADMIN_PRIVATE_KEY")
VALIDATOR_PRIVATE_KEY = get_env_str("VALIDATOR_PRIVATE_KEY")
EXECUTOR_PRIVATE_KEY = get_env_str("EXECUTOR_PRIVATE_KEY")
ESTABLISHMENT_PRIVATE_KEY = get_env_str("ESTABLISHMENT_PRIVATE_KEY")

# Admin Credentials
ADMIN_USERNAME = get_env_str("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = get_env_str("ADMIN_PASSWORD")
ADMIN_EMAIL = get_env_str("ADMIN_EMAIL", "admin@logichain.local")

# JWT Configuration
JWT_SECRET_KEY = get_env_str("JWT_SECRET_KEY")
JWT_EXPIRATION_HOURS = get_env_int("JWT_EXPIRATION_HOURS", 24)
JWT_ALGORITHM = get_env_str("JWT_ALGORITHM", "HS256")

# Database Configuration
DB_TYPE = get_env_str("DB_TYPE", "sqlite")
DB_PATH = get_env_str("DB_PATH", "/data/blockchain/chain.db")
DB_BACKUP_PATH = get_env_str("DB_BACKUP_PATH", "/data/backups")

# Blockchain Configuration
CHAIN_ID = get_env_int("CHAIN_ID", 1337)
NETWORK_ID = get_env_int("NETWORK_ID", 1)
NETWORK_NAME = get_env_str("NETWORK_NAME", "LogiChain_Mainnet")
GENESIS_BLOCK_HASH = get_env_str("GENESIS_BLOCK_HASH", "0" * 64)

# Mining/Validation
BLOCK_TIME = get_env_int("BLOCK_TIME", 600)
DIFFICULTY = get_env_int("DIFFICULTY", 4)
MIN_STAKE_AMOUNT = get_env_float("MIN_STAKE_AMOUNT", 1000.0)
MAX_BLOCK_SIZE = get_env_int("MAX_BLOCK_SIZE", 1048576)  # 1MB
MAX_CONTRACT_SIZE = get_env_int("MAX_CONTRACT_SIZE", 102400)  # 100KB

# Reputation System
MIN_REPUTATION_SCORE = get_env_float("MIN_REPUTATION_SCORE", 0.7)
REPUTATION_UPDATE_INTERVAL = get_env_int("REPUTATION_UPDATE_INTERVAL", 3600)
MAX_PENALTY_POINTS = get_env_int("MAX_PENALTY_POINTS", 100)

# Security Settings
SSL_ENABLED = get_env_bool("SSL_ENABLED", True)
SSL_CERT_PATH = get_env_str("SSL_CERT_PATH", "/data/ssl/cert.pem")
SSL_KEY_PATH = get_env_str("SSL_KEY_PATH", "/data/ssl/key.pem")
ALLOWED_HOSTS = get_env_list("ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CORS_ORIGINS = get_env_list("CORS_ORIGINS", ["http://localhost:8080"])

# Logging Configuration
LOG_LEVEL = get_env_str("LOG_LEVEL", "INFO")
LOG_FORMAT = get_env_str("LOG_FORMAT", "json")
LOG_MAX_SIZE = get_env_int("LOG_MAX_SIZE", 10485760)  # 10MB
LOG_BACKUP_COUNT = get_env_int("LOG_BACKUP_COUNT", 3)
LOG_PATH = get_env_str("LOG_PATH", "/data/logs")

# Cache Configuration
CACHE_ENABLED = get_env_bool("CACHE_ENABLED", True)
CACHE_TYPE = get_env_str("CACHE_TYPE", "redis")
CACHE_URL = get_env_str("CACHE_URL", "redis://localhost:6379/0")
CACHE_TTL = get_env_int("CACHE_TTL", 3600)

# Monitoring
PROMETHEUS_ENABLED = get_env_bool("PROMETHEUS_ENABLED", True)
PROMETHEUS_PORT = get_env_int("PROMETHEUS_PORT", 9090)
GRAFANA_ENABLED = get_env_bool("GRAFANA_ENABLED", True)
GRAFANA_PORT = get_env_int("GRAFANA_PORT", 3000)

# Feature Flags
OFFLINE_MODE = get_env_bool("OFFLINE_MODE", True)
DEBUG_MODE = get_env_bool("DEBUG_MODE", False)
MAINTENANCE_MODE = get_env_bool("MAINTENANCE_MODE", False)
ENABLE_METRICS = get_env_bool("ENABLE_METRICS", True)

# Rate Limiting
RATE_LIMIT_ENABLED = get_env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_REQUESTS = get_env_int("RATE_LIMIT_REQUESTS", 100)
RATE_LIMIT_WINDOW = get_env_int("RATE_LIMIT_WINDOW", 60)

# Node Identity
NODE_ID = get_env_str("NODE_ID", "mainnet_node_01")
NODE_TYPE = get_env_str("NODE_TYPE", "validator")
NODE_REGION = get_env_str("NODE_REGION", "us-east-1")

# Contract Settings
MAX_CONTRACT_DURATION = get_env_int("MAX_CONTRACT_DURATION", 2592000)  # 30 days
MIN_CONTRACT_VALUE = get_env_float("MIN_CONTRACT_VALUE", 10.0)
CONTRACT_FEE_PERCENT = get_env_float("CONTRACT_FEE_PERCENT", 1.5)

# P2P Network
P2P_PROTOCOL_VERSION = get_env_int("P2P_PROTOCOL_VERSION", 1)
P2P_NETWORK_ID = get_env_int("P2P_NETWORK_ID", 1)
P2P_CLIENT_NAME = get_env_str("P2P_CLIENT_NAME", "LogiChain/1.0.0")
P2P_CAPABILITIES = get_env_list("P2P_CAPABILITIES", ["chain/1.0", "contracts/1.0", "pod/1.0"])

# API Documentation
API_DOCS_ENABLED = get_env_bool("API_DOCS_ENABLED", True)
API_VERSION = get_env_str("API_VERSION", "v1")
API_TITLE = get_env_str("API_TITLE", "LogiChain API")
API_DESCRIPTION = get_env_str("API_DESCRIPTION", "LogiChain Blockchain API for Logistics")

# Backup Configuration
BACKUP_ENABLED = get_env_bool("BACKUP_ENABLED", True)
BACKUP_INTERVAL = get_env_int("BACKUP_INTERVAL", 86400)  # 24 hours
BACKUP_RETENTION_DAYS = get_env_int("BACKUP_RETENTION_DAYS", 30)
BACKUP_COMPRESSION = get_env_bool("BACKUP_COMPRESSION", True)

# Security Validation
def validate_security_settings():
    """Validate critical security settings"""
    required_keys = [
        "ADMIN_PRIVATE_KEY",
        "VALIDATOR_PRIVATE_KEY",
        "EXECUTOR_PRIVATE_KEY",
        "ESTABLISHMENT_PRIVATE_KEY",
        "ADMIN_PASSWORD",
        "JWT_SECRET_KEY"
    ]
    
    missing_keys = [key for key in required_keys if not globals().get(key)]
    if missing_keys:
        raise ValueError(f"Missing required security settings: {', '.join(missing_keys)}")

# Path Validation
def validate_paths():
    """Validate critical paths exist"""
    required_paths = [
        DATA_ROOT,
        BLOCKCHAIN_DIR,
        CONTRACTS_DIR,
        LOGS_DIR,
        KEYS_DIR
    ]
    
    for path in required_paths:
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Failed to create required path {path}: {str(e)}")

def initialize():
    """Initialize and validate all settings"""
    validate_security_settings()
    validate_paths() 