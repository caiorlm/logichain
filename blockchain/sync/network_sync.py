from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import time
import hashlib
from enum import Enum
import asyncio
from collections import defaultdict

class NetworkMode(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"

@dataclass
class Operation:
    op_id: str
    node_id: str
    timestamp: float
    data: Dict
    signature: bytes
    public_key: bytes
    location_history: Optional[List[Tuple[float, float, float]]] = None  # [(lat, lon, timestamp)]

@dataclass
class NetworkState:
    operations: List[Operation]
    last_block_hash: str
    timestamp: float
    node_states: Dict[str, Dict]
    network_mode: NetworkMode

@dataclass
class SyncResult:
    success: bool
    state: Optional[NetworkState] = None
    reason: str = ""

class CircuitBreaker:
    def __init__(self):
        self.failure_count = defaultdict(int)
        self.last_failure = defaultdict(float)
        self.thresholds = {
            "MAX_FAILURES": 3,
            "RESET_AFTER": 3600,  # 1 hour
            "MAX_STATE_DIFF_PERCENT": 20,
            "MAX_OP_COUNT_DIFF": 1000,
            "MIN_NODES_AGREEMENT": 0.67  # 2/3 of nodes must agree
        }
        
    def record_failure(self, component: str):
        current_time = time.time()
        
        # Reset if enough time has passed
        if current_time - self.last_failure[component] > self.thresholds["RESET_AFTER"]:
            self.failure_count[component] = 0
            
        self.failure_count[component] += 1
        self.last_failure[component] = current_time
        
    def should_break(self, state: NetworkState) -> bool:
        # Check failure thresholds
        for component, count in self.failure_count.items():
            if count >= self.thresholds["MAX_FAILURES"]:
                return True
                
        # Analyze state metrics
        metrics = self._calculate_state_metrics(state)
        
        # Check for anomalies
        if metrics["state_diff_percent"] > self.thresholds["MAX_STATE_DIFF_PERCENT"]:
            return True
            
        if metrics["op_count_diff"] > self.thresholds["MAX_OP_COUNT_DIFF"]:
            return True
            
        if metrics["node_agreement"] < self.thresholds["MIN_NODES_AGREEMENT"]:
            return True
            
        return False
        
    def _calculate_state_metrics(self, state: NetworkState) -> Dict:
        metrics = {
            "state_diff_percent": 0,
            "op_count_diff": 0,
            "node_agreement": 1.0
        }
        
        # Calculate state differences
        state_values = []
        for node_state in state.node_states.values():
            state_values.append(self._hash_state(node_state))
            
        # Calculate agreement percentage
        if state_values:
            most_common = max(set(state_values), key=state_values.count)
            metrics["node_agreement"] = state_values.count(most_common) / len(state_values)
            
        # Calculate operation count differences
        op_counts = [len(node_state.get("operations", [])) for node_state in state.node_states.values()]
        if op_counts:
            metrics["op_count_diff"] = max(op_counts) - min(op_counts)
            
        return metrics
        
    def _hash_state(self, state: Dict) -> str:
        # Create deterministic string representation of state
        state_str = str(sorted(state.items()))
        return hashlib.sha256(state_str.encode()).hexdigest()

class StateMerger:
    def __init__(self):
        self.conflict_resolution_strategies = {
            "TIMESTAMP_BASED": self._resolve_by_timestamp,
            "QUORUM_BASED": self._resolve_by_quorum,
            "PROOF_OF_WORK": self._resolve_by_pow
        }
        
    async def merge(
        self,
        resolved_state: NetworkState,
        current_state: NetworkState
    ) -> NetworkState:
        try:
            # 1. Merge operations
            merged_ops = await self._merge_operations(
                resolved_state.operations,
                current_state.operations
            )
            
            # 2. Merge node states
            merged_node_states = self._merge_node_states(
                resolved_state.node_states,
                current_state.node_states
            )
            
            # 3. Choose latest timestamp
            merged_timestamp = max(
                resolved_state.timestamp,
                current_state.timestamp
            )
            
            # 4. Select appropriate block hash
            merged_block_hash = (
                resolved_state.last_block_hash
                if resolved_state.timestamp > current_state.timestamp
                else current_state.last_block_hash
            )
            
            return NetworkState(
                operations=merged_ops,
                last_block_hash=merged_block_hash,
                timestamp=merged_timestamp,
                node_states=merged_node_states,
                network_mode=resolved_state.network_mode
            )
            
        except Exception as e:
            raise Exception(f"State merge failed: {str(e)}")
            
    async def _merge_operations(
        self,
        ops1: List[Operation],
        ops2: List[Operation]
    ) -> List[Operation]:
        # Create operation maps for quick lookup
        op_map1 = {op.op_id: op for op in ops1}
        op_map2 = {op.op_id: op for op in ops2}
        
        # Combine unique operations
        merged_ops = {}
        
        # Add all ops from first list
        for op_id, op in op_map1.items():
            merged_ops[op_id] = op
            
        # Process ops from second list
        for op_id, op in op_map2.items():
            if op_id in merged_ops:
                # Resolve conflict
                merged_ops[op_id] = await self._resolve_operation_conflict(
                    merged_ops[op_id],
                    op
                )
            else:
                merged_ops[op_id] = op
                
        return list(merged_ops.values())
        
    def _merge_node_states(
        self,
        states1: Dict[str, Dict],
        states2: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        merged_states = {}
        
        # Merge states from both sources
        all_node_ids = set(states1.keys()) | set(states2.keys())
        
        for node_id in all_node_ids:
            state1 = states1.get(node_id, {})
            state2 = states2.get(node_id, {})
            
            if node_id in states1 and node_id in states2:
                # Both states exist - merge them
                merged_states[node_id] = self._merge_single_node_state(
                    state1,
                    state2
                )
            else:
                # Take the existing state
                merged_states[node_id] = state1 if node_id in states1 else state2
                
        return merged_states
        
    def _merge_single_node_state(
        self,
        state1: Dict,
        state2: Dict
    ) -> Dict:
        merged_state = {}
        
        # Merge all keys
        all_keys = set(state1.keys()) | set(state2.keys())
        
        for key in all_keys:
            if key in state1 and key in state2:
                # Both states have the key - use most recent
                timestamp1 = state1.get("timestamp", 0)
                timestamp2 = state2.get("timestamp", 0)
                merged_state[key] = state1[key] if timestamp1 > timestamp2 else state2[key]
            else:
                # Take the existing value
                merged_state[key] = state1.get(key, state2.get(key))
                
        return merged_state
        
    async def _resolve_operation_conflict(
        self,
        op1: Operation,
        op2: Operation
    ) -> Operation:
        # Try different resolution strategies in order
        for strategy in self.conflict_resolution_strategies.values():
            result = await strategy(op1, op2)
            if result:
                return result
                
        # Default to timestamp-based if no strategy succeeds
        return op1 if op1.timestamp > op2.timestamp else op2
        
    async def _resolve_by_timestamp(
        self,
        op1: Operation,
        op2: Operation
    ) -> Optional[Operation]:
        # Simple timestamp-based resolution
        if abs(op1.timestamp - op2.timestamp) > 1:  # 1 second threshold
            return op1 if op1.timestamp > op2.timestamp else op2
        return None
        
    async def _resolve_by_quorum(
        self,
        op1: Operation,
        op2: Operation
    ) -> Optional[Operation]:
        # This would check which operation has more confirmations from trusted nodes
        # Simplified version - would need actual quorum data
        return None
        
    async def _resolve_by_pow(
        self,
        op1: Operation,
        op2: Operation
    ) -> Optional[Operation]:
        # This would check which operation has more proof of work
        # Simplified version - would need actual PoW data
        return None

class SecureSynchronizer:
    def __init__(self):
        self.snapshot_validator = SnapshotValidator()
        self.state_merger = StateMerger()
        self.circuit_breaker = CircuitBreaker()
        
    async def sync_networks(
        self,
        online_state: NetworkState,
        offline_state: NetworkState
    ) -> SyncResult:
        try:
            # 1. Validate states
            if not self._validate_states(online_state, offline_state):
                return SyncResult(
                    success=False,
                    reason="Invalid state format"
                )
                
            # 2. Detect conflicts
            conflicts = self._detect_conflicts(
                online_state.operations,
                offline_state.operations
            )
            
            # 3. Resolve conflicts
            resolved_state = await self._resolve_conflicts(
                conflicts,
                online_state,
                offline_state
            )
            
            # 4. Check circuit breakers
            if self.circuit_breaker.should_break(resolved_state):
                return SyncResult(
                    success=False,
                    reason="Circuit breaker activated"
                )
                
            # 5. Merge final state
            final_state = await self.state_merger.merge(
                resolved_state,
                online_state if online_state.timestamp > offline_state.timestamp else offline_state
            )
            
            return SyncResult(success=True, state=final_state)
            
        except Exception as e:
            return SyncResult(
                success=False,
                reason=f"Sync error: {str(e)}"
            )
            
    def _validate_states(
        self,
        online_state: NetworkState,
        offline_state: NetworkState
    ) -> bool:
        # Basic validation of state format and content
        try:
            # Check network modes
            if online_state.network_mode != NetworkMode.ONLINE:
                return False
            if offline_state.network_mode != NetworkMode.OFFLINE:
                return False
                
            # Validate timestamps
            current_time = time.time()
            max_time_drift = 3600  # 1 hour
            
            if abs(online_state.timestamp - current_time) > max_time_drift:
                return False
            if abs(offline_state.timestamp - current_time) > max_time_drift:
                return False
                
            # Validate operation format
            for op in online_state.operations + offline_state.operations:
                if not self._validate_operation(op):
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def _validate_operation(self, operation: Operation) -> bool:
        # Validate individual operation format and content
        try:
            # Check required fields
            if not all([
                operation.op_id,
                operation.node_id,
                operation.timestamp,
                operation.data,
                operation.signature,
                operation.public_key
            ]):
                return False
                
            # Validate timestamp
            if operation.timestamp > time.time():
                return False
                
            # Validate location history if present
            if operation.location_history:
                prev_timestamp = 0
                for lat, lon, timestamp in operation.location_history:
                    if timestamp <= prev_timestamp:
                        return False
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        return False
                    prev_timestamp = timestamp
                    
            return True
            
        except Exception:
            return False
            
    def _detect_conflicts(
        self,
        online_ops: List[Operation],
        offline_ops: List[Operation]
    ) -> Dict[str, List[Operation]]:
        conflicts = defaultdict(list)
        
        # Create operation maps
        online_map = {op.op_id: op for op in online_ops}
        offline_map = {op.op_id: op for op in offline_ops}
        
        # Find conflicting operations
        all_op_ids = set(online_map.keys()) | set(offline_map.keys())
        
        for op_id in all_op_ids:
            online_op = online_map.get(op_id)
            offline_op = offline_map.get(op_id)
            
            if online_op and offline_op:
                # Both networks have the operation - check for conflicts
                if self._operations_conflict(online_op, offline_op):
                    conflicts[op_id].extend([online_op, offline_op])
                    
        return conflicts
        
    def _operations_conflict(
        self,
        op1: Operation,
        op2: Operation
    ) -> bool:
        # Check if two operations conflict
        # This is a simplified check - real implementation would be more complex
        return (
            op1.op_id == op2.op_id and
            (
                op1.data != op2.data or
                op1.signature != op2.signature or
                abs(op1.timestamp - op2.timestamp) > 1
            )
        )
        
    async def _resolve_conflicts(
        self,
        conflicts: Dict[str, List[Operation]],
        online_state: NetworkState,
        offline_state: NetworkState
    ) -> NetworkState:
        resolved_ops = []
        
        # Add non-conflicting operations
        online_map = {op.op_id: op for op in online_state.operations}
        offline_map = {op.op_id: op for op in offline_state.operations}
        
        for op_id in set(online_map.keys()) | set(offline_map.keys()):
            if op_id not in conflicts:
                # No conflict - take the operation from either state
                op = online_map.get(op_id) or offline_map.get(op_id)
                resolved_ops.append(op)
                
        # Resolve conflicts
        for op_id, conflicting_ops in conflicts.items():
            resolved_op = await self.state_merger._resolve_operation_conflict(
                conflicting_ops[0],
                conflicting_ops[1]
            )
            resolved_ops.append(resolved_op)
            
        # Create resolved state
        return NetworkState(
            operations=resolved_ops,
            last_block_hash=online_state.last_block_hash,  # Prefer online state
            timestamp=time.time(),
            node_states=online_state.node_states,  # Prefer online state
            network_mode=NetworkMode.ONLINE  # Switch to online mode
        )

class SnapshotValidator:
    def __init__(self):
        pass  # Add initialization if needed 