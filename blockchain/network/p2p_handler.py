"""
P2P Network Handler with replay protection and message validation
"""

import time
import hashlib
import asyncio
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from collections import OrderedDict

@dataclass
class MessageState:
    """Message state tracking"""
    message_id: str
    sender_id: str
    timestamp: float
    signature: str
    nonce: int
    
class P2PHandler:
    def __init__(self):
        self.message_timeout = 300  # 5 minutes
        self.max_message_age = 3600  # 1 hour
        self.max_cache_size = 10000
        self.nonce_window = 1000
        
        # Message tracking
        self.message_cache = OrderedDict()
        self.nonce_cache: Dict[str, Set[int]] = {}
        self.active_sessions: Set[str] = set()
        self.message_states: Dict[str, MessageState] = {}
        
        # Locks
        self._message_lock = asyncio.Lock()
        self._nonce_lock = asyncio.Lock()
        
    async def validate_message(
        self,
        message: Dict,
        sender_pubkey: bytes
    ) -> bool:
        """Validate P2P message with replay protection"""
        try:
            # Check message format
            if not self._validate_message_format(message):
                return False
                
            # Extract fields
            message_id = message["message_id"]
            sender_id = message["sender_id"]
            timestamp = message["timestamp"]
            signature = message["signature"]
            nonce = message["nonce"]
            
            # Check timestamp
            current_time = time.time()
            if (current_time - timestamp > self.max_message_age or
                timestamp > current_time + 300):  # 5 min future tolerance
                return False
                
            # Check replay
            async with self._message_lock:
                if await self._is_replay(message_id, sender_id, nonce):
                    return False
                    
                # Verify signature
                if not await self._verify_signature(
                    message_id,
                    sender_id,
                    timestamp,
                    nonce,
                    bytes.fromhex(signature),
                    sender_pubkey
                ):
                    return False
                    
                # Track message
                await self._track_message(
                    message_id,
                    sender_id,
                    timestamp,
                    signature,
                    nonce
                )
                
            return True
            
        except Exception as e:
            print(f"Message validation error: {e}")
            return False
            
    async def process_message(
        self,
        message: Dict,
        handler_callback
    ) -> Optional[Dict]:
        """Process P2P message with state validation"""
        try:
            message_id = message["message_id"]
            
            # Get message state
            state = self.message_states.get(message_id)
            if not state:
                return None
                
            # Check processing window
            if time.time() - state.timestamp > self.message_timeout:
                await self._cleanup_message(message_id)
                return None
                
            # Process message
            result = await handler_callback(message)
            
            # Cleanup
            await self._cleanup_message(message_id)
            
            return result
            
        except Exception as e:
            print(f"Message processing error: {e}")
            return None
            
    def _validate_message_format(self, message: Dict) -> bool:
        """Validate message format and required fields"""
        required_fields = {
            "message_id",
            "sender_id",
            "timestamp",
            "signature",
            "nonce",
            "payload"
        }
        
        return all(field in message for field in required_fields)
        
    async def _is_replay(
        self,
        message_id: str,
        sender_id: str,
        nonce: int
    ) -> bool:
        """Check for message replay"""
        try:
            # Check message cache
            if message_id in self.message_cache:
                return True
                
            # Check nonce window
            sender_nonces = self.nonce_cache.get(sender_id, set())
            if nonce in sender_nonces:
                return True
                
            # Update caches
            self.message_cache[message_id] = time.time()
            if len(self.message_cache) > self.max_cache_size:
                self.message_cache.popitem(last=False)
                
            if sender_id not in self.nonce_cache:
                self.nonce_cache[sender_id] = set()
            self.nonce_cache[sender_id].add(nonce)
            
            # Cleanup old nonces
            if len(self.nonce_cache[sender_id]) > self.nonce_window:
                oldest_nonce = min(self.nonce_cache[sender_id])
                self.nonce_cache[sender_id].remove(oldest_nonce)
                
            return False
            
        except Exception:
            return True
            
    async def _verify_signature(
        self,
        message_id: str,
        sender_id: str,
        timestamp: float,
        nonce: int,
        signature: bytes,
        pubkey: bytes
    ) -> bool:
        """Verify message signature"""
        try:
            # Create message digest
            message_data = f"{message_id}:{sender_id}:{timestamp}:{nonce}"
            message_hash = hashlib.sha256(message_data.encode()).digest()
            
            # Verify signature
            return self._verify_ecdsa_signature(
                message_hash,
                signature,
                pubkey
            )
            
        except Exception:
            return False
            
    async def _track_message(
        self,
        message_id: str,
        sender_id: str,
        timestamp: float,
        signature: str,
        nonce: int
    ):
        """Track message state"""
        state = MessageState(
            message_id=message_id,
            sender_id=sender_id,
            timestamp=timestamp,
            signature=signature,
            nonce=nonce
        )
        
        self.message_states[message_id] = state
        
    async def _cleanup_message(self, message_id: str):
        """Clean up message state"""
        if message_id in self.message_states:
            del self.message_states[message_id] 