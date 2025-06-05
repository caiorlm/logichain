"""
LogiChain Sync Blocker
Handles operation blocking during synchronization
"""

import time
import asyncio
from typing import Dict, Optional, Set
from enum import Enum
from dataclasses import dataclass

class SyncState(Enum):
    SYNCED = "synced"
    SYNCING = "syncing"
    BLOCKED = "blocked"

@dataclass
class SyncStatus:
    """Current sync status"""
    state: SyncState
    last_sync: float
    block_height: int
    block_hash: str
    timestamp: float

class SyncBlocker:
    """Manages operation blocking during sync"""
    
    def __init__(
        self,
        max_sync_age: int = 3600,  # 1 hour
        min_peers: int = 3
    ):
        self.max_sync_age = max_sync_age
        self.min_peers = min_peers
        
        self.sync_status = SyncStatus(
            state=SyncState.BLOCKED,
            last_sync=0,
            block_height=0,
            block_hash="",
            timestamp=0
        )
        
        self.peer_states: Dict[str, SyncStatus] = {}
        self.blocked_operations: Set[str] = set()
        
    def start_sync(self) -> bool:
        """Start synchronization process"""
        try:
            # Already syncing
            if self.sync_status.state == SyncState.SYNCING:
                return False
                
            # Update state
            self.sync_status.state = SyncState.SYNCING
            self.blocked_operations = set()
            
            return True
            
        except Exception:
            return False
            
    def end_sync(
        self,
        block_height: int,
        block_hash: str
    ) -> bool:
        """End synchronization process"""
        try:
            # Update status
            self.sync_status = SyncStatus(
                state=SyncState.SYNCED,
                last_sync=time.time(),
                block_height=block_height,
                block_hash=block_hash,
                timestamp=time.time()
            )
            
            # Clear blocked operations
            self.blocked_operations.clear()
            
            return True
            
        except Exception:
            return False
            
    def block_operation(self, operation_id: str) -> bool:
        """Block specific operation"""
        try:
            if self.sync_status.state != SyncState.SYNCED:
                return False
                
            self.blocked_operations.add(operation_id)
            return True
            
        except Exception:
            return False
            
    def unblock_operation(self, operation_id: str) -> bool:
        """Unblock specific operation"""
        try:
            self.blocked_operations.discard(operation_id)
            return True
            
        except Exception:
            return False
            
    def is_operation_allowed(self, operation_id: str) -> bool:
        """Check if operation is allowed"""
        try:
            # Check sync state
            if self.sync_status.state != SyncState.SYNCED:
                return False
                
            # Check sync age
            if time.time() - self.sync_status.last_sync > self.max_sync_age:
                return False
                
            # Check if operation is blocked
            if operation_id in self.blocked_operations:
                return False
                
            return True
            
        except Exception:
            return False
            
    def update_peer_state(
        self,
        peer_id: str,
        block_height: int,
        block_hash: str
    ) -> bool:
        """Update peer sync state"""
        try:
            # Update peer state
            self.peer_states[peer_id] = SyncStatus(
                state=SyncState.SYNCED,
                last_sync=time.time(),
                block_height=block_height,
                block_hash=block_hash,
                timestamp=time.time()
            )
            
            return True
            
        except Exception:
            return False
            
    def validate_sync_state(self) -> bool:
        """Validate current sync state"""
        try:
            # Must have minimum peers
            if len(self.peer_states) < self.min_peers:
                return False
                
            # Check sync age
            current_time = time.time()
            if current_time - self.sync_status.last_sync > self.max_sync_age:
                return False
                
            # Get peer heights
            heights = [
                state.block_height
                for state in self.peer_states.values()
                if current_time - state.timestamp <= self.max_sync_age
            ]
            
            if not heights:
                return False
                
            # Must be within 1 block of highest peer
            max_height = max(heights)
            if max_height - self.sync_status.block_height > 1:
                return False
                
            return True
            
        except Exception:
            return False
            
    async def wait_for_sync(
        self,
        timeout: Optional[float] = None
    ) -> bool:
        """Wait for sync to complete"""
        try:
            start_time = time.time()
            while True:
                # Check timeout
                if timeout and time.time() - start_time > timeout:
                    return False
                    
                # Check sync state
                if self.sync_status.state == SyncState.SYNCED:
                    if self.validate_sync_state():
                        return True
                        
                # Wait and retry
                await asyncio.sleep(1)
                
        except Exception:
            return False
            
    def cleanup_old_peers(self):
        """Remove old peer states"""
        current_time = time.time()
        
        # Find old peers
        old_peers = [
            peer_id
            for peer_id, state in self.peer_states.items()
            if current_time - state.timestamp > self.max_sync_age
        ]
        
        # Remove old peers
        for peer_id in old_peers:
            del self.peer_states[peer_id] 