"""
Mining Manager for LogiChain
"""

import sqlite3
import logging
import hashlib
import time
from typing import List, Optional, Dict, Tuple
from models import Block, Transaction
from wallet_manager import WalletManager
from blockchain_validator import BlockchainValidator
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MiningManager:
    """Manages blockchain mining operations with persistence"""
    
    def __init__(self, miner_address: str, difficulty: int = 4):
        self.miner_address = miner_address
        self.difficulty = difficulty
        self.db = DatabaseManager()
        self.wallet_manager = WalletManager()
        self.validator = BlockchainValidator()
        
    def get_connection(self):
        """Get database connection"""
        return self.wallet_manager.get_connection()
        
    def validate_block(self, block: Block) -> Tuple[bool, str]:
        """Validate block before adding to chain"""
        # Verify block integrity
        if not block.is_valid():
            return False, "Bloco inválido"
            
        # Verify block index and previous hash
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT hash 
                FROM blocks 
                WHERE block_index = ?
            """, (block.index - 1,))
            result = cursor.fetchone()
            
            if not result:
                return False, "Bloco anterior não encontrado"
                
            if result[0] != block.previous_hash:
                return False, "Hash anterior inválido"
                
            # Verify miner wallet exists
            cursor.execute("""
                SELECT id 
                FROM wallets 
                WHERE address = ?
            """, (block.miner_address,))
            if not cursor.fetchone():
                return False, "Carteira do minerador não encontrada"
                
            return True, "Bloco válido"
            
        finally:
            cursor.close()
            conn.close()
            
    def check_wallet_balance(self, miner_address: str) -> bool:
        """Check if miner wallet exists and has no negative balance"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT balance 
                FROM wallets 
                WHERE address = ?
            """, (miner_address,))
            result = cursor.fetchone()
            
            if not result:
                return True  # New wallet is ok
                
            return result[0] >= 0
            
        finally:
            cursor.close()
            conn.close()
            
    def validate_pending_transactions(self) -> List[Transaction]:
        """Validate transactions in mempool"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get pending transactions
            cursor.execute("""
                SELECT tx_hash, raw_transaction
                FROM mempool
                WHERE status = 'pending'
                ORDER BY fee DESC, timestamp ASC
            """)
            pending = cursor.fetchall()
            
            valid_transactions = []
            for tx_hash, raw_tx in pending:
                tx_data = eval(raw_tx)  # Convert string to dict
                
                # Create Transaction object
                transaction = Transaction(
                    tx_hash=tx_hash,
                    tx_type='transfer',
                    from_address=tx_data['from_address'],
                    to_address=tx_data['to_address'],
                    amount=float(tx_data['amount']),
                    timestamp=float(tx_data['timestamp']),
                    signature=tx_data.get('signature'),
                    public_key=tx_data.get('public_key')
                )
                
                # Validate transaction
                if Block.verify_transaction_signature(transaction):
                    valid, _ = self.wallet_manager.validate_transaction(
                        transaction.from_address,
                        transaction.amount
                    )
                    if valid:
                        valid_transactions.append(transaction)
                    else:
                        # Mark as rejected
                        cursor.execute("""
                            UPDATE mempool
                            SET status = 'rejected'
                            WHERE tx_hash = ?
                        """, (tx_hash,))
                        
            conn.commit()
            return valid_transactions
            
        finally:
            cursor.close()
            conn.close()
            
    def add_block(self, block: Block) -> bool:
        """Add new block to chain and update miner wallet"""
        # First validate blockchain integrity
        audit = self.validator.audit_blockchain()
        if not audit['success']:
            logger.error("Blockchain validation failed before adding block")
            return False
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Validate block
            is_valid, message = self.validate_block(block)
            if not is_valid:
                logger.error(f"Bloco inválido: {message}")
                return False
                
            # Insert block
            block_data = block.to_dict()
            cursor.execute("""
                INSERT INTO blocks (
                    hash, block_index, timestamp,
                    previous_hash, merkle_root,
                    difficulty, nonce,
                    miner_address, mining_reward
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block_data['hash'],
                block_data['index'],
                block_data['timestamp'],
                block_data['previous_hash'],
                block_data['merkle_root'],
                block_data['difficulty'],
                block_data['nonce'],
                block_data['miner_address'],
                block_data['mining_reward']
            ))
            
            # Insert all transactions
            for tx in block.transactions:
                cursor.execute("""
                    INSERT INTO transactions (
                        tx_hash, block_hash, tx_type,
                        from_address, to_address, amount,
                        timestamp, signature, public_key,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
                """, (
                    tx.tx_hash,
                    block.hash,
                    tx.tx_type,
                    tx.from_address,
                    tx.to_address,
                    tx.amount,
                    tx.timestamp,
                    tx.signature,
                    tx.public_key
                ))
                
                # Update wallet balances
                if tx.tx_type == 'mining_reward':
                    self.wallet_manager.update_miner_wallet(
                        tx.to_address,
                        tx.amount,
                        block.hash
                    )
                else:
                    self.wallet_manager.update_transaction_wallets(
                        tx.from_address,
                        tx.to_address,
                        tx.amount,
                        tx.tx_hash
                    )
                    
                    # Remove from mempool if present
                    cursor.execute("""
                        DELETE FROM mempool
                        WHERE tx_hash = ?
                    """, (tx.tx_hash,))
                    
            conn.commit()
            logger.info(f"Bloco {block.index} adicionado à cadeia")
            
            # Validate blockchain after adding block
            audit = self.validator.audit_blockchain()
            if not audit['success']:
                logger.error("Blockchain validation failed after adding block")
                conn.rollback()
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Erro ao adicionar bloco: {str(e)}")
            conn.rollback()
            return False
            
        finally:
            cursor.close()
            conn.close()
            
    def get_mining_info(self) -> Dict:
        """Get current mining information"""
        # First validate blockchain
        audit = self.validator.audit_blockchain()
        if not audit['success']:
            logger.warning("Blockchain validation failed before mining")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get latest block
            cursor.execute("""
                SELECT block_index, hash
                FROM blocks
                ORDER BY block_index DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()
            
            if not latest:
                return {
                    'next_index': 0,
                    'previous_hash': "0" * 64,
                    'difficulty': self.difficulty,
                    'reward': 50.0
                }
                
            return {
                'next_index': latest[0] + 1,
                'previous_hash': latest[1],
                'difficulty': self.difficulty,
                'reward': 50.0
            }
            
        finally:
            cursor.close()
            conn.close()
            
    def create_mining_reward(self, block_index: int) -> Transaction:
        """Create mining reward transaction with proper persistence"""
        # Fixed reward before first halving
        reward = 50.0 if block_index < 210000 else 50.0 / (2 ** (block_index // 210000))
        
        # Create unique reward transaction
        reward_tx = Transaction(
            tx_hash=f"reward_{block_index}_{int(time.time())}",
            tx_type="mining_reward",
            from_address="0" * 64,  # Coinbase transaction
            to_address=self.miner_address,
            amount=reward,
            timestamp=time.time()
        )
        
        # Ensure reward transaction is saved atomically
        if not self.db.save_transaction_to_mempool(reward_tx):
            logger.error(f"Failed to save mining reward transaction for block {block_index}")
            return None
            
        logger.info(f"Created mining reward: {reward} LOGI for block {block_index}")
        return reward_tx
        
    def mine_block(self) -> Optional[Block]:
        """Mine a new block with pending transactions"""
        try:
            # Get latest block
            latest_block = self.db.get_latest_block()
            if not latest_block:
                logger.info("Creating genesis block...")
                latest_block = Block.create_genesis_block()
                if not self.db.save_block(latest_block, atomic=True):
                    logger.error("Failed to save genesis block")
                    return None
                return latest_block
                
            # Create mining reward first
            reward_tx = self.create_mining_reward(latest_block.index + 1)
            if not reward_tx:
                logger.error("Failed to create mining reward")
                return None
                
            # Get pending transactions
            pending_txs = self.db.get_pending_transactions()
            
            # Create new block
            new_block = Block(
                index=latest_block.index + 1,
                timestamp=time.time(),
                transactions=[reward_tx] + pending_txs,
                previous_hash=latest_block.hash,
                difficulty=self.difficulty,
                miner_address=self.miner_address
            )
            
            # Mine block
            logger.info(f"Mining block {new_block.index}...")
            if not new_block.mine_block(self.difficulty):
                logger.error("Failed to mine block")
                return None
                
            # Save block atomically
            if not self.db.save_block(new_block, atomic=True):
                logger.error(f"Failed to save block {new_block.index}")
                return None
                
            logger.info(f"Successfully mined and saved block {new_block.index}")
            return new_block
            
        except Exception as e:
            logger.error(f"Error in mine_block: {e}")
            return None
            
    def start_mining(self, stop_event=None):
        """Start continuous mining process"""
        while not (stop_event and stop_event.is_set()):
            try:
                # Check if there are enough pending transactions
                pending_count = len(self.db.get_pending_transactions())
                if pending_count < 1:  # Mine even with just reward transaction
                    time.sleep(10)  # Wait for transactions
                    continue
                    
                # Mine block
                new_block = self.mine_block()
                if not new_block:
                    logger.warning("Failed to mine block, retrying...")
                    time.sleep(5)
                    continue
                    
                logger.info(f"Successfully mined block {new_block.index}")
                
            except Exception as e:
                logger.error(f"Mining loop error: {str(e)}")
                time.sleep(5)  # Wait before retrying 