"""
Security configuration
"""

class SecurityConfig:
    """Security configuration"""
    
    def __init__(self):
        # Network timing
        self.ping_interval = 60  # Ping peers every 60 seconds
        self.sync_interval = 300  # Sync chain every 5 minutes
        
        # Security parameters
        self.min_peers = 3
        self.max_peers = 100
        self.max_connections = 50
        self.connection_timeout = 10
        self.handshake_timeout = 5
        self.max_message_size = 1024 * 1024  # 1MB
        
        # Cryptographic parameters
        self.key_size = 2048
        self.hash_algorithm = 'sha256'
        self.signature_algorithm = 'ed25519'
        
        # Trust parameters
        self.trust_threshold = 0.8
        self.max_trust_score = 100
        self.min_trust_score = -100
        self.initial_trust_score = 0 