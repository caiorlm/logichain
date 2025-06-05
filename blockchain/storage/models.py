"""
Modelos do banco de dados da blockchain
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .init_db import Base

class Block(Base):
    __tablename__ = 'blocks'
    
    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True, nullable=False)
    previous_hash = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    nonce = Column(Integer, nullable=False)
    difficulty = Column(Integer, nullable=False)
    miner_address = Column(String, nullable=False)
    consensus_reward = Column(Float, nullable=False)
    transactions = relationship("Transaction", back_populates="block")

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String, unique=True, nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    signature = Column(String, nullable=False)
    block_id = Column(Integer, ForeignKey('blocks.id'))
    block = relationship("Block", back_populates="transactions")
    status = Column(String, nullable=False, default='pending')

class Wallet(Base):
    __tablename__ = 'wallets'
    
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False)
    public_key = Column(String, nullable=False)
    encrypted_private_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    balance = Column(Float, default=0.0)

class Peer(Base):
    __tablename__ = 'peers'
    
    id = Column(Integer, primary_key=True)
    node_id = Column(String, unique=True, nullable=False)
    ip_address = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    reputation = Column(Integer, default=0)
    version = Column(String, nullable=False)

class MiningStats(Base):
    __tablename__ = 'mining_stats'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    blocks_mined = Column(Integer, default=0)
    total_reward = Column(Float, default=0.0)
    hash_rate = Column(Float, nullable=False)
    difficulty = Column(Integer, nullable=False)
    miner_address = Column(String, nullable=False) 