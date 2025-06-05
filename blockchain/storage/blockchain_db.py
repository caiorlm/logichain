"""
Blockchain database implementation
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from ..core.block import Block
from ..core.transaction import Transaction

logger = logging.getLogger(__name__)

Base = declarative_base()

class BlockModel(Base):
    """Block database model"""
    __tablename__ = 'blocks'
    
    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True, nullable=False)
    previous_hash = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    nonce = Column(Integer, nullable=False)
    difficulty = Column(Integer, nullable=False)
    transactions = relationship("TransactionModel", back_populates="block", cascade="all, delete-orphan")
    
    @classmethod
    def from_block(cls, block: Block) -> 'BlockModel':
        """Create model from block"""
        block_model = cls(
            hash=block.hash,
            previous_hash=block.prev_hash,
            timestamp=block.timestamp,
            nonce=block.nonce,
            difficulty=block.difficulty
        )
        
        # Create transaction models
        for tx in block.transactions:
            tx_model = TransactionModel.from_transaction(tx)
            tx_model.block = block_model
            block_model.transactions.append(tx_model)
        
        return block_model
        
    def to_block(self) -> Block:
        """Convert to block"""
        block = Block(
            prev_hash=self.previous_hash,
            timestamp=self.timestamp,
            nonce=self.nonce,
            difficulty=self.difficulty,
            transactions=[]
        )
        
        # Add transactions
        block.transactions = [tx.to_transaction() for tx in self.transactions]
        block.hash = self.hash  # Use the stored hash
        
        return block

class TransactionModel(Base):
    """Transaction database model"""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    hash = Column(String, nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    nonce = Column(Integer, nullable=False, default=0)
    block_id = Column(Integer, ForeignKey('blocks.id'))
    block = relationship("BlockModel", back_populates="transactions")
    
    @classmethod
    def from_transaction(cls, transaction: Transaction) -> 'TransactionModel':
        """Create model from transaction"""
        return cls(
            hash=transaction.hash,
            from_address=transaction.from_address,
            to_address=transaction.to_address,
            amount=transaction.amount,
            timestamp=transaction.timestamp,
            nonce=transaction.nonce
        )
        
    def to_transaction(self) -> Transaction:
        """Convert to transaction"""
        tx = Transaction(
            from_address=self.from_address,
            to_address=self.to_address,
            amount=self.amount,
            timestamp=self.timestamp
        )
        tx.nonce = self.nonce
        tx.hash = self.hash
        return tx

class BlockchainDB:
    """Blockchain database interface"""
    
    def __init__(self, db_url: str = 'sqlite:///blockchain.db'):
        """Initialize database"""
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        
    def save_block(self, block: Block) -> bool:
        """Save block to database"""
        try:
            with Session(self.engine) as session:
                # Begin transaction
                session.begin()
                
                try:
                    # Create block model
                    block_model = BlockModel(
                        hash=block.hash,
                        previous_hash=block.prev_hash,
                        timestamp=block.timestamp,
                        nonce=block.nonce,
                        difficulty=block.difficulty
                    )
                    
                    # Add block to session
                    session.add(block_model)
                    session.flush()  # This will assign an ID to the block
                    
                    # Create and add transactions
                    for tx in block.transactions:
                        tx_model = TransactionModel(
                            hash=tx.hash,
                            from_address=tx.from_address,
                            to_address=tx.to_address,
                            amount=tx.amount,
                            timestamp=tx.timestamp,
                            nonce=tx.nonce,
                            block_id=block_model.id  # Use the assigned block ID
                        )
                        session.add(tx_model)
                    
                    # Commit transaction
                    session.commit()
                    logger.info(f"Saved block {block.hash}")
                    return True
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Failed to save block: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Database error: {e}")
            return False
            
    def save_transaction(self, transaction: Transaction) -> bool:
        """Save transaction to database"""
        try:
            with Session(self.engine) as session:
                tx_model = TransactionModel.from_transaction(transaction)
                session.add(tx_model)
                session.commit()
                logger.info(f"Saved transaction {transaction.hash}")
                return True
        except Exception as e:
            logger.error(f"Failed to save transaction: {e}")
            return False
            
    def load_blocks(self) -> List[Block]:
        """Load all blocks from database"""
        try:
            with Session(self.engine) as session:
                blocks = []
                for block_model in session.query(BlockModel).order_by(BlockModel.id):
                    blocks.append(block_model.to_block())
                return blocks
        except Exception as e:
            logger.error(f"Failed to load blocks: {e}")
            return []
            
    def get_block(self, block_hash: str) -> Optional[Block]:
        """Get block by hash"""
        try:
            with Session(self.engine) as session:
                block_model = session.query(BlockModel).filter_by(hash=block_hash).first()
                if block_model:
                    return block_model.to_block()
                return None
        except Exception as e:
            logger.error(f"Failed to get block: {e}")
            return None
            
    def get_transaction(self, tx_hash: str) -> Optional[Transaction]:
        """Get transaction by hash"""
        try:
            with Session(self.engine) as session:
                tx_model = session.query(TransactionModel).filter_by(hash=tx_hash).first()
                if tx_model:
                    return tx_model.to_transaction()
                return None
        except Exception as e:
            logger.error(f"Failed to get transaction: {e}")
            return None
            
    def get_all_blocks(self) -> List[Block]:
        """Get all blocks"""
        try:
            with Session(self.engine) as session:
                blocks = []
                for block_model in session.query(BlockModel).order_by(BlockModel.id):
                    blocks.append(block_model.to_block())
                return blocks
        except Exception as e:
            logger.error(f"Failed to get blocks: {e}")
            return []
            
    def get_pending_transactions(self) -> List[Transaction]:
        """Get pending transactions"""
        try:
            with Session(self.engine) as session:
                transactions = []
                for tx_model in session.query(TransactionModel).filter_by(block_id=None):
                    transactions.append(tx_model.to_transaction())
                return transactions
        except Exception as e:
            logger.error(f"Failed to get pending transactions: {e}")
            return []
            
    def get_address_transactions(self, address: str) -> List[Transaction]:
        """Get transactions for address"""
        try:
            with Session(self.engine) as session:
                transactions = []
                query = session.query(TransactionModel).filter(
                    (TransactionModel.from_address == address) |
                    (TransactionModel.to_address == address)
                )
                for tx_model in query:
                    transactions.append(tx_model.to_transaction())
                return transactions
        except Exception as e:
            logger.error(f"Failed to get address transactions: {e}")
            return [] 