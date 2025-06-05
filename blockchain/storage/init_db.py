"""
Database initialization
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create base class for declarative models
Base = declarative_base()

def init_db(db_url: str = 'sqlite:///blockchain.db'):
    """Initialize database"""
    # Create engine
    engine = create_engine(db_url)
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create session factory
    Session = sessionmaker(bind=engine)
    
    return engine, Session

# Export base for models
__all__ = ['Base', 'init_db'] 