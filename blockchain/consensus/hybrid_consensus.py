"""
Hybrid consensus implementation combining PoW and BFT
"""

import logging
from typing import Optional
from datetime import datetime
from ..core.block import Block
from ..core.transaction import Transaction
from .pow_consensus import PoWConsensus
from .bft_consensus import BFTConsensus

logger = logging.getLogger(__name__)

class HybridConsensus:
    """Hybrid consensus implementation"""
    
    def __init__(
        self,
        node_id: str = "main-node",
        min_validators: int = 4,
        pow_difficulty: int = 4
    ):
        self.node_id = node_id
        self.pow = PoWConsensus(difficulty=pow_difficulty)
        self.bft = BFTConsensus(node_id=node_id, min_validators=min_validators)
        
        logger.info(
            f"Hybrid Consensus initialized with node_id: {node_id}, "
            f"min_validators: {min_validators} and pow_difficulty: {pow_difficulty}"
        )
        
    def validate_block(self, block: Block) -> bool:
        """Validate a block using both PoW and BFT"""
        # First validate PoW
        if not self.pow.validate_block(block):
            return False
            
        # Then validate BFT
        if not self.bft.validate_block(block):
            return False
            
        return True
        
    def mine_block(self, transactions: list[Transaction]) -> Optional[Block]:
        """Mine a new block"""
        try:
            # Create block
            block = Block(
                prev_hash=self.pow.latest_hash,
                timestamp=datetime.utcnow(),
                nonce=0,
                difficulty=self.pow.difficulty,
                transactions=transactions
            )
            
            # Mine block with PoW
            mined_block = self.pow.mine_block(block)
            if not mined_block:
                return None
                
            # Get BFT consensus
            if not self.bft.add_block(mined_block):
                return None
                
            return mined_block
            
        except Exception as e:
            logger.error(f"Mining error: {e}")
            return None 