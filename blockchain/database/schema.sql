-- Esquema do banco de dados da blockchain

-- Tabela de blocos
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    block_index INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    previous_hash TEXT NOT NULL,
    difficulty INTEGER NOT NULL DEFAULT 4,
    nonce INTEGER NOT NULL DEFAULT 0,
    miner_address TEXT,
    mining_reward REAL DEFAULT 50.0,
    merkle_root TEXT,
    version INTEGER DEFAULT 1,
    state TEXT DEFAULT 'confirmed',
    total_transactions INTEGER DEFAULT 0,
    size_bytes INTEGER DEFAULT 0,
    UNIQUE(block_index)
);

-- Tabela de transações
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT UNIQUE NOT NULL,
    block_hash TEXT NOT NULL,
    tx_type TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT,
    amount REAL NOT NULL DEFAULT 0.0,
    timestamp REAL NOT NULL,
    nonce INTEGER NOT NULL DEFAULT 0,
    signature TEXT,
    data TEXT,
    status TEXT DEFAULT 'confirmed',
    fee REAL DEFAULT 0.0,
    FOREIGN KEY (block_hash) REFERENCES blocks(hash)
);

-- Tabela de carteiras
CREATE TABLE IF NOT EXISTS wallets (
    address TEXT PRIMARY KEY,
    public_key TEXT NOT NULL,
    encrypted_private_key TEXT,
    mnemonic TEXT,
    balance REAL NOT NULL DEFAULT 0.0,
    nonce INTEGER NOT NULL DEFAULT 0,
    last_updated REAL NOT NULL,
    status TEXT DEFAULT 'active',
    created_at REAL NOT NULL
);

-- Tabela de mempool
CREATE TABLE IF NOT EXISTS mempool (
    tx_hash TEXT PRIMARY KEY,
    raw_transaction TEXT NOT NULL,
    timestamp REAL NOT NULL,
    fee REAL DEFAULT 0.0,
    status TEXT DEFAULT 'pending'
);

-- Tabela de peers
CREATE TABLE IF NOT EXISTS peers (
    address TEXT PRIMARY KEY,
    port INTEGER NOT NULL,
    last_seen REAL NOT NULL,
    reputation INTEGER DEFAULT 0,
    version TEXT,
    capabilities TEXT
);

-- Índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash);
CREATE INDEX IF NOT EXISTS idx_blocks_index ON blocks(block_index);
CREATE INDEX IF NOT EXISTS idx_blocks_miner ON blocks(miner_address);
CREATE INDEX IF NOT EXISTS idx_blocks_time ON blocks(timestamp);

CREATE INDEX IF NOT EXISTS idx_transactions_hash ON transactions(tx_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_block ON transactions(block_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_address);
CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_address);
CREATE INDEX IF NOT EXISTS idx_transactions_time ON transactions(timestamp);

CREATE INDEX IF NOT EXISTS idx_wallets_balance ON wallets(balance);
CREATE INDEX IF NOT EXISTS idx_wallets_status ON wallets(status);

CREATE INDEX IF NOT EXISTS idx_mempool_time ON mempool(timestamp);
CREATE INDEX IF NOT EXISTS idx_mempool_status ON mempool(status);

CREATE INDEX IF NOT EXISTS idx_peers_last_seen ON peers(last_seen);
CREATE INDEX IF NOT EXISTS idx_peers_reputation ON peers(reputation); 