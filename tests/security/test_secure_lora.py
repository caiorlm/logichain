import pytest
import time
from blockchain.security.secure_lora import (
    SecureLoRaProtocol,
    LoRaMessage,
    SecurityException
)

@pytest.fixture
def protocol():
    return SecureLoRaProtocol()

@pytest.fixture
def test_message():
    return LoRaMessage(
        source="node1",
        destination="node2",
        timestamp=time.time(),
        data={"test": "data"},
        message_type="TEST",
        sequence=1
    )

def test_packet_encryption(protocol, test_message):
    # Test basic encryption
    encrypted = protocol.encrypt_packet(test_message)
    assert isinstance(encrypted, bytes)
    assert len(encrypted) > 0
    
    # Verify packet components
    nonce = encrypted[:protocol.NONCE_SIZE]
    tag = encrypted[protocol.NONCE_SIZE:protocol.NONCE_SIZE + protocol.TAG_SIZE]
    ciphertext = encrypted[protocol.NONCE_SIZE + protocol.TAG_SIZE:]
    
    assert len(nonce) == protocol.NONCE_SIZE
    assert len(tag) == protocol.TAG_SIZE
    assert len(ciphertext) > 0

def test_packet_decryption(protocol, test_message):
    # Encrypt and then decrypt
    encrypted = protocol.encrypt_packet(test_message)
    decrypted = protocol.decrypt_packet(
        encrypted,
        test_message.source,
        test_message.destination
    )
    
    # Verify decrypted data
    assert isinstance(decrypted, dict)
    assert decrypted["type"] == test_message.message_type
    assert decrypted["seq"] == test_message.sequence
    assert decrypted["data"] == test_message.data

def test_nonce_reuse_detection(protocol, test_message):
    # First encryption should succeed
    encrypted1 = protocol.encrypt_packet(test_message)
    
    # Force nonce reuse by adding it to cache
    nonce = encrypted1[:protocol.NONCE_SIZE]
    protocol.nonce_cache.add(nonce)
    
    # Second encryption should fail
    with pytest.raises(SecurityException, match="Nonce reuse detected"):
        protocol.encrypt_packet(test_message)

def test_packet_size_limit(protocol, test_message):
    # Create message with large data
    large_data = {"data": "x" * 1000}  # Should exceed LoRa packet size
    large_message = LoRaMessage(
        source="node1",
        destination="node2",
        timestamp=time.time(),
        data=large_data,
        message_type="TEST",
        sequence=1
    )
    
    # Encryption should fail due to size
    with pytest.raises(SecurityException, match="Packet too large"):
        protocol.encrypt_packet(large_message)

def test_key_rotation(protocol, test_message):
    # Get initial key
    initial_key = protocol.current_key()
    
    # Force key rotation by setting last rotation time
    protocol._last_key_rotation = time.time() - protocol.key_rotation_interval - 1
    
    # Get new key after rotation
    new_key = protocol.current_key()
    
    # Keys should be different
    assert initial_key != new_key

def test_invalid_packet_decryption(protocol):
    # Try to decrypt invalid data
    invalid_data = b"invalid"
    with pytest.raises(SecurityException, match="Packet decryption error"):
        protocol.decrypt_packet(invalid_data, "node1", "node2")

def test_tampered_packet_detection(protocol, test_message):
    # Encrypt valid packet
    encrypted = protocol.encrypt_packet(test_message)
    
    # Tamper with the ciphertext
    tampered = bytearray(encrypted)
    tampered[-1] ^= 0x01  # Flip last bit
    
    # Decryption should fail
    with pytest.raises(SecurityException, match="Decryption failed"):
        protocol.decrypt_packet(
            bytes(tampered),
            test_message.source,
            test_message.destination
        )

def test_packet_size_validation(protocol):
    # Test valid size
    assert protocol.validate_packet_size(b"x" * 100)
    
    # Test invalid size
    assert not protocol.validate_packet_size(b"x" * 300)

def test_multiple_messages(protocol):
    # Create and encrypt multiple messages
    messages = []
    encrypted = []
    
    for i in range(5):
        msg = LoRaMessage(
            source=f"node{i}",
            destination=f"node{i+1}",
            timestamp=time.time(),
            data={"test": f"data{i}"},
            message_type="TEST",
            sequence=i
        )
        messages.append(msg)
        encrypted.append(protocol.encrypt_packet(msg))
        
    # Decrypt all messages
    for i, enc in enumerate(encrypted):
        dec = protocol.decrypt_packet(
            enc,
            messages[i].source,
            messages[i].destination
        )
        assert dec["data"] == messages[i].data
        assert dec["seq"] == messages[i].sequence 