import pytest
import time
import asyncio
from blockchain.sync.network_sync import (
    SecureSynchronizer,
    NetworkState,
    Operation,
    NetworkMode,
    SyncResult
)

@pytest.fixture
def synchronizer():
    return SecureSynchronizer()

@pytest.fixture
def valid_operation():
    return Operation(
        op_id="test_op_1",
        node_id="node1",
        timestamp=time.time(),
        data={"test": "data"},
        signature=b"test_signature",
        public_key=b"test_public_key",
        location_history=[(40.7128, -74.0060, time.time())]
    )

@pytest.fixture
def online_state(valid_operation):
    return NetworkState(
        operations=[valid_operation],
        last_block_hash="test_block_hash",
        timestamp=time.time(),
        node_states={
            "node1": {
                "status": "active",
                "timestamp": time.time(),
                "operations": []
            }
        },
        network_mode=NetworkMode.ONLINE
    )

@pytest.fixture
def offline_state(valid_operation):
    return NetworkState(
        operations=[valid_operation],
        last_block_hash="test_block_hash",
        timestamp=time.time(),
        node_states={
            "node1": {
                "status": "active",
                "timestamp": time.time(),
                "operations": []
            }
        },
        network_mode=NetworkMode.OFFLINE
    )

@pytest.mark.asyncio
async def test_valid_sync(synchronizer, online_state, offline_state):
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert result.success
    assert result.state is not None

@pytest.mark.asyncio
async def test_invalid_network_modes(synchronizer, online_state, offline_state):
    # Set both states to same mode
    online_state.network_mode = NetworkMode.OFFLINE
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert not result.success
    assert "Invalid state format" in result.reason

@pytest.mark.asyncio
async def test_future_timestamp(synchronizer, online_state, offline_state):
    # Set future timestamp
    online_state.timestamp = time.time() + 7200  # 2 hours in future
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert not result.success
    assert "Invalid state format" in result.reason

@pytest.mark.asyncio
async def test_conflicting_operations(synchronizer, online_state, offline_state):
    # Create conflicting operation
    conflict_op = Operation(
        op_id="test_op_1",  # Same ID
        node_id="node2",
        timestamp=time.time(),
        data={"test": "different_data"},
        signature=b"different_signature",
        public_key=b"different_public_key",
        location_history=[(40.7128, -74.0060, time.time())]
    )
    
    online_state.operations = [conflict_op]
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert result.success  # Should resolve conflict
    assert len(result.state.operations) == 1  # Should have one resolved operation

@pytest.mark.asyncio
async def test_invalid_operation(synchronizer, online_state, offline_state):
    # Create invalid operation
    invalid_op = Operation(
        op_id="",  # Invalid empty ID
        node_id="node1",
        timestamp=time.time(),
        data={},
        signature=b"",
        public_key=b"",
        location_history=None
    )
    
    online_state.operations = [invalid_op]
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert not result.success
    assert "Invalid state format" in result.reason

@pytest.mark.asyncio
async def test_circuit_breaker(synchronizer, online_state, offline_state):
    # Create many operations to trigger circuit breaker
    operations = []
    for i in range(1000):
        op = Operation(
            op_id=f"test_op_{i}",
            node_id=f"node_{i % 10}",
            timestamp=time.time(),
            data={"test": f"data_{i}"},
            signature=b"sig",
            public_key=b"pub",
            location_history=[(40.7128, -74.0060, time.time())]
        )
        operations.append(op)
        
    online_state.operations = operations[:500]
    offline_state.operations = operations[500:]
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert not result.success
    assert "Circuit breaker" in result.reason

@pytest.mark.asyncio
async def test_state_merger(synchronizer, online_state, offline_state):
    # Add different operations to each state
    op1 = Operation(
        op_id="test_op_1",
        node_id="node1",
        timestamp=time.time(),
        data={"test": "data1"},
        signature=b"sig1",
        public_key=b"pub1",
        location_history=[(40.7128, -74.0060, time.time())]
    )
    
    op2 = Operation(
        op_id="test_op_2",
        node_id="node2",
        timestamp=time.time(),
        data={"test": "data2"},
        signature=b"sig2",
        public_key=b"pub2",
        location_history=[(40.7129, -74.0061, time.time())]
    )
    
    online_state.operations = [op1]
    offline_state.operations = [op2]
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert result.success
    assert len(result.state.operations) == 2  # Should have both operations

@pytest.mark.asyncio
async def test_invalid_location_history(synchronizer, online_state, offline_state):
    # Create operation with invalid location history
    invalid_op = Operation(
        op_id="test_op_3",
        node_id="node3",
        timestamp=time.time(),
        data={"test": "data3"},
        signature=b"sig3",
        public_key=b"pub3",
        location_history=[(100.0, 200.0, time.time())]  # Invalid coordinates
    )
    
    online_state.operations = [invalid_op]
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert not result.success
    assert "Invalid state format" in result.reason

@pytest.mark.asyncio
async def test_node_state_merger(synchronizer, online_state, offline_state):
    # Add different node states
    online_state.node_states["node2"] = {
        "status": "active",
        "timestamp": time.time(),
        "operations": []
    }
    
    offline_state.node_states["node3"] = {
        "status": "active",
        "timestamp": time.time(),
        "operations": []
    }
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert result.success
    assert len(result.state.node_states) == 3  # Should have all node states

@pytest.mark.asyncio
async def test_timestamp_based_resolution(synchronizer, online_state, offline_state):
    # Create operations with different timestamps
    op1 = Operation(
        op_id="test_op_1",
        node_id="node1",
        timestamp=time.time() - 3600,  # 1 hour ago
        data={"test": "old_data"},
        signature=b"sig1",
        public_key=b"pub1",
        location_history=[(40.7128, -74.0060, time.time() - 3600)]
    )
    
    op2 = Operation(
        op_id="test_op_1",  # Same ID
        node_id="node1",
        timestamp=time.time(),  # Current time
        data={"test": "new_data"},
        signature=b"sig2",
        public_key=b"pub2",
        location_history=[(40.7128, -74.0060, time.time())]
    )
    
    online_state.operations = [op1]
    offline_state.operations = [op2]
    
    result = await synchronizer.sync_networks(online_state, offline_state)
    assert result.success
    assert len(result.state.operations) == 1
    assert result.state.operations[0].data["test"] == "new_data"  # Should keep newer version 