"""
Secure synchronization with atomic locks and sequential validation
"""

import time
import hashlib
import threading
import asyncio
import json
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from collections import OrderedDict

class SyncStatus(Enum):
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    AUDIT = "AUDIT"
    LOCKED = "LOCKED"

@dataclass
class SyncState:
    """Atomic sync state"""
    local_chain_hash: str
    remote_chain_hash: str
    last_common_block: Dict
    pending_blocks: List[Dict]
    pending_transactions: List[Dict]
    pending_pods: List[Dict]
    merkle_proof: Dict
    timestamp: float
    status: SyncStatus
    sequence_number: int
    lock: threading.Lock
    validation_event: asyncio.Event

class SecureSync:
    def __init__(self):
        self.sync_timeout = 3600  # 1 hour
        self.max_pending_blocks = 1000
        self.min_quorum_votes = 3
        self.sync_states: Dict[str, SyncState] = {}
        self.audit_queue: List[Tuple[str, str]] = []
        self.global_lock = threading.Lock()
        self.sequence_counter = 0
        self.active_syncs: Set[str] = set()
        self._sync_cache = OrderedDict()
        self.MAX_CACHE_SIZE = 1000
        
    async def start_sync(
        self,
        local_chain: List[Dict],
        remote_chain: List[Dict],
        node_id: str
    ) -> Optional[str]:
        """Start atomic synchronization process"""
        try:
            # Global lock for sync initialization
            with self.global_lock:
                if node_id in self.active_syncs:
                    return None
                    
                # Generate unique sync ID
                sync_id = self._generate_sync_id(node_id)
                
                # Initialize atomic state
                state = await self._init_sync_state(
                    local_chain,
                    remote_chain,
                    sync_id
                )
                
                self.sync_states[sync_id] = state
                self.active_syncs.add(node_id)
                
            return sync_id
            
        except Exception as e:
            print(f"Sync start error: {e}")
            return None
            
    async def prepare_sync_data(
        self,
        sync_id: str,
        local_chain: List[Dict],
        node_id: str,
        private_key: bytes
    ) -> Optional[Dict]:
        """Prepare sync data with sequential validation"""
        try:
            state = self.sync_states.get(sync_id)
            if not state:
                return None
                
            # Acquire state lock
            async with self._acquire_state_lock(state):
                # Validate sequence
                if not await self._validate_sequence(state, sync_id):
                    return None
                    
                # Prepare sync data
                sync_data = await self._prepare_data(
                    state,
                    local_chain,
                    node_id,
                    private_key
                )
                
                # Cache sync data
                self._cache_sync_data(sync_id, sync_data)
                
                return sync_data
                
        except Exception as e:
            print(f"Error preparing sync data: {e}")
            return None
            
    async def verify_sync_data(
        self,
        sync_data: Dict,
        node_pubkey: bytes
    ) -> bool:
        """Verify sync data with replay protection"""
        try:
            # Check replay
            if self._is_replay(sync_data):
                return False
                
            # Verify signature
            if not await self._verify_sync_signature(
                sync_data["sync_id"],
                sync_data["merkle_proof"]["root"],
                bytes.fromhex(sync_data["signature"]),
                node_pubkey
            ):
                return False
                
            # Verify Merkle proof
            if not await self._verify_merkle_proof(
                sync_data["blocks"],
                sync_data["transactions"],
                sync_data["pods"],
                sync_data["merkle_proof"]
            ):
                return False
                
            return True
            
        except Exception:
            return False
            
    async def apply_sync(
        self,
        sync_id: str,
        sync_data: Dict,
        quorum_votes: List[Dict]
    ) -> bool:
        """Apply sync with atomic state transition"""
        try:
            state = self.sync_states.get(sync_id)
            if not state:
                return False
                
            # Acquire state lock
            async with self._acquire_state_lock(state):
                # Verify quorum
                if len(quorum_votes) < self.min_quorum_votes:
                    return False
                    
                # Verify all votes are valid
                if not await self._verify_all_votes(quorum_votes):
                    return False
                    
                # Check for suspicious patterns
                if await self._is_sync_suspicious(state, sync_data):
                    await self._handle_suspicious_sync(state)
                    return False
                    
                # Atomic state transition
                await self._transition_state(state, sync_data)
                
                return True
                
        except Exception as e:
            print(f"Sync application error: {e}")
            state.status = SyncStatus.FAILED
            return False
            
    def _generate_sync_id(self, node_id: str) -> str:
        """Generate unique sync ID with timestamp"""
        timestamp = int(time.time() * 1000)
        data = f"{node_id}:{timestamp}:{self.sequence_counter}"
        return hashlib.sha256(data.encode()).hexdigest()
        
    async def _init_sync_state(
        self,
        local_chain: List[Dict],
        remote_chain: List[Dict],
        sync_id: str
    ) -> SyncState:
        """Initialize atomic sync state"""
        with self.global_lock:
            self.sequence_counter += 1
            sequence = self.sequence_counter
            
        return SyncState(
            local_chain_hash=self._calculate_chain_hash(local_chain),
            remote_chain_hash=self._calculate_chain_hash(remote_chain),
            last_common_block=self._find_last_common_block(
                local_chain,
                remote_chain
            ),
            pending_blocks=[],
            pending_transactions=[],
            pending_pods=[],
            merkle_proof={},
            timestamp=time.time(),
            status=SyncStatus.PENDING,
            sequence_number=sequence,
            lock=threading.Lock(),
            validation_event=asyncio.Event()
        )
        
    async def _acquire_state_lock(self, state: SyncState):
        """Acquire state lock with timeout"""
        if not state.lock.acquire(timeout=5):
            raise TimeoutError("Failed to acquire state lock")
        return state.lock
        
    async def _validate_sequence(
        self,
        state: SyncState,
        sync_id: str
    ) -> bool:
        """Validate operation sequence"""
        try:
            # Check sequence number
            if state.sequence_number <= 0:
                return False
                
            # Check timestamp
            if time.time() - state.timestamp > self.sync_timeout:
                return False
                
            # Set validation event
            state.validation_event.set()
            return True
            
        except Exception:
            return False
            
    def _is_replay(self, sync_data: Dict) -> bool:
        """Check for replay attacks"""
        sync_id = sync_data.get("sync_id")
        if not sync_id:
            return True
            
        # Check cache
        if sync_id in self._sync_cache:
            return True
            
        # Add to cache with LRU eviction
        self._sync_cache[sync_id] = time.time()
        if len(self._sync_cache) > self.MAX_CACHE_SIZE:
            self._sync_cache.popitem(last=False)
            
        return False
        
    async def _verify_all_votes(self, votes: List[Dict]) -> bool:
        """Verify all quorum votes"""
        try:
            for vote in votes:
                if not await self._verify_quorum_vote(vote):
                    return False
            return True
        except Exception:
            return False
            
    async def _transition_state(
        self,
        state: SyncState,
        sync_data: Dict
    ):
        """Atomic state transition"""
        try:
            # Update state
            state.pending_blocks = sync_data["blocks"]
            state.pending_transactions = sync_data["transactions"]
            state.pending_pods = sync_data["pods"]
            state.merkle_proof = sync_data["merkle_proof"]
            state.status = SyncStatus.COMPLETED
            
            # Clear validation event
            state.validation_event.clear()
            
        except Exception as e:
            state.status = SyncStatus.FAILED
            raise e
            
    async def _handle_suspicious_sync(self, state: SyncState):
        """Handle suspicious sync attempt"""
        state.status = SyncStatus.AUDIT
        self.audit_queue.append(
            (state.local_chain_hash, state.remote_chain_hash)
        )
        
    def _calculate_chain_hash(self, chain: List[Dict]) -> str:
        """Calculate deterministic chain hash"""
        hasher = hashlib.sha256()
        
        for block in chain:
            block_data = json.dumps(block, sort_keys=True)
            hasher.update(block_data.encode())
            
        return hasher.hexdigest()
        
    def _find_last_common_block(
        self,
        local_chain: List[Dict],
        remote_chain: List[Dict]
    ) -> Optional[int]:
        """Find index of last common block between chains"""
        min_len = min(len(local_chain), len(remote_chain))
        
        for i in range(min_len - 1, -1, -1):
            if (
                local_chain[i]["hash"] == remote_chain[i]["hash"] and
                local_chain[i]["index"] == remote_chain[i]["index"]
            ):
                return i
                
        return None
        
    def _create_merkle_proof(
        self,
        blocks: List[Dict],
        transactions: List[Dict],
        pods: List[Dict]
    ) -> Dict:
        """Create Merkle proof for sync data"""
        # Create leaf nodes
        leaves = (
            [self._hash_dict(b) for b in blocks] +
            [self._hash_dict(t) for t in transactions] +
            [self._hash_dict(p) for p in pods]
        )
        
        # Build Merkle tree
        tree = leaves.copy()
        proof = {"leaves": leaves, "path": []}
        
        while len(tree) > 1:
            if len(tree) % 2 == 1:
                tree.append(tree[-1])
                
            proof["path"].append([
                tree[i:i+2]
                for i in range(0, len(tree), 2)
            ])
            
            tree = [
                hashlib.sha256(
                    (tree[i] + tree[i+1]).encode()
                ).hexdigest()
                for i in range(0, len(tree), 2)
            ]
            
        proof["root"] = tree[0]
        return proof
        
    def _verify_merkle_proof(
        self,
        blocks: List[Dict],
        transactions: List[Dict],
        pods: List[Dict],
        proof: Dict
    ) -> bool:
        """Verify Merkle proof of sync data"""
        # Verify leaves match data
        leaves = (
            [self._hash_dict(b) for b in blocks] +
            [self._hash_dict(t) for t in transactions] +
            [self._hash_dict(p) for p in pods]
        )
        
        if leaves != proof["leaves"]:
            return False
            
        # Verify proof path
        tree = leaves.copy()
        
        for level in proof["path"]:
            if len(tree) % 2 == 1:
                tree.append(tree[-1])
                
            calculated = [
                hashlib.sha256(
                    (tree[i] + tree[i+1]).encode()
                ).hexdigest()
                for i in range(0, len(tree), 2)
            ]
            
            if calculated != [
                hashlib.sha256(
                    (pair[0] + pair[1]).encode()
                ).hexdigest()
                for pair in level
            ]:
                return False
                
            tree = calculated
            
        return tree[0] == proof["root"]
        
    def _sign_sync_data(
        self,
        sync_id: str,
        merkle_root: str,
        private_key: bytes
    ) -> bytes:
        """Sign sync data with node's private key"""
        message = f"{sync_id}:{merkle_root}".encode()
        signing_key = ed25519.SigningKey(private_key)
        return signing_key.sign(message)
        
    def _verify_sync_signature(
        self,
        sync_id: str,
        merkle_root: str,
        signature: bytes,
        node_pubkey: bytes
    ) -> bool:
        """Verify sync data signature"""
        try:
            message = f"{sync_id}:{merkle_root}".encode()
            verifying_key = ed25519.VerifyingKey(node_pubkey)
            verifying_key.verify(signature, message)
            return True
        except:
            return False
            
    def _verify_quorum_vote(self, vote: Dict) -> bool:
        """Verify quorum vote validity"""
        # Implementation depends on quorum system
        return True  # Placeholder
        
    def _is_sync_suspicious(
        self,
        state: SyncState,
        sync_data: Dict
    ) -> bool:
        """Check for suspicious patterns in sync"""
        # Check sync age
        if time.time() - state.timestamp > self.sync_timeout:
            return True
            
        # Check block sequence
        if not self._verify_block_sequence(sync_data["blocks"]):
            return True
            
        # Check for duplicate transactions/PODs
        if self._has_duplicates(sync_data["transactions"]):
            return True
            
        if self._has_duplicates(sync_data["pods"]):
            return True
            
        return False
        
    def _verify_block_sequence(self, blocks: List[Dict]) -> bool:
        """Verify block sequence is valid"""
        for i in range(1, len(blocks)):
            if (
                blocks[i]["index"] != blocks[i-1]["index"] + 1 or
                blocks[i]["previous_hash"] != blocks[i-1]["hash"]
            ):
                return False
        return True
        
    def _has_duplicates(self, items: List[Dict]) -> bool:
        """Check for duplicate items"""
        seen = set()
        for item in items:
            item_hash = self._hash_dict(item)
            if item_hash in seen:
                return True
            seen.add(item_hash)
        return False
        
    def _hash_dict(self, data: Dict) -> str:
        """Create hash of dictionary data"""
        return hashlib.sha256(
            str(sorted(data.items())).encode()
        ).hexdigest() 