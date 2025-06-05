import time
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class SyncStatus(Enum):
    IN_SYNC = "IN_SYNC"
    SYNCING = "SYNCING"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    SUSPICIOUS = "SUSPICIOUS"

@dataclass
class SyncAttempt:
    node_id: str
    start_height: int
    target_height: int
    start_time: float
    last_update: float
    blocks_synced: int
    status: SyncStatus
    is_offgrid: bool
    details: Dict

class SyncDetector:
    def __init__(self):
        self.sync_attempts: Dict[str, SyncAttempt] = {}  # node_id -> attempt
        self.failed_attempts: Dict[str, List[SyncAttempt]] = {}  # node_id -> history
        self.suspicious_nodes: Set[str] = set()
        self.sync_timeout = 300  # 5 minutes
        self.max_retry_count = 3
        self.min_sync_speed = 1  # blocks/second
        
    def start_sync(
        self,
        node_id: str,
        start_height: int,
        target_height: int,
        is_offgrid: bool
    ) -> SyncStatus:
        """Start tracking a new sync attempt"""
        try:
            # Check if node is suspicious
            if node_id in self.suspicious_nodes:
                return SyncStatus.SUSPICIOUS
                
            # Check existing attempt
            if node_id in self.sync_attempts:
                existing = self.sync_attempts[node_id]
                
                # Check if existing attempt timed out
                if self._is_timeout(existing):
                    self._handle_timeout(existing)
                    
                # Check retry count
                if self._get_retry_count(node_id) >= self.max_retry_count:
                    self.suspicious_nodes.add(node_id)
                    return SyncStatus.SUSPICIOUS
                    
            # Start new attempt
            attempt = SyncAttempt(
                node_id=node_id,
                start_height=start_height,
                target_height=target_height,
                start_time=time.time(),
                last_update=time.time(),
                blocks_synced=0,
                status=SyncStatus.SYNCING,
                is_offgrid=is_offgrid,
                details={}
            )
            
            self.sync_attempts[node_id] = attempt
            return SyncStatus.SYNCING
            
        except Exception as e:
            print(f"Error starting sync: {e}")
            return SyncStatus.FAILED
            
    def update_sync(
        self,
        node_id: str,
        current_height: int,
        blocks_received: int,
        merkle_valid: bool,
        pow_valid: bool
    ) -> SyncStatus:
        """Update sync progress"""
        try:
            if node_id not in self.sync_attempts:
                return SyncStatus.FAILED
                
            attempt = self.sync_attempts[node_id]
            
            # Check timeout
            if self._is_timeout(attempt):
                self._handle_timeout(attempt)
                return SyncStatus.TIMEOUT
                
            # Update progress
            attempt.blocks_synced += blocks_received
            attempt.last_update = time.time()
            
            # Check sync speed
            if not self._check_sync_speed(attempt):
                attempt.status = SyncStatus.SUSPICIOUS
                self.suspicious_nodes.add(node_id)
                return SyncStatus.SUSPICIOUS
                
            # Check validation
            if not merkle_valid or not pow_valid:
                attempt.status = SyncStatus.FAILED
                self._record_failed_attempt(attempt)
                return SyncStatus.FAILED
                
            # Check if sync complete
            if current_height >= attempt.target_height:
                attempt.status = SyncStatus.IN_SYNC
                del self.sync_attempts[node_id]
                return SyncStatus.IN_SYNC
                
            # Still syncing
            return SyncStatus.SYNCING
            
        except Exception as e:
            print(f"Error updating sync: {e}")
            return SyncStatus.FAILED
            
    def _is_timeout(
        self,
        attempt: SyncAttempt
    ) -> bool:
        """Check if sync attempt has timed out"""
        current_time = time.time()
        
        # Check total time
        if current_time - attempt.start_time > self.sync_timeout:
            return True
            
        # Check time since last update
        if current_time - attempt.last_update > 60:  # 1 minute
            return True
            
        return False
        
    def _handle_timeout(
        self,
        attempt: SyncAttempt
    ):
        """Handle sync timeout"""
        attempt.status = SyncStatus.TIMEOUT
        attempt.details["timeout_time"] = time.time()
        self._record_failed_attempt(attempt)
        
        if attempt.node_id in self.sync_attempts:
            del self.sync_attempts[attempt.node_id]
            
    def _record_failed_attempt(
        self,
        attempt: SyncAttempt
    ):
        """Record failed sync attempt"""
        if attempt.node_id not in self.failed_attempts:
            self.failed_attempts[attempt.node_id] = []
            
        self.failed_attempts[attempt.node_id].append(attempt)
        
        # Cleanup old attempts
        self.failed_attempts[attempt.node_id] = [
            a for a in self.failed_attempts[attempt.node_id]
            if time.time() - a.start_time < 86400  # 24 hours
        ]
        
    def _get_retry_count(
        self,
        node_id: str
    ) -> int:
        """Get number of failed attempts in last hour"""
        if node_id not in self.failed_attempts:
            return 0
            
        current_time = time.time()
        return len([
            a for a in self.failed_attempts[node_id]
            if current_time - a.start_time < 3600  # 1 hour
        ])
        
    def _check_sync_speed(
        self,
        attempt: SyncAttempt
    ) -> bool:
        """Check if sync speed is suspicious"""
        try:
            # Calculate blocks per second
            elapsed = time.time() - attempt.start_time
            if elapsed < 10:  # Need minimum time to calculate
                return True
                
            blocks_per_second = attempt.blocks_synced / elapsed
            
            # Check minimum speed
            if blocks_per_second < self.min_sync_speed:
                attempt.details["sync_speed"] = blocks_per_second
                return False
                
            # Check for impossible speed
            if attempt.is_offgrid:
                if blocks_per_second > 10:  # Max 10 blocks/s off-grid
                    attempt.details["sync_speed"] = blocks_per_second
                    return False
            else:
                if blocks_per_second > 100:  # Max 100 blocks/s on-grid
                    attempt.details["sync_speed"] = blocks_per_second
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def get_sync_status(
        self,
        node_id: str
    ) -> Optional[Dict]:
        """Get node's sync status"""
        # Check current attempt
        if node_id in self.sync_attempts:
            attempt = self.sync_attempts[node_id]
            return {
                "status": attempt.status.value,
                "progress": attempt.blocks_synced / (
                    attempt.target_height - attempt.start_height
                ),
                "blocks_synced": attempt.blocks_synced,
                "elapsed_time": time.time() - attempt.start_time,
                "is_suspicious": node_id in self.suspicious_nodes,
                "details": attempt.details
            }
            
        # Check failed attempts
        if node_id in self.failed_attempts:
            failed = self.failed_attempts[node_id]
            return {
                "status": "FAILED",
                "total_attempts": len(failed),
                "last_attempt": max(a.start_time for a in failed),
                "is_suspicious": node_id in self.suspicious_nodes,
                "details": failed[-1].details if failed else {}
            }
            
        return None
        
    def cleanup_old_attempts(self):
        """Cleanup old sync attempts"""
        current_time = time.time()
        
        # Check timeouts
        for node_id, attempt in list(self.sync_attempts.items()):
            if self._is_timeout(attempt):
                self._handle_timeout(attempt)
                
        # Cleanup failed attempts
        for node_id in list(self.failed_attempts.keys()):
            self.failed_attempts[node_id] = [
                a for a in self.failed_attempts[node_id]
                if current_time - a.start_time < 86400  # 24 hours
            ]
            
            if not self.failed_attempts[node_id]:
                del self.failed_attempts[node_id] 