"""
Implementação do consenso Proof of Work
"""

import time
import logging
from typing import Optional, List
from datetime import datetime
from ..core.block import Block
from ..core.transaction import Transaction
from ..network.config import MINING_DIFFICULTY, BLOCK_REWARD

logger = logging.getLogger(__name__)

class PoWConsensus:
    """Implementação do consenso Proof of Work"""
    
    def __init__(self, difficulty: int = MINING_DIFFICULTY):
        self.difficulty = difficulty
        self.target = '0' * difficulty
        self.latest_hash = self._create_genesis_block().hash
        
    def _create_genesis_block(self) -> Block:
        """Cria o bloco genesis"""
        genesis_tx = {
            'tx_id': 'genesis',
            'tx_type': 'genesis',
            'from_address': '0' * 40,
            'to_address': '0' * 40,
            'amount': 0,
            'timestamp': 0,
            'data': {'message': 'Bloco Genesis da LogiChain'}
        }
        
        return Block(
            index=0,
            timestamp=0,
            transactions=[genesis_tx],
            previous_hash='0' * 64,
            difficulty=self.difficulty,
            nonce=0,
            miner_address='0' * 40,
            mining_reward=0.0
        )
    
    def mine_block(self, block: Block) -> bool:
        """Minera um bloco usando Proof of Work"""
        target = '0' * self.difficulty
        
        while block.hash[:self.difficulty] != target:
            block.nonce += 1
            block.hash = block.calculate_hash()
            
        return True
    
    def validate_block(self, block: Block, previous_block: Block) -> bool:
        """Valida um bloco"""
        # Verifica hash do bloco anterior
        if block.previous_hash != previous_block.hash:
            return False
            
        # Verifica se o hash atende à dificuldade
        if block.hash[:self.difficulty] != '0' * self.difficulty:
            return False
            
        # Verifica se o hash está correto
        if block.hash != block.calculate_hash():
            return False
            
        return True
    
    def get_difficulty(self) -> int:
        """Retorna a dificuldade atual"""
        return self.difficulty
    
    def adjust_difficulty(self, blocks: List[Block], target_time: int = 10) -> None:
        """Ajusta a dificuldade com base no tempo médio de mineração"""
        if len(blocks) < 2:
            return
            
        # Calcula tempo médio dos últimos blocos
        times = []
        for i in range(1, len(blocks)):
            time_diff = blocks[i].timestamp - blocks[i-1].timestamp
            times.append(time_diff)
            
        avg_time = sum(times) / len(times)
        
        # Ajusta dificuldade
        if avg_time < target_time:
            self.difficulty += 1
        elif avg_time > target_time:
            self.difficulty = max(1, self.difficulty - 1)
            
        logger.info(f"Dificuldade ajustada para {self.difficulty} (tempo médio: {avg_time:.2f}s)")

    def validate_transaction(self, transaction: Transaction) -> bool:
        """Validate a transaction"""
        try:
            # Skip validation for mining rewards
            if transaction.from_address == '0' * 64:
                return True
                
            # Verify transaction hash
            calculated_hash = transaction.calculate_hash()
            if calculated_hash != transaction.hash:
                logger.warning(f"Transaction {transaction.hash} has invalid hash")
                return False
                
            # Additional validation rules can be added here
            # - Check if sender has sufficient balance
            # - Verify transaction signature
            # - Check for double spending
            
            return True
            
        except Exception as e:
            logger.error(f"Transaction validation error: {e}")
            return False
            
    def validate_chain(self, blocks: List[Block]) -> bool:
        """Validate the entire blockchain"""
        try:
            for i in range(1, len(blocks)):
                current_block = blocks[i]
                previous_block = blocks[i-1]
                
                # Check block link
                if current_block.previous_hash != previous_block.hash:
                    logger.warning(f"Invalid block link at height {i}")
                    return False
                    
                # Validate current block
                if not self.validate_block(current_block, previous_block):
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Chain validation error: {e}")
            return False
        
    def mine_block(self, block: Block) -> Optional[Block]:
        """Mine a block"""
        try:
            # Set previous hash
            block.prev_hash = self.latest_hash
            
            # Mine block
            mining_time = block.mine_block()
            
            # Update latest hash
            self.latest_hash = block.hash
            
            logger.info(f"Block mined in {mining_time:.2f}s")
            return block
            
        except Exception as e:
            logger.error(f"Mining error: {e}")
            return None 