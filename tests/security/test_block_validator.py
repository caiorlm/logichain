import pytest
import time
import hashlib
from blockchain.core.block_validator import (
    EnhancedBlockValidator,
    Block,
    Transaction,
    ChainContext,
    NetworkMode,
    ValidationResult
)

@pytest.fixture
def validator():
    return EnhancedBlockValidator()

@pytest.fixture
def valid_transaction():
    return Transaction(
        tx_id="test_tx_1",
        sender="sender1",
        receiver="receiver1",
        amount=100.0,
        timestamp=time.time(),
        signature=b"test_signature",
        public_key=b"test_public_key",
        dependencies=[]
    )

@pytest.fixture
def valid_block(valid_transaction):
    current_time = time.time()
    
    # Create block with valid PoW
    nonce = 0
    while True:
        block = Block(
            version=1,
            previous_hash="test_prev_hash",
            merkle_root="test_merkle_root",
            timestamp=current_time,
            difficulty=10,
            nonce=nonce,
            transactions=[valid_transaction],
            quorum_sigs=[b"sig1", b"sig2", b"sig3"]
        )
        
        # Check if block meets difficulty requirement
        header = (
            f"{block.version}{block.previous_hash}{block.merkle_root}"
            f"{block.timestamp}{block.difficulty}{block.nonce}"
        ).encode()
        block_hash = hashlib.sha256(header).hexdigest()
        if int(block_hash, 16) < 2 ** (256 - block.difficulty):
            break
            
        nonce += 1
        
    return block

@pytest.fixture
def chain_context():
    return ChainContext(
        difficulty=10,
        last_block=None,
        current_state={"sender1": 1000.0, "receiver1": 0.0},
        trusted_nodes={b"sig1", b"sig2", b"sig3"},
        fork_choice_rule="LONGEST_CHAIN",
        network_mode=NetworkMode.ONLINE
    )

def test_valid_block_online(validator, valid_block, chain_context):
    result = validator.validate_block(valid_block, chain_context)
    assert result.valid
    assert not result.reason

def test_valid_block_offline(validator, valid_block, chain_context):
    # Remove quorum signatures for offline mode
    valid_block.quorum_sigs = None
    chain_context.network_mode = NetworkMode.OFFLINE
    
    result = validator.validate_block(valid_block, chain_context)
    assert result.valid
    assert not result.reason

def test_invalid_pow(validator, valid_block, chain_context):
    # Modify nonce to invalidate PoW
    valid_block.nonce += 1
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "proof of work" in result.reason.lower()

def test_future_timestamp(validator, valid_block, chain_context):
    # Set block timestamp to future
    valid_block.timestamp = time.time() + 7200  # 2 hours in future
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "temporal order" in result.reason.lower()

def test_invalid_merkle_root(validator, valid_block, chain_context):
    # Modify merkle root
    valid_block.merkle_root = "invalid_merkle_root"
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "merkle root" in result.reason.lower()

def test_transaction_cycle(validator, valid_block, chain_context):
    # Create transactions with cyclic dependencies
    tx1 = Transaction(
        tx_id="tx1",
        sender="sender1",
        receiver="receiver1",
        amount=50.0,
        timestamp=time.time(),
        signature=b"sig1",
        public_key=b"pub1",
        dependencies=["tx2"]
    )
    
    tx2 = Transaction(
        tx_id="tx2",
        sender="sender2",
        receiver="receiver2",
        amount=50.0,
        timestamp=time.time(),
        signature=b"sig2",
        public_key=b"pub2",
        dependencies=["tx1"]
    )
    
    valid_block.transactions = [tx1, tx2]
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "cycle" in result.reason.lower()

def test_missing_quorum_online(validator, valid_block, chain_context):
    # Remove quorum signatures in online mode
    valid_block.quorum_sigs = None
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "quorum" in result.reason.lower()

def test_invalid_quorum_signatures(validator, valid_block, chain_context):
    # Use untrusted signatures
    valid_block.quorum_sigs = [b"untrusted1", b"untrusted2", b"untrusted3"]
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "quorum" in result.reason.lower()

def test_invalid_state_transition(validator, valid_block, chain_context):
    # Create transaction with insufficient balance
    tx = Transaction(
        tx_id="test_tx_2",
        sender="sender1",
        receiver="receiver1",
        amount=2000.0,  # More than sender's balance
        timestamp=time.time(),
        signature=b"test_signature",
        public_key=b"test_public_key",
        dependencies=[]
    )
    
    valid_block.transactions = [tx]
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "state" in result.reason.lower()

def test_block_size_limit_online(validator, valid_block, chain_context):
    # Create many transactions to exceed online block size
    transactions = []
    for i in range(validator.MAX_TX_COUNT_ONLINE + 1):
        tx = Transaction(
            tx_id=f"tx_{i}",
            sender="sender1",
            receiver="receiver1",
            amount=1.0,
            timestamp=time.time(),
            signature=b"sig",
            public_key=b"pub",
            dependencies=[]
        )
        transactions.append(tx)
        
    valid_block.transactions = transactions
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "transaction count" in result.reason.lower()

def test_block_size_limit_offline(validator, valid_block, chain_context):
    # Create many transactions to exceed offline block size
    chain_context.network_mode = NetworkMode.OFFLINE
    valid_block.quorum_sigs = None
    
    transactions = []
    for i in range(validator.MAX_TX_COUNT_OFFLINE + 1):
        tx = Transaction(
            tx_id=f"tx_{i}",
            sender="sender1",
            receiver="receiver1",
            amount=1.0,
            timestamp=time.time(),
            signature=b"sig",
            public_key=b"pub",
            dependencies=[]
        )
        transactions.append(tx)
        
    valid_block.transactions = transactions
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "transaction count" in result.reason.lower()

def test_temporal_order_with_previous_block(validator, valid_block, chain_context):
    # Create previous block with future timestamp
    prev_block = Block(
        version=1,
        previous_hash="old_prev_hash",
        merkle_root="old_merkle_root",
        timestamp=valid_block.timestamp + 1,  # Future timestamp
        difficulty=10,
        nonce=0,
        transactions=[],
        quorum_sigs=[b"sig1", b"sig2", b"sig3"]
    )
    
    chain_context.last_block = prev_block
    
    result = validator.validate_block(valid_block, chain_context)
    assert not result.valid
    assert "temporal order" in result.reason.lower() 