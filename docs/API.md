# LogiChain API Documentation

## Overview

LogiChain is a blockchain system specialized for logistics and supply chain management. This document describes the APIs and protocols used in the system.

## Network Protocols

### NAT Traversal

The NAT traversal protocol enables peer-to-peer connectivity through NAT devices using STUN servers and hole punching techniques.

#### STUN Protocol
- Uses standard STUN servers for NAT type discovery
- Supports multiple fallback servers
- Implements keep-alive mechanism

#### Hole Punching
- Creates multiple UDP ports for connectivity
- Maintains connection through periodic keep-alive messages
- Handles connection recovery automatically

### Gossip Protocol

The gossip protocol manages peer-to-peer message propagation across the network.

#### Message Types
- `BLOCK`: New block announcements
- `TRANSACTION`: New transaction broadcasts
- `PEER_DISCOVERY`: Network topology updates
- `SYNC_REQUEST`: Block synchronization requests
- `SYNC_RESPONSE`: Block synchronization responses
- `FALLBACK_REQUEST`: Message recovery requests
- `FALLBACK_RESPONSE`: Message recovery responses
- `ACK`: Message acknowledgments

#### Message Format
```json
{
    "type": "MessageType",
    "payload": {},
    "sender": "node_id",
    "timestamp": 1234567890.123,
    "message_id": "hash",
    "ttl": 3,
    "signature": "hex_signature"
}
```

### Synchronization Protocol

The synchronization protocol ensures consistency across the network.

#### Session Management
- Unique session IDs per sync request
- Timeout handling
- Retry mechanism
- Partial block sync support

#### Recovery Process
1. Missing block detection
2. Peer selection
3. Block request
4. Validation
5. Integration

## DAG Management

### Node Types
- `BLOCK`: Regular transaction blocks
- `CHECKPOINT`: Consensus checkpoints
- `MERGE`: Fork resolution blocks

### Node Structure
```json
{
    "node_id": "hash",
    "node_type": "NodeType",
    "parents": ["parent_hashes"],
    "timestamp": 1234567890.123,
    "data": {},
    "signature": "hex_signature",
    "height": 10,
    "weight": 1.5
}
```

### Consensus Rules
1. Temporal ordering
2. Parent validation
3. Signature verification
4. Fork detection
5. Weight calculation

## Metrics and Monitoring

### Network Metrics
- Messages sent/received
- Message latency
- Active peers
- Failed messages

### DAG Metrics
- Total nodes
- Tips count
- Fork points
- Suspicious nodes
- Validation time

### Sync Metrics
- Active sessions
- Blocks synced
- Sync failures
- Sync latency

## Security

### Node Authentication
- ECDSA signatures using SECP256K1
- Per-node key pairs
- Message signing and verification

### Fork Protection
- Suspicious node detection
- Fork point tracking
- Weight-based resolution

### Anti-spam Measures
- Message TTL
- Rate limiting
- Validation requirements

## REST API Endpoints

### Node Management

#### GET /node/status
Returns node status information.

Response:
```json
{
    "node_id": "string",
    "uptime": 123456,
    "peers": 10,
    "blocks": 1000,
    "sync_status": "string"
}
```

#### GET /node/metrics
Returns node metrics.

Response:
```json
{
    "network": {
        "messages_sent": 1000,
        "messages_received": 950,
        "active_peers": 10,
        "failed_messages": 50
    },
    "dag": {
        "nodes": 1000,
        "tips": 5,
        "forks": 2,
        "suspicious": 1
    },
    "sync": {
        "active_sessions": 2,
        "blocks_synced": 100,
        "failures": 5
    }
}
```

### Block Management

#### POST /block/submit
Submits a new block to the network.

Request:
```json
{
    "type": "BLOCK",
    "parents": ["hashes"],
    "data": {},
    "signature": "hex"
}
```

Response:
```json
{
    "success": true,
    "block_id": "hash",
    "timestamp": 1234567890.123
}
```

#### GET /block/{block_id}
Returns information about a specific block.

Response:
```json
{
    "node_id": "hash",
    "type": "BLOCK",
    "parents": ["hashes"],
    "timestamp": 1234567890.123,
    "data": {},
    "signature": "hex",
    "height": 10,
    "weight": 1.5
}
```

### Network Management

#### GET /network/peers
Returns list of connected peers.

Response:
```json
{
    "peers": [
        {
            "node_id": "string",
            "address": "ip:port",
            "nat_type": "string",
            "uptime": 123456
        }
    ]
}
```

#### POST /network/connect
Connects to a new peer.

Request:
```json
{
    "address": "ip:port"
}
```

Response:
```json
{
    "success": true,
    "peer_id": "string"
}
```

## Error Handling

All API endpoints use standard HTTP status codes and return error details in the following format:

```json
{
    "error": true,
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": {}
}
```

Common error codes:
- `INVALID_REQUEST`: Malformed request
- `VALIDATION_ERROR`: Invalid data
- `NOT_FOUND`: Resource not found
- `NETWORK_ERROR`: Network-related error
- `SYNC_ERROR`: Synchronization error
- `INTERNAL_ERROR`: Internal server error 