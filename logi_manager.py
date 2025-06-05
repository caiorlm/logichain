"""
LogiChain Management System
"""

import os
import json
import sqlite3
import hashlib
import logging
import time
import subprocess
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = "data/blockchain/chain.db"
WALLETS_DIR = "data/wallets"

class LogiManager:
    def __init__(self):
        """Initialize LogiChain manager"""
        self.ensure_directories()
        
    def ensure_directories(self):
        """Ensure required directories exist"""
        os.makedirs(WALLETS_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
    def create_wallet(self) -> Dict:
        """Create a new wallet"""
        # Generate keys
        private_key = hashlib.sha256(os.urandom(32)).hexdigest()
        public_key = hashlib.sha256(private_key.encode()).hexdigest()
        address = "LOGI" + hashlib.sha256(public_key.encode()).hexdigest()[:32]
        
        wallet = {
            'address': address,
            'private_key': private_key,
            'public_key': public_key,
            'balance': 0.0
        }
        
        # Save wallet
        wallet_path = os.path.join(WALLETS_DIR, f'{address}.json')
        with open(wallet_path, 'w') as f:
            json.dump(wallet, f, indent=2)
            
        logger.info(f"Created new wallet: {address}")
        logger.info(f"Wallet saved to: {wallet_path}")
        
        return wallet
        
    def list_wallets(self) -> List[Dict]:
        """List all wallets"""
        wallets = []
        for filename in os.listdir(WALLETS_DIR):
            if filename.endswith('.json'):
                with open(os.path.join(WALLETS_DIR, filename)) as f:
                    wallet = json.load(f)
                    wallets.append(wallet)
        return wallets
        
    def start_mining(self, wallet_address: str):
        """Start mining process"""
        logger.info(f"Starting miner with wallet: {wallet_address}")
        subprocess.Popen(['python', 'simple_miner.py'])
        
    def get_balance(self, address: str) -> float:
        """Get wallet balance"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Get all incoming transactions
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE to_address = ?
            """, (address,))
            incoming = cursor.fetchone()[0] or 0
            
            # Get outgoing transactions
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE from_address = ?
                AND from_address != ?
            """, (address, '0' * 64))
            outgoing = cursor.fetchone()[0] or 0
            
            # Get blocks mined
            cursor.execute("""
                SELECT COUNT(*)
                FROM blocks
                WHERE miner_address = ?
            """, (address,))
            blocks_mined = cursor.fetchone()[0] or 0
            
            # Calculate mining rewards
            mining_rewards = blocks_mined * 50.0  # BLOCK_REWARD
            
            return incoming - outgoing + mining_rewards
            
        finally:
            conn.close()
            
    def send_transaction(self, from_address: str, to_address: str, amount: float):
        """Send LOGI from one wallet to another"""
        # Check balance
        balance = self.get_balance(from_address)
        if balance < amount:
            raise ValueError(f"Insufficient balance: {balance} LOGI")
        
        # Create transaction
        tx = {
            'from_address': from_address,
            'to_address': to_address,
            'amount': amount,
            'timestamp': time.time(),
            'nonce': int(time.time() * 1000)
        }
        
        # Sign transaction
        message = json.dumps(tx, sort_keys=True)
        tx_hash = hashlib.sha256(message.encode()).hexdigest()
        
        # Save to mempool
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO mempool (
                    tx_hash, raw_transaction, timestamp, fee, status
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                tx_hash,
                json.dumps(tx),
                tx['timestamp'],
                0.0,  # fee
                'pending'  # status
            ))
            conn.commit()
            
            logger.info(f"Transaction sent:")
            logger.info(f"From: {from_address}")
            logger.info(f"To: {to_address}")
            logger.info(f"Amount: {amount} LOGI")
            logger.info(f"Hash: {tx_hash}")
            
        finally:
            conn.close()
            
    def recover_wallet(self, address: str) -> Optional[Dict]:
        """Recover wallet from file"""
        wallet_path = os.path.join(WALLETS_DIR, f'{address}.json')
        if os.path.exists(wallet_path):
            with open(wallet_path) as f:
                return json.load(f)
        return None
        
    def get_latest_blocks(self, limit: int = 10) -> List[Dict]:
        """Get latest blocks"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT hash, block_index, timestamp, miner_address, mining_reward
                FROM blocks
                ORDER BY block_index DESC
                LIMIT ?
            """, (limit,))
            
            blocks = []
            for row in cursor.fetchall():
                blocks.append({
                    'hash': row[0],
                    'index': row[1],
                    'timestamp': row[2],
                    'miner': row[3],
                    'reward': row[4]
                })
            return blocks
            
        finally:
            conn.close()
            
    def get_blockchain_stats(self) -> Dict:
        """Get blockchain statistics"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Get total blocks
            cursor.execute("SELECT COUNT(*) FROM blocks")
            total_blocks = cursor.fetchone()[0]
            
            # Get unique wallet addresses
            cursor.execute("""
                SELECT COUNT(DISTINCT address)
                FROM (
                    SELECT miner_address as address FROM blocks
                    UNION
                    SELECT from_address as address FROM transactions
                    UNION
                    SELECT to_address as address FROM transactions
                    WHERE to_address IS NOT NULL
                )
            """)
            total_wallets = cursor.fetchone()[0]
            
            # Get total transactions
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total_transactions = cursor.fetchone()[0]
            
            return {
                'total_blocks': total_blocks,
                'total_wallets': total_wallets,
                'total_transactions': total_transactions
            }
            
        finally:
            conn.close()

def print_menu():
    """Print menu options"""
    print("\n=== LogiChain Manager ===")
    print("1. Create new wallet")
    print("2. List wallets")
    print("3. Start mining")
    print("4. Check wallet balance")
    print("5. Send transaction")
    print("6. Receive (show wallet address)")
    print("7. Recover wallet")
    print("8. Show latest blocks")
    print("9. Show blockchain stats")
    print("0. Exit")
    print("=====================")

def main():
    manager = LogiManager()
    
    while True:
        print_menu()
        choice = input("Enter your choice (0-9): ")
        
        try:
            if choice == "1":
                wallet = manager.create_wallet()
                print(f"Created wallet: {wallet['address']}")
                
            elif choice == "2":
                wallets = manager.list_wallets()
                print("\nWallets:")
                for wallet in wallets:
                    balance = manager.get_balance(wallet['address'])
                    print(f"Address: {wallet['address']}")
                    print(f"Balance: {balance} LOGI\n")
                    
            elif choice == "3":
                address = input("Enter wallet address to mine with: ")
                manager.start_mining(address)
                print("Mining started in background")
                
            elif choice == "4":
                address = input("Enter wallet address: ")
                balance = manager.get_balance(address)
                print(f"Balance: {balance} LOGI")
                
            elif choice == "5":
                from_addr = input("From address: ")
                to_addr = input("To address: ")
                amount = float(input("Amount (LOGI): "))
                manager.send_transaction(from_addr, to_addr, amount)
                print("Transaction sent!")
                
            elif choice == "6":
                address = input("Enter your wallet address: ")
                print(f"Your receiving address: {address}")
                print("Share this address with others to receive LOGI")
                
            elif choice == "7":
                address = input("Enter wallet address to recover: ")
                wallet = manager.recover_wallet(address)
                if wallet:
                    print(f"Recovered wallet: {wallet['address']}")
                    print(f"Private key: {wallet['private_key']}")
                else:
                    print("Wallet not found")
                    
            elif choice == "8":
                blocks = manager.get_latest_blocks(10)
                print("\nLatest blocks:")
                for block in blocks:
                    print(f"Block #{block['index']}")
                    print(f"Hash: {block['hash']}")
                    print(f"Miner: {block['miner']}")
                    print(f"Reward: {block['reward']} LOGI\n")
                    
            elif choice == "9":
                stats = manager.get_blockchain_stats()
                print("\nBlockchain Statistics:")
                print(f"Total blocks: {stats['total_blocks']}")
                print(f"Total wallets: {stats['total_wallets']}")
                print(f"Total transactions: {stats['total_transactions']}")
                
            elif choice == "0":
                print("Goodbye!")
                break
                
            else:
                print("Invalid choice")
                
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")
            
if __name__ == "__main__":
    main() 