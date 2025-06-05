from typing import Dict, Optional
import os
import json
import time
from dataclasses import dataclass
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from collections import OrderedDict

@dataclass
class LoRaMessage:
    source: str
    destination: str
    timestamp: float
    data: Dict
    message_type: str
    sequence: int

class ExpiringSet:
    def __init__(self, timeout: int):
        self.timeout = timeout
        self.items = OrderedDict()
        
    def add(self, item):
        self.items[item] = time.time()
        self._cleanup()
        
    def __contains__(self, item):
        if item in self.items:
            if time.time() - self.items[item] > self.timeout:
                del self.items[item]
                return False
            return True
        return False
        
    def _cleanup(self):
        current_time = time.time()
        for item, timestamp in list(self.items.items()):
            if current_time - timestamp > self.timeout:
                del self.items[item]

class SecurityException(Exception):
    pass

class SecureLoRaProtocol:
    KEY_SIZE = 32  # 256 bits
    NONCE_SIZE = 12
    TAG_SIZE = 16
    MAX_PACKET_SIZE = 255  # LoRa limitation
    
    def __init__(self):
        self.key_rotation_interval = 3600  # 1 hour
        self.nonce_cache = ExpiringSet(timeout=3600)
        self._current_key = get_random_bytes(self.KEY_SIZE)
        self._last_key_rotation = time.time()
        
    def _rotate_key_if_needed(self):
        current_time = time.time()
        if current_time - self._last_key_rotation > self.key_rotation_interval:
            self._current_key = get_random_bytes(self.KEY_SIZE)
            self._last_key_rotation = current_time
            self.nonce_cache = ExpiringSet(timeout=3600)  # Reset nonce cache
            
    def current_key(self) -> bytes:
        self._rotate_key_if_needed()
        return self._current_key
        
    def encrypt_packet(self, message: LoRaMessage) -> bytes:
        # Generate nonce
        nonce = os.urandom(self.NONCE_SIZE)
        if nonce in self.nonce_cache:
            raise SecurityException("Nonce reuse detected")
            
        self.nonce_cache.add(nonce)
        
        # Prepare associated data for additional authentication
        aad = f"{message.source}:{message.destination}:{message.timestamp}".encode()
        
        # Create cipher instance
        cipher = AES.new(self.current_key(), AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)
        
        # Serialize and encrypt message
        message_data = json.dumps({
            "type": message.message_type,
            "seq": message.sequence,
            "data": message.data
        }).encode()
        
        # Check packet size
        total_size = len(nonce) + self.TAG_SIZE + len(message_data)
        if total_size > self.MAX_PACKET_SIZE:
            raise SecurityException(f"Packet too large: {total_size} bytes")
            
        # Encrypt and create authentication tag
        ciphertext, tag = cipher.encrypt_and_digest(message_data)
        
        # Combine nonce, tag and ciphertext
        return nonce + tag + ciphertext
        
    def decrypt_packet(self, encrypted_data: bytes, source: str, destination: str) -> Optional[Dict]:
        try:
            # Extract components
            nonce = encrypted_data[:self.NONCE_SIZE]
            tag = encrypted_data[self.NONCE_SIZE:self.NONCE_SIZE + self.TAG_SIZE]
            ciphertext = encrypted_data[self.NONCE_SIZE + self.TAG_SIZE:]
            
            # Check for nonce reuse
            if nonce in self.nonce_cache:
                raise SecurityException("Nonce reuse detected in decryption")
                
            self.nonce_cache.add(nonce)
            
            # Prepare AAD
            current_time = time.time()
            aad = f"{source}:{destination}:{current_time}".encode()
            
            # Create cipher instance
            cipher = AES.new(self.current_key(), AES.MODE_GCM, nonce=nonce)
            cipher.update(aad)
            
            # Decrypt and verify
            try:
                decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
                return json.loads(decrypted_data.decode())
            except (ValueError, json.JSONDecodeError) as e:
                raise SecurityException(f"Decryption failed: {str(e)}")
                
        except Exception as e:
            raise SecurityException(f"Packet decryption error: {str(e)}")
            
    def validate_packet_size(self, data: bytes) -> bool:
        return len(data) <= self.MAX_PACKET_SIZE 