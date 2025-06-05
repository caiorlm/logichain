from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import time
import hashlib
from enum import Enum

class ValidationResult:
    def __init__(self, valid: bool, reason: str = ""):
        self.valid = valid
        self.reason = reason

class NetworkMode(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"

@dataclass
class Transaction:
    tx_id: str
    sender: str
    receiver: str
    amount: float
    timestamp: float
    signature: bytes
    public_key: bytes
    dependencies: List[str]  # List of transaction IDs this tx depends on

@dataclass
class Block:
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: float
    difficulty: int
    nonce: int
    transactions: List[Transaction]
    quorum_sigs: Optional[List[bytes]] = None

@dataclass
class ChainContext:
    difficulty: int
    last_block: Optional[Block]
    current_state: Dict
    trusted_nodes: Set[bytes]
    fork_choice_rule: str
    network_mode: NetworkMode

class EnhancedBlockValidator:
    def __init__(self):
        self.MAX_BLOCK_SIZE_ONLINE = 1024 * 1024  # 1MB
        self.MAX_BLOCK_SIZE_OFFLINE = 1024  # 1KB
        self.MAX_TX_COUNT_ONLINE = 1000
        self.MAX_TX_COUNT_OFFLINE = 10
        self.MAX_TIME_DRIFT = 300  # 5 minutes
        self.MIN_QUORUM_SIGS = 3
        
    def _validate_pow(self, block: Block, difficulty: int) -> bool:
        try:
            # Prepare block header for PoW validation
            header = (
                f"{block.version}{block.previous_hash}{block.merkle_root}"
                f"{block.timestamp}{block.difficulty}{block.nonce}"
            ).encode()
            
            # Calculate block hash
            block_hash = hashlib.sha256(header).hexdigest()
            
            # Check if hash meets difficulty requirement
            target = 2 ** (256 - difficulty)
            block_hash_int = int(block_hash, 16)
            
            return block_hash_int < target
            
        except Exception:
            return False
            
    def _validate_temporal_order(
        self,
        block: Block,
        last_block: Optional[Block]
    ) -> bool:
        current_time = time.time()
        
        # Check if block is from the future
        if block.timestamp > current_time + self.MAX_TIME_DRIFT:
            return False
            
        # Check if block is too old
        if block.timestamp < current_time - self.MAX_TIME_DRIFT:
            return False
            
        # Check order with previous block
        if last_block and block.timestamp <= last_block.timestamp:
            return False
            
        return True
        
    def _validate_merkle_root(self, block: Block) -> bool:
        def calculate_merkle_root(transactions: List[Transaction]) -> str:
            if not transactions:
                return hashlib.sha256(b"").hexdigest()
                
            # Calculate leaf nodes
            leaves = [
                hashlib.sha256(
                    f"{tx.tx_id}{tx.sender}{tx.receiver}{tx.amount}{tx.timestamp}".encode()
                ).hexdigest()
                for tx in transactions
            ]
            
            # Build tree
            while len(leaves) > 1:
                if len(leaves) % 2 == 1:
                    leaves.append(leaves[-1])
                    
                next_level = []
                for i in range(0, len(leaves), 2):
                    combined = leaves[i] + leaves[i+1]
                    next_level.append(
                        hashlib.sha256(combined.encode()).hexdigest()
                    )
                leaves = next_level
                
            return leaves[0]
            
        calculated_root = calculate_merkle_root(block.transactions)
        return calculated_root == block.merkle_root
        
    def _validate_transactions_dag(
        self,
        transactions: List[Transaction]
    ) -> ValidationResult:
        # Build dependency graph
        dependencies = {}
        for tx in transactions:
            dependencies[tx.tx_id] = set(tx.dependencies)
            
        # Check for cycles
        visited = set()
        temp_visited = set()
        
        def has_cycle(tx_id: str) -> bool:
            if tx_id in temp_visited:
                return True
            if tx_id in visited:
                return False
                
            temp_visited.add(tx_id)
            
            for dep in dependencies.get(tx_id, set()):
                if has_cycle(dep):
                    return True
                    
            temp_visited.remove(tx_id)
            visited.add(tx_id)
            return False
            
        # Check each transaction for cycles
        for tx_id in dependencies:
            if has_cycle(tx_id):
                return ValidationResult(
                    valid=False,
                    reason=f"Cycle detected in transaction {tx_id}"
                )
                
        return ValidationResult(valid=True)
        
    def _validate_quorum_signatures(
        self,
        signatures: List[bytes],
        trusted_nodes: Set[bytes]
    ) -> bool:
        if len(signatures) < self.MIN_QUORUM_SIGS:
            return False
            
        valid_sigs = 0
        for sig in signatures:
            if sig in trusted_nodes:
                valid_sigs += 1
                
        return valid_sigs >= self.MIN_QUORUM_SIGS
        
    def _validate_state_transition(
        self,
        block: Block,
        current_state: Dict
    ) -> bool:
        # Create temporary state for validation
        temp_state = current_state.copy()
        
        # Process transactions in order
        for tx in block.transactions:
            # Check sender balance
            if temp_state.get(tx.sender, 0) < tx.amount:
                return False
                
            # Update balances
            temp_state[tx.sender] = temp_state.get(tx.sender, 0) - tx.amount
            temp_state[tx.receiver] = temp_state.get(tx.receiver, 0) + tx.amount
            
        return True
        
    def _detect_fork(
        self,
        block: Block,
        fork_choice_rule: str
    ) -> bool:
        # Implement fork detection based on the chosen rule
        # This is a simplified version - real implementation would be more complex
        if fork_choice_rule == "LONGEST_CHAIN":
            # Check if block builds on the longest chain
            return False
        elif fork_choice_rule == "HEAVIEST_CHAIN":
            # Check if block builds on the chain with most accumulated work
            return False
            
        return True
        
    def validate_block(
        self,
        block: Block,
        chain_context: ChainContext
    ) -> ValidationResult:
        try:
            # 1. Validate block size and transaction count
            total_size = len(str(block).encode())  # Simplified size calculation
            max_size = (
                self.MAX_BLOCK_SIZE_ONLINE
                if chain_context.network_mode == NetworkMode.ONLINE
                else self.MAX_BLOCK_SIZE_OFFLINE
            )
            max_tx_count = (
                self.MAX_TX_COUNT_ONLINE
                if chain_context.network_mode == NetworkMode.ONLINE
                else self.MAX_TX_COUNT_OFFLINE
            )
            
            if total_size > max_size:
                return ValidationResult(
                    valid=False,
                    reason=f"Block size {total_size} exceeds maximum {max_size}"
                )
                
            if len(block.transactions) > max_tx_count:
                return ValidationResult(
                    valid=False,
                    reason=f"Transaction count exceeds maximum {max_tx_count}"
                )
                
            # 2. Validate PoW
            if not self._validate_pow(block, chain_context.difficulty):
                return ValidationResult(
                    valid=False,
                    reason="Invalid proof of work"
                )
                
            # 3. Validate temporal order
            if not self._validate_temporal_order(
                block,
                chain_context.last_block
            ):
                return ValidationResult(
                    valid=False,
                    reason="Invalid temporal order"
                )
                
            # 4. Validate merkle root
            if not self._validate_merkle_root(block):
                return ValidationResult(
                    valid=False,
                    reason="Invalid merkle root"
                )
                
            # 5. Validate transaction DAG
            tx_result = self._validate_transactions_dag(block.transactions)
            if not tx_result.valid:
                return tx_result
                
            # 6. Validate quorum signatures in online mode
            if chain_context.network_mode == NetworkMode.ONLINE:
                if not block.quorum_sigs:
                    return ValidationResult(
                        valid=False,
                        reason="Missing quorum signatures in online mode"
                    )
                    
                if not self._validate_quorum_signatures(
                    block.quorum_sigs,
                    chain_context.trusted_nodes
                ):
                    return ValidationResult(
                        valid=False,
                        reason="Invalid quorum signatures"
                    )
                    
            # 7. Validate state transition
            if not self._validate_state_transition(
                block,
                chain_context.current_state
            ):
                return ValidationResult(
                    valid=False,
                    reason="Invalid state transition"
                )
                
            # 8. Detect forks
            if self._detect_fork(block, chain_context.fork_choice_rule):
                return ValidationResult(
                    valid=False,
                    reason="Fork detected"
                )
                
            return ValidationResult(valid=True)
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                reason=f"Validation error: {str(e)}"
            ) 