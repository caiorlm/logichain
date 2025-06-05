"""
Immutable audit system with state protection and cryptographic verification
"""

import time
import hashlib
import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from collections import OrderedDict

class AuditState(Enum):
    PENDING = "PENDING"
    RECORDING = "RECORDING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    LOCKED = "LOCKED"
    INVALID = "INVALID"

@dataclass
class AuditEntry:
    """Immutable audit entry"""
    entry_id: str
    timestamp: float
    action: str
    data: Dict
    previous_hash: str
    entry_hash: str
    signature: str
    
class ImmutableAudit:
    def __init__(self):
        self.entries: OrderedDict[str, AuditEntry] = OrderedDict()
        self.state_hashes: Dict[str, str] = {}
        self.locked_entries: Set[str] = set()
        self.current_state = AuditState.PENDING
        self._last_hash = None
        
    def start_audit(self) -> bool:
        """Start new audit session"""
        if self.current_state != AuditState.PENDING:
            return False
            
        self.current_state = AuditState.RECORDING
        return True
        
    def record_entry(
        self,
        action: str,
        data: Dict,
        private_key: bytes
    ) -> Optional[str]:
        """Record new audit entry"""
        try:
            if self.current_state != AuditState.RECORDING:
                return None
                
            # Create entry
            entry_id = self._generate_entry_id()
            timestamp = time.time()
            
            # Calculate hashes
            previous_hash = self._last_hash or self._null_hash()
            entry_hash = self._calculate_entry_hash(
                entry_id,
                timestamp,
                action,
                data,
                previous_hash
            )
            
            # Sign entry
            signature = self._sign_entry(
                entry_hash,
                private_key
            )
            
            # Create immutable entry
            entry = AuditEntry(
                entry_id=entry_id,
                timestamp=timestamp,
                action=action,
                data=data.copy(),  # Copy to prevent mutation
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                signature=signature
            )
            
            # Store entry
            self.entries[entry_id] = entry
            self.state_hashes[entry_id] = entry_hash
            self._last_hash = entry_hash
            
            return entry_id
            
        except Exception as e:
            print(f"Error recording audit entry: {e}")
            return None
            
    def verify_entry(
        self,
        entry_id: str,
        public_key: bytes
    ) -> bool:
        """Verify audit entry integrity"""
        try:
            # Get entry
            entry = self.entries.get(entry_id)
            if not entry:
                return False
                
            # Check if locked
            if entry_id in self.locked_entries:
                return False
                
            # Verify hash chain
            if not self._verify_hash_chain(entry):
                return False
                
            # Verify signature
            if not self._verify_signature(
                entry.entry_hash,
                entry.signature,
                public_key
            ):
                return False
                
            return True
            
        except Exception:
            return False
            
    def lock_entry(self, entry_id: str) -> bool:
        """Lock audit entry to prevent modification"""
        try:
            if entry_id not in self.entries:
                return False
                
            self.locked_entries.add(entry_id)
            return True
            
        except Exception:
            return False
            
    def complete_audit(self) -> Optional[str]:
        """Complete audit session"""
        try:
            if self.current_state != AuditState.RECORDING:
                return None
                
            # Verify all entries
            self.current_state = AuditState.VERIFYING
            
            for entry_id in self.entries:
                if not self._verify_entry_state(entry_id):
                    self.current_state = AuditState.INVALID
                    return None
                    
            # Lock all entries
            for entry_id in self.entries:
                self.lock_entry(entry_id)
                
            # Calculate final hash
            final_hash = self._calculate_final_hash()
            
            self.current_state = AuditState.COMPLETED
            return final_hash
            
        except Exception as e:
            print(f"Error completing audit: {e}")
            self.current_state = AuditState.INVALID
            return None
            
    def _generate_entry_id(self) -> str:
        """Generate unique entry ID"""
        timestamp = int(time.time() * 1000)
        count = len(self.entries)
        data = f"entry:{timestamp}:{count}"
        return hashlib.sha256(data.encode()).hexdigest()
        
    def _calculate_entry_hash(
        self,
        entry_id: str,
        timestamp: float,
        action: str,
        data: Dict,
        previous_hash: str
    ) -> str:
        """Calculate deterministic entry hash"""
        entry_data = {
            "entry_id": entry_id,
            "timestamp": timestamp,
            "action": action,
            "data": data,
            "previous_hash": previous_hash
        }
        
        entry_json = json.dumps(entry_data, sort_keys=True)
        return hashlib.sha256(entry_json.encode()).hexdigest()
        
    def _verify_hash_chain(self, entry: AuditEntry) -> bool:
        """Verify entry hash chain"""
        try:
            # Get previous entry
            entries = list(self.entries.values())
            entry_index = entries.index(entry)
            
            if entry_index == 0:
                # First entry should link to null hash
                return entry.previous_hash == self._null_hash()
                
            # Verify link to previous entry
            previous_entry = entries[entry_index - 1]
            return entry.previous_hash == previous_entry.entry_hash
            
        except Exception:
            return False
            
    def _verify_entry_state(self, entry_id: str) -> bool:
        """Verify entry state integrity"""
        try:
            entry = self.entries[entry_id]
            stored_hash = self.state_hashes[entry_id]
            
            # Recalculate hash
            current_hash = self._calculate_entry_hash(
                entry.entry_id,
                entry.timestamp,
                entry.action,
                entry.data,
                entry.previous_hash
            )
            
            return current_hash == stored_hash
            
        except Exception:
            return False
            
    def _calculate_final_hash(self) -> str:
        """Calculate final audit hash"""
        hasher = hashlib.sha256()
        
        for entry in self.entries.values():
            entry_data = json.dumps({
                "entry_id": entry.entry_id,
                "entry_hash": entry.entry_hash,
                "signature": entry.signature
            }, sort_keys=True)
            
            hasher.update(entry_data.encode())
            
        return hasher.hexdigest()
        
    def _null_hash(self) -> str:
        """Generate null hash for first entry"""
        return "0" * 64
        
    def _sign_entry(
        self,
        entry_hash: str,
        private_key: bytes
    ) -> str:
        """Sign audit entry"""
        # Implementation depends on crypto library
        pass
        
    def _verify_signature(
        self,
        entry_hash: str,
        signature: str,
        public_key: bytes
    ) -> bool:
        """Verify entry signature"""
        # Implementation depends on crypto library
        pass 