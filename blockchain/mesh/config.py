"""
LogiChain Mesh Configuration
Configuração da rede mesh
"""

from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class MeshConfig:
    """Configuração da rede mesh"""
    
    # Parâmetros da rede
    NETWORK_ID: str = "logichain_mainnet"
    CHAIN_ID: int = 1337
    MAX_PEERS: int = 10
    MIN_PEERS: int = 3
    
    # Intervalos de sincronização
    SYNC_INTERVAL: int = 300  # 5 minutos
    CLEANUP_INTERVAL: int = 3600  # 1 hora
    HANDSHAKE_TIMEOUT: int = 30  # 30 segundos
    
    # Limites de armazenamento
    MAX_PENDING_TXS: int = 10000
    MAX_PENDING_BLOCKS: int = 1000
    MAX_PENDING_CONTRACTS: int = 1000
    MAX_PENDING_VALIDATIONS: int = 1000
    
    # Parâmetros de nós bridge
    MIN_BRIDGE_STAKE: float = 50000.0
    MIN_BRIDGE_UPTIME: float = 0.95  # 95% uptime
    MAX_BRIDGE_LATENCY: int = 1000  # 1 segundo
    
    # Parâmetros LoRa
    LORA_ENABLED: bool = True
    LORA_FREQUENCY: int = 915000000  # 915MHz
    LORA_BANDWIDTH: int = 125000  # 125kHz
    LORA_SPREADING_FACTOR: int = 7
    LORA_CODING_RATE: int = 5
    LORA_POWER: int = 20  # dBm
    LORA_SYNC_WORD: int = 0x12
    
    # Parâmetros de validação
    VALIDATION_THRESHOLD: float = 0.67  # 67% dos validadores
    MIN_VALIDATORS: int = 3
    MAX_VALIDATION_TIME: int = 60  # 1 minuto
    
    # Parâmetros de estado
    STATE_SNAPSHOT_INTERVAL: int = 1800  # 30 minutos
    MAX_STATE_SIZE: int = 100 * 1024 * 1024  # 100MB
    STATE_BACKUP_COUNT: int = 3
    
    # Parâmetros de segurança
    MIN_STAKE: float = 1000.0
    MAX_OFFLINE_TIME: int = 86400  # 24 horas
    MAX_CLOCK_DRIFT: int = 300  # 5 minutos
    
    def __init__(self, **kwargs):
        """Inicializa com valores customizados"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                
    @classmethod
    def from_dict(cls, config_dict: Dict) -> 'MeshConfig':
        """Cria configuração a partir de dicionário"""
        return cls(**config_dict)
        
    def to_dict(self) -> Dict:
        """Converte configuração para dicionário"""
        return {
            key: getattr(self, key)
            for key in self.__annotations__
        }
        
    def validate(self) -> bool:
        """Valida configuração"""
        try:
            # Valida intervalos
            assert self.SYNC_INTERVAL > 0
            assert self.CLEANUP_INTERVAL > 0
            assert self.HANDSHAKE_TIMEOUT > 0
            
            # Valida limites
            assert self.MAX_PENDING_TXS > 0
            assert self.MAX_PENDING_BLOCKS > 0
            assert self.MAX_PENDING_CONTRACTS > 0
            assert self.MAX_PENDING_VALIDATIONS > 0
            
            # Valida parâmetros de nós
            assert self.MIN_BRIDGE_STAKE > 0
            assert 0 < self.MIN_BRIDGE_UPTIME <= 1
            assert self.MAX_BRIDGE_LATENCY > 0
            
            # Valida parâmetros LoRa
            if self.LORA_ENABLED:
                assert 860000000 <= self.LORA_FREQUENCY <= 1020000000
                assert self.LORA_BANDWIDTH in [125000, 250000, 500000]
                assert 6 <= self.LORA_SPREADING_FACTOR <= 12
                assert 5 <= self.LORA_CODING_RATE <= 8
                assert 2 <= self.LORA_POWER <= 20
                
            # Valida parâmetros de validação
            assert 0 < self.VALIDATION_THRESHOLD <= 1
            assert self.MIN_VALIDATORS > 0
            assert self.MAX_VALIDATION_TIME > 0
            
            # Valida parâmetros de estado
            assert self.STATE_SNAPSHOT_INTERVAL > 0
            assert self.MAX_STATE_SIZE > 0
            assert self.STATE_BACKUP_COUNT > 0
            
            # Valida parâmetros de segurança
            assert self.MIN_STAKE > 0
            assert self.MAX_OFFLINE_TIME > 0
            assert self.MAX_CLOCK_DRIFT > 0
            
            return True
            
        except AssertionError:
            return False
            
    def merge(self, other: 'MeshConfig') -> 'MeshConfig':
        """Combina duas configurações"""
        merged_dict = self.to_dict()
        other_dict = other.to_dict()
        
        for key in merged_dict:
            if key in other_dict and other_dict[key] is not None:
                merged_dict[key] = other_dict[key]
                
        return MeshConfig.from_dict(merged_dict)
        
# Configuração padrão
DEFAULT_CONFIG = MeshConfig()

def load_config(config_dict: Optional[Dict] = None) -> MeshConfig:
    """Carrega configuração"""
    if config_dict:
        custom_config = MeshConfig.from_dict(config_dict)
        return DEFAULT_CONFIG.merge(custom_config)
    return DEFAULT_CONFIG 