"""
P2P Network Configuration
"""

# Network settings
DEFAULT_PORT = 8333
BOOTSTRAP_NODES = [
    ("localhost", 8333),
    ("localhost", 8334),
    ("localhost", 8335)
]

# Protocol settings
PROTOCOL_VERSION = "1.0.0"
MAX_PEERS = 10
PING_INTERVAL = 30  # seconds
SYNC_INTERVAL = 60  # seconds
MAX_BLOCK_SIZE = 1024 * 1024  # 1MB
MAX_TRANSACTIONS_PER_BLOCK = 1000

# Database settings
DB_PATH = "data/blockchain/chain.db"
BLOCKS_FILE = "data/blockchain/blocks.json"
WALLETS_DIR = "data/wallets"

# Mining settings
MINING_DIFFICULTY = 4
BLOCK_REWARD = 50.0
TARGET_BLOCK_TIME = 60  # seconds

# Security settings
MIN_PEERS_FOR_CONSENSUS = 3
REQUIRED_CONFIRMATIONS = 6

# Wallet settings
WALLET_FILE_FORMAT = "wallet_{address}.json"
DEFAULT_FEE = 0.001 