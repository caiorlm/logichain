"""
Prometheus metrics configuration for LogiChain
"""
from prometheus_client import Counter, Gauge, Histogram, Info
import time

# Network metrics
PEER_COUNT = Gauge('logichain_peer_count', 'Number of connected peers')
MESSAGE_COUNT = Counter('logichain_message_count_total', 'Total number of P2P messages', ['type'])
NETWORK_LATENCY = Histogram('logichain_network_latency_seconds', 'Network message latency')

# Blockchain metrics
BLOCK_HEIGHT = Gauge('logichain_block_height', 'Current blockchain height')
TRANSACTION_COUNT = Counter('logichain_transaction_count_total', 'Total number of transactions')
BLOCK_TIME = Histogram('logichain_block_time_seconds', 'Time between blocks')

# Consensus metrics
CONSENSUS_ROUNDS = Counter('logichain_consensus_rounds_total', 'Total number of consensus rounds')
CONSENSUS_FAILURES = Counter('logichain_consensus_failures_total', 'Number of consensus failures')
VALIDATOR_COUNT = Gauge('logichain_validator_count', 'Number of active validators')

# Security metrics
SECURITY_EVENTS = Counter('logichain_security_events_total', 'Security events', ['type'])
BANNED_PEERS = Gauge('logichain_banned_peers', 'Number of banned peers')

# System metrics
MEMORY_USAGE = Gauge('logichain_memory_bytes', 'Memory usage in bytes')
CPU_USAGE = Gauge('logichain_cpu_percent', 'CPU usage percentage')
DISK_USAGE = Gauge('logichain_disk_bytes', 'Disk usage in bytes')

# Node info
NODE_INFO = Info('logichain_node', 'Node information')

def init_metrics(node_id: str, network: str):
    """Initialize metrics with node information"""
    NODE_INFO.info({
        'node_id': node_id,
        'network': network,
        'version': '0.1.0',
        'start_time': str(int(time.time()))
    })

def update_system_metrics(memory_bytes: int, cpu_percent: float, disk_bytes: int):
    """Update system resource metrics"""
    MEMORY_USAGE.set(memory_bytes)
    CPU_USAGE.set(cpu_percent)
    DISK_USAGE.set(disk_bytes)

def record_network_message(msg_type: str, latency: float):
    """Record network message metrics"""
    MESSAGE_COUNT.labels(type=msg_type).inc()
    NETWORK_LATENCY.observe(latency)

def record_consensus_event(success: bool):
    """Record consensus round metrics"""
    CONSENSUS_ROUNDS.inc()
    if not success:
        CONSENSUS_FAILURES.inc()

def record_security_event(event_type: str):
    """Record security event metrics"""
    SECURITY_EVENTS.labels(type=event_type).inc()

def update_blockchain_metrics(height: int, tx_count: int, block_time: float):
    """Update blockchain metrics"""
    BLOCK_HEIGHT.set(height)
    TRANSACTION_COUNT.inc(tx_count)
    BLOCK_TIME.observe(block_time) 