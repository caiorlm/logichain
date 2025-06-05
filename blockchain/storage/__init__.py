"""
Storage initialization module
"""

import os
from pathlib import Path
from .chaindb import ChainDB

# Default data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data/blockchain")

# Initialize storage
def init_storage():
    """Initialize blockchain storage"""
    return ChainDB(DATA_DIR)

# Get storage instance
def get_storage():
    """Get blockchain storage instance"""
    return init_storage() 