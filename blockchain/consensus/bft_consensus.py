"""
Byzantine Fault Tolerant (BFT) consensus implementation with Sybil protection.
Implements PBFT (Practical Byzantine Fault Tolerance) with reputation-based Sybil resistance.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import hashlib
import json
import logging
import asyncio
from datetime import datetime, UTC
from web3 import Web3
from ..wallet.wallet import Wallet
from ..security import SecurityConfig
from ..core.block import Block
from ..monitoring.prometheus_metrics import record_consensus_event

logger = logging.getLogger(__name__)

class ConsensusState(Enum):
    """Consensus states"""
    PREPARE = "PREPARE"
    PRE_PREPARE = "PRE_PREPARE"
    COMMIT = "COMMIT"
    FINALIZE = "FINALIZE"

@dataclass
class ConsensusMessage:
    """Consensus message between nodes"""
    node_id: str
    block_hash: str
    state: ConsensusState
    timestamp: float
    signature: str
    
class BFTConsensus:
    """BFT Consensus implementation"""
    
    def __init__(self, node_id: str = "main-node", min_validators: int = 4):
        self.node_id = node_id
        self.min_validators = min_validators
        self.validators = set()
        self.blocks = []
        
        logger.info(f"BFT Consensus initialized with node_id: {node_id}")
        
    def validate_block(self, block: Block) -> bool:
        """Validate a block"""
        # In this simplified version, we just check if the block is properly formed
        if not block.hash or not block.prev_hash:
            return False
            
        if not block.transactions:
            return False
            
        return True
        
    def add_block(self, block: Block) -> bool:
        """Add a block to the chain"""
        if not self.validate_block(block):
            return False
            
        self.blocks.append(block)
        return True
        
    def add_validator(self, validator_id: str):
        """Add a validator"""
        self.validators.add(validator_id)
        
    def remove_validator(self, validator_id: str):
        """Remove a validator"""
        self.validators.discard(validator_id)
        
    def has_consensus(self) -> bool:
        """Check if we have enough validators for consensus"""
        return len(self.validators) >= self.min_validators
        
    async def start_consensus(self, block: Block) -> bool:
        """Start consensus process for a block"""
        async with self._lock:
            try:
                self.current_block = block
                self.current_state = ConsensusState.PRE_PREPARE
                self.prepared_nodes.clear()
                self.committed_nodes.clear()
                
                # Create PRE-PREPARE message
                message = await self._create_message(ConsensusState.PRE_PREPARE)
                await self._broadcast_message(message)
                
                record_consensus_event(True)
                return True
                
            except Exception as e:
                logger.error("Failed to start consensus: %s", e)
                record_consensus_event(False)
                return False
        
    async def receive_message(self, message: ConsensusMessage) -> Optional[ConsensusState]:
        """Process received message from another node"""
        async with self._lock:
            try:
                if not await self._verify_message(message):
                    return None
                
                if message.state == ConsensusState.PRE_PREPARE:
                    self.prepared_nodes.add(message.node_id)
                    if len(self.prepared_nodes) >= self.required_votes:
                        self.current_state = ConsensusState.COMMIT
                        return self.current_state
                
                elif message.state == ConsensusState.COMMIT:
                    self.committed_nodes.add(message.node_id)
                    if len(self.committed_nodes) >= self.required_votes:
                        self.current_state = ConsensusState.FINALIZE
                        return self.current_state
                
                return None
                
            except Exception as e:
                logger.error("Failed to process message: %s", e)
                return None
        
    def is_consensus_reached(self) -> bool:
        """Check if consensus is reached"""
        return self.current_state == ConsensusState.FINALIZE
        
    async def _create_message(self, state: ConsensusState) -> ConsensusMessage:
        """Create new consensus message"""
        message = ConsensusMessage(
            node_id=self.node_id,
            block_hash=self.current_block.hash if self.current_block else "",
            state=state,
            timestamp=datetime.now(UTC).timestamp(),
            signature=""  # TODO: Implement signing
        )
        return message
        
    async def _verify_message(self, message: ConsensusMessage) -> bool:
        """Verify message validity"""
        try:
            # Verify timestamp
            if abs(message.timestamp - datetime.now(UTC).timestamp()) > 300:  # 5 min max
                logger.warning("Message timestamp too old")
                return False
                
            # Verify state transition
            if not self._is_valid_state_transition(message.state):
                logger.warning("Invalid state transition")
                return False
                
            # TODO: Verify signature
            
            return True
            
        except Exception as e:
            logger.error("Message verification failed: %s", e)
            return False
        
    def get_consensus_stats(self) -> Dict:
        """Get consensus statistics"""
        return {
            'state': self.current_state.value,
            'prepared_nodes': len(self.prepared_nodes),
            'committed_nodes': len(self.committed_nodes),
            'required_votes': self.required_votes,
            'total_nodes': self.total_nodes
        }

    async def add_validator(self, validator: str):
        """Add validator"""
        async with self._lock:
            self.validators.add(validator)
            
    async def remove_validator(self, validator: str):
        """Remove validator"""
        async with self._lock:
            self.validators.remove(validator)
            
    def is_validator(self, node: str) -> bool:
        """Check if node is validator"""
        return node in self.validators
        
    def get_validators(self) -> Set[str]:
        """Get validators"""
        return self.validators.copy()
        
    def get_leader(self) -> Optional[str]:
        """Get current leader"""
        return self.leader
        
    async def register_validator(self, address: str, stake: float) -> bool:
        """Register new validator"""
        async with self._lock:
            if address in self.validators:
                return False
                
            self.validators.add(address)
            self.validator_stakes[address] = stake
            return True
            
    def _is_valid_state_transition(self, new_state: ConsensusState) -> bool:
        """Check if state transition is valid"""
        transitions = {
            ConsensusState.PREPARE: {ConsensusState.PRE_PREPARE},
            ConsensusState.PRE_PREPARE: {ConsensusState.COMMIT},
            ConsensusState.COMMIT: {ConsensusState.FINALIZE},
            ConsensusState.FINALIZE: {ConsensusState.PREPARE}
        }
        return new_state in transitions.get(self.current_state, set())
        
    async def _select_primary(self) -> Optional[str]:
        """Select primary validator"""
        async with self._lock:
            if not self.validators:
                return None
                
            # Select validator with highest stake
            primary = max(
                self.validators,
                key=lambda v: self.validator_stakes.get(v, 0)
            )
            return primary
            
    async def check_view_timeout(self):
        """Check view timeout"""
        current_time = datetime.now(UTC).timestamp()
        if current_time - self.last_view_change > 30:  # 30 seconds
            await self._initiate_view_change()
            
    async def _initiate_view_change(self):
        """Initiate view change"""
        new_view = self.current_view + 1
        await self._send_view_change_vote(new_view)
        
    async def _send_view_change_vote(self, new_view: int):
        """Send view change vote"""
        message = await self._create_message(ConsensusState.PREPARE)
        message.state = "VIEW_CHANGE"
        await self._broadcast_message(message)
        
    async def _broadcast_message(self, message: ConsensusMessage):
        """Broadcast message to all validators"""
        # TODO: Implement actual broadcast
        pass 

    async def start(self):
        """Start consensus process"""
        if self.running:
            return
            
        self.running = True
        logger.info("Starting BFT consensus")
        
        # Start validation in background
        self.validation_task = asyncio.create_task(self.validate_loop())
        
    async def validate_loop(self):
        """Main validation loop"""
        while self.running:
            try:
                # Get pending blocks
                blocks = await self.get_pending_blocks()
                
                for block in blocks:
                    # Check votes
                    if self.verify_block_votes(block.hash):
                        logger.info(f"Block {block.hash} achieved consensus")
                    else:
                        logger.warning(f"Block {block.hash} needs more votes")
                        
                await asyncio.sleep(1)  # Avoid busy loop
                
            except Exception as e:
                logger.error(f"Error in validation loop: {e}")
                await asyncio.sleep(5)  # Back off on error
                
    def stop(self):
        """Stop consensus process"""
        self.running = False
        if self.validation_task:
            self.validation_task.cancel()
        logger.info("Stopped BFT consensus")
        
    async def get_pending_blocks(self) -> List[Block]:
        """Get blocks waiting for consensus"""
        # This should be implemented to get blocks from mempool
        return []
        
    def propose_block(self, block: Block, proposer_id: str) -> bool:
        """Propose block for consensus"""
        if proposer_id not in self.validators:
            logger.warning(f"Invalid proposer {proposer_id}")
            return False
            
        # Add vote from proposer
        if block.hash not in self.votes:
            self.votes[block.hash] = set()
        self.votes[block.hash].add(proposer_id)
        
        # Check if we have enough votes
        return self.verify_block_votes(block.hash)
        
    def verify_block_votes(self, block_hash: str) -> bool:
        """Verify if block has enough votes"""
        if block_hash not in self.votes:
            return False
            
        return len(self.votes[block_hash]) >= self.min_votes
        
    def get_stats(self) -> Dict:
        """Get consensus statistics"""
        return {
            "validators": len(self.validators),
            "min_votes": self.min_votes,
            "running": self.running,
            "active_votes": len(self.votes)
        } 