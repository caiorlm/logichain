from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SecurityConfig:
    """Configurações de segurança"""
    key_size: int = 2048
    hash_algorithm: str = "sha256"
    signature_algorithm: str = "ecdsa"
    key_dir: str = "keys"
    trusted_nodes: List[str] = None
    min_peers: int = 3
    max_peers: int = 10
    connection_timeout: int = 30
    keep_alive_interval: int = 60
    max_retries: int = 3
    
    def __post_init__(self):
        if self.trusted_nodes is None:
            self.trusted_nodes = [] 