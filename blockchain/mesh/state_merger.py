"""
LogiChain State Merger
Handles merging and validating mesh states
"""

import time
from typing import Dict, List, Optional, Set, Tuple
from .snapshot import StateSnapshot, Transaction
from .mesh_history import MeshHistory
from ..crypto.key_manager import KeyManager

class StateMerger:
    """Manages state merging and validation"""
    
    def __init__(
        self,
        node_id: str,
        private_key: str,
        key_manager: KeyManager,
        max_time_drift: int = 300,
        max_depth: int = 1000
    ):
        self.node_id = node_id
        self.private_key = private_key
        self.key_manager = key_manager
        self.mesh_history = MeshHistory(max_depth=max_depth)
        self.max_time_drift = max_time_drift
        self.invalid_states: Set[str] = set()
        
    def validate_state_consistency(
        self,
        state: StateSnapshot,
        current_time: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Validate state consistency"""
        if current_time is None:
            current_time = time.time()
            
        # Skip if previously invalid
        if state.state_hash in self.invalid_states:
            return False, "Previously marked invalid"
            
        # Check timestamps
        if state.timestamp > current_time + self.max_time_drift:
            return False, "Future timestamp"
            
        # Sort and validate transactions
        transactions = sorted(
            state.transactions,
            key=lambda t: t.original_timestamp
        )
        
        # Check transaction order
        prev_time = 0
        seen_hashes = set()
        for tx in transactions:
            # Check timestamp order
            if tx.original_timestamp < prev_time:
                return False, "Invalid transaction order"
            prev_time = tx.original_timestamp
            
            # Check for duplicates
            if tx.tx_hash in seen_hashes:
                return False, "Duplicate transaction"
            seen_hashes.add(tx.tx_hash)
            
            # Validate transaction
            if not tx.validate_complete(self.key_manager, current_time):
                return False, f"Invalid transaction: {tx.tx_hash}"
                
        # Validate state signature
        if not state.verify(self.key_manager.get_node_key(state.node_id)):
            return False, "Invalid state signature"
            
        return True, ""
        
    def merge_states(
        self,
        local_state: StateSnapshot,
        peer_state: StateSnapshot
    ) -> Optional[StateSnapshot]:
        """Merge two states preserving history"""
        current_time = time.time()
        
        # Validate states
        local_valid = self.validate_state_consistency(local_state, current_time)
        if not local_valid[0]:
            return None
            
        peer_valid = self.validate_state_consistency(peer_state, current_time)
        if not peer_valid[0]:
            return None
            
        # Find common ancestor
        common = self.mesh_history.find_common_ancestor(
            local_state.state_hash,
            peer_state.state_hash
        )
        
        # Require common ancestor for non-empty states
        if not common and (local_state.transactions or peer_state.transactions):
            return None
            
        # Get all transactions
        all_txs: Dict[str, Transaction] = {}
        
        # Add local transactions
        for tx in local_state.transactions:
            all_txs[tx.tx_hash] = tx
            
        # Merge peer transactions
        for tx in peer_state.transactions:
            if tx.tx_hash in all_txs:
                # Keep transaction with more hops
                existing = all_txs[tx.tx_hash]
                if len(tx.sync_path) > len(existing.sync_path):
                    all_txs[tx.tx_hash] = tx
            else:
                all_txs[tx.tx_hash] = tx
                
        # Sort by original timestamp
        sorted_txs = sorted(
            all_txs.values(),
            key=lambda t: t.original_timestamp
        )
        
        # Create merged snapshot
        merged = StateSnapshot(
            node_id=self.node_id,
            private_key=self.private_key,
            transactions=sorted_txs
        )
        
        # Add sync hop to all transactions
        for tx in merged.transactions:
            tx.add_sync_hop(self.node_id, self.private_key)
            
        # Add to history
        parent_hashes = [
            local_state.state_hash,
            peer_state.state_hash
        ]
        if not self.mesh_history.add_state(merged, parent_hashes):
            return None
            
        return merged
        
    def validate_dag_consistency(self) -> Tuple[bool, List[str]]:
        """Validate complete DAG consistency"""
        issues = []
        
        # Check for multiple heads with same timestamp
        head_times = {}
        for head in self.mesh_history.heads:
            state = self.mesh_history.states[head]
            t = state.timestamp
            if t in head_times:
                issues.append(f"Multiple heads at timestamp {t}")
            head_times[t] = head
            
        # Check for loops
        visited = set()
        def check_loop(current: str, path: Set[str]) -> bool:
            if current in path:
                issues.append(f"Loop detected at {current}")
                return True
            if current in visited:
                return False
                
            visited.add(current)
            path.add(current)
            
            state = self.mesh_history.states[current]
            for parent in state.parents:
                if check_loop(parent, path):
                    return True
                    
            path.remove(current)
            return False
            
        for head in self.mesh_history.heads:
            check_loop(head, set())
            
        return len(issues) == 0, issues
        
    def generate_signed_snapshot(
        self,
        transactions: List[Transaction]
    ) -> StateSnapshot:
        """Generate new signed snapshot"""
        # Filter valid transactions
        valid_txs = [
            tx for tx in transactions
            if self._validate_transaction_path(tx)
        ]
        
        snapshot = StateSnapshot(
            node_id=self.node_id,
            private_key=self.private_key,
            transactions=sorted(
                valid_txs,
                key=lambda t: t.original_timestamp
            )
        )
        
        # Add to history as new head
        self.mesh_history.add_state(snapshot, [])
        return snapshot 