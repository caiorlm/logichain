"""
LogiChain Mesh History
Manages mesh state history with DAG support
"""

import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from .snapshot import StateSnapshot
import json
import hashlib

@dataclass
class MeshStateNode:
    """Node in the mesh state DAG"""
    snapshot: StateSnapshot
    parents: List[str]  # parent state hashes
    children: List[str] # child state hashes
    timestamp: float
    depth: int = 0  # Depth from genesis

class MeshHistory:
    """Manages mesh state history as a DAG"""
    
    def __init__(self, max_depth: int = 1000):
        self.states: Dict[str, MeshStateNode] = {}
        self.heads: Set[str] = set()  # Latest state hashes
        self.max_depth = max_depth
        self.genesis_hash: Optional[str] = None
        
    def add_state(
        self,
        snapshot: StateSnapshot,
        parent_hashes: List[str],
        validate: bool = True
    ) -> Tuple[bool, str]:
        """Add new state to history"""
        # Validate state
        if validate:
            validation = self.validate_new_state(snapshot, parent_hashes)
            if not validation[0]:
                return False, validation[1]
                
        # Create state node
        state_node = MeshStateNode(
            snapshot=snapshot,
            parents=parent_hashes,
            children=[],
            timestamp=time.time()
        )
        
        # Calculate depth
        if parent_hashes:
            state_node.depth = max(
                self.states[p].depth for p in parent_hashes
            ) + 1
            if state_node.depth >= self.max_depth:
                return False, "Max depth exceeded"
        else:
            # Genesis state
            if not self.genesis_hash:
                self.genesis_hash = snapshot.state_hash
            else:
                return False, "Multiple genesis states"
                
        # Check for timestamp conflicts
        for head in self.heads:
            head_state = self.states[head]
            if abs(head_state.timestamp - state_node.timestamp) < 1:
                return False, "Timestamp conflict with existing head"
                
        # Update parent links
        for parent_hash in parent_hashes:
            self.states[parent_hash].children.append(snapshot.state_hash)
            
        # Update heads
        self.heads.difference_update(parent_hashes)
        self.heads.add(snapshot.state_hash)
        
        # Store state
        self.states[snapshot.state_hash] = state_node
        return True, ""
        
    def validate_new_state(
        self,
        snapshot: StateSnapshot,
        parent_hashes: List[str]
    ) -> Tuple[bool, str]:
        """Validate state before adding"""
        # Check parents exist
        for parent_hash in parent_hashes:
            if parent_hash not in self.states:
                return False, f"Parent not found: {parent_hash}"
                
        # Check for loops
        if snapshot.state_hash in self.states:
            return False, "State already exists"
            
        visited = set()
        def check_loop(current: str, path: Set[str]) -> bool:
            if current in path:
                return True
            if current in visited:
                return False
            visited.add(current)
            path.add(current)
            
            if current in self.states:
                for parent in self.states[current].parents:
                    if check_loop(parent, path):
                        return True
            path.remove(current)
            return False
            
        for parent in parent_hashes:
            if check_loop(parent, set()):
                return False, "Loop detected in ancestry"
                
        # Check timestamps
        current_time = time.time()
        if snapshot.timestamp > current_time + 300:  # 5 min drift
            return False, "Future timestamp"
            
        if parent_hashes:
            parent_times = [
                self.states[p].timestamp
                for p in parent_hashes
            ]
            if snapshot.timestamp < max(parent_times):
                return False, "Invalid timestamp order"
                
        return True, ""
        
    def get_ancestry(
        self,
        state_hash: str,
        max_depth: Optional[int] = None
    ) -> List[str]:
        """Get ancestry chain for state"""
        if max_depth is None:
            max_depth = self.max_depth
            
        ancestry = []
        visited = set()
        
        def traverse(current: str, depth: int):
            if depth >= max_depth or current in visited:
                return
            visited.add(current)
            ancestry.append(current)
            if current in self.states:
                for parent in self.states[current].parents:
                    traverse(parent, depth + 1)
                    
        traverse(state_hash, 0)
        return ancestry
        
    def find_common_ancestor(
        self,
        hash_a: str,
        hash_b: str
    ) -> Optional[str]:
        """Find most recent common ancestor of two states"""
        if hash_a not in self.states or hash_b not in self.states:
            return None
            
        # Get ancestries with depth limit
        ancestry_a = set(self.get_ancestry(hash_a))
        ancestry_b = set(self.get_ancestry(hash_b))
        
        # Find common ancestors
        common = ancestry_a.intersection(ancestry_b)
        if not common:
            return None
            
        # Return most recent
        return max(
            common,
            key=lambda h: self.states[h].timestamp
        )
        
    def validate_ancestry(
        self,
        snapshot: StateSnapshot,
        max_depth: Optional[int] = None
    ) -> bool:
        """Validate state ancestry chain"""
        if max_depth is None:
            max_depth = self.max_depth
            
        # Check snapshot exists
        if snapshot.state_hash not in self.states:
            return False
            
        # Get ancestry
        ancestry = self.get_ancestry(snapshot.state_hash, max_depth)
        
        # Validate each ancestor
        prev_time = 0
        for state_hash in ancestry:
            state = self.states[state_hash]
            
            # Check timestamp order
            if state.timestamp < prev_time:
                return False
            prev_time = state.timestamp
            
            # Validate snapshot
            if not state.snapshot.verify(state.snapshot.node_id):
                return False
                
        return True
        
    def get_state_at(self, timestamp: float) -> Optional[StateSnapshot]:
        """Get state at specific timestamp"""
        # Find closest state before timestamp
        valid_states = [
            state
            for state in self.states.values()
            if state.timestamp <= timestamp
        ]
        
        if not valid_states:
            return None
            
        # Return most recent valid state
        return max(
            valid_states,
            key=lambda s: s.timestamp
        ).snapshot
        
    def cleanup_old_states(self, max_age: int = 86400):
        """Remove old states beyond max age"""
        current_time = time.time()
        old_states = [
            hash
            for hash, state in self.states.items()
            if current_time - state.timestamp > max_age
            and hash not in self.heads
            and hash != self.genesis_hash
        ]
        
        for hash in old_states:
            # Remove from parents' children
            state = self.states[hash]
            for parent in state.parents:
                if parent in self.states:
                    self.states[parent].children.remove(hash)
                    
            # Remove state
            del self.states[hash]
            
    def generate_checkpoint_hash(self) -> str:
        """Generate cryptographic checkpoint of DAG state"""
        # Sort states by timestamp
        sorted_states = sorted(
            self.states.items(),
            key=lambda x: x[1].timestamp
        )
        
        # Build checkpoint data
        checkpoint = {
            "genesis": self.genesis_hash,
            "heads": list(sorted(self.heads)),
            "states": [
                {
                    "hash": h,
                    "parents": s.parents,
                    "timestamp": s.timestamp,
                    "depth": s.depth
                }
                for h, s in sorted_states
            ]
        }
        
        # Generate hash
        content = json.dumps(checkpoint, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest() 