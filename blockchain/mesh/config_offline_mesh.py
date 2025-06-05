"""
LogiChain Offline Mesh Configuration
Configuration settings for offline mesh network
"""

import os
import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class LoRaConfig:
    """LoRa radio configuration"""
    port: Optional[str] = None
    baudrate: int = 9600
    timeout: int = 1
    retry_interval: int = 5
    max_retries: int = 3
    frequency: int = 915000000  # 915MHz
    spreading_factor: int = 7
    bandwidth: int = 125  # kHz
    tx_power: int = 20  # dBm
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoRaConfig":
        """Create from dictionary"""
        return cls(**data)

@dataclass
class NetworkConfig:
    """Mesh network configuration"""
    discovery_interval: int = 30  # seconds
    node_timeout: int = 300  # seconds
    sync_interval: int = 60  # seconds
    max_peers: int = 10
    bridge_threshold: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NetworkConfig":
        """Create from dictionary"""
        return cls(**data)

@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_encryption: bool = True
    enable_signature: bool = True
    key_size: int = 2048
    hash_algorithm: str = "sha256"
    signature_algorithm: str = "rsa-pss"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityConfig":
        """Create from dictionary"""
        return cls(**data)

@dataclass
class LoggingConfig:
    """Logging configuration"""
    log_dir: str = "logs"
    log_file: str = "mesh_activity.log"
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingConfig":
        """Create from dictionary"""
        return cls(**data)

@dataclass
class VisualizerConfig:
    """Visualizer configuration"""
    host: str = "localhost"
    port: int = 8765
    update_interval: int = 5  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualizerConfig":
        """Create from dictionary"""
        return cls(**data)

class OfflineMeshConfig:
    """Offline mesh network configuration"""
    
    def __init__(
        self,
        config_file: Optional[str] = None,
        is_bridge: bool = False,
        location: Optional[str] = None
    ):
        self.config_file = config_file or "config/mesh_config.json"
        self.is_bridge = is_bridge
        self.location = location
        
        # Initialize components
        self.lora = LoRaConfig()
        self.network = NetworkConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.visualizer = VisualizerConfig()
        
        # Load configuration
        self.load_config()
        
    def load_config(self):
        """Load configuration from file"""
        try:
            config_path = Path(self.config_file)
            
            if config_path.exists():
                with open(config_path, "r") as f:
                    data = json.load(f)
                    
                # Load component configs
                if "lora" in data:
                    self.lora = LoRaConfig.from_dict(data["lora"])
                if "network" in data:
                    self.network = NetworkConfig.from_dict(data["network"])
                if "security" in data:
                    self.security = SecurityConfig.from_dict(data["security"])
                if "logging" in data:
                    self.logging = LoggingConfig.from_dict(data["logging"])
                if "visualizer" in data:
                    self.visualizer = VisualizerConfig.from_dict(data["visualizer"])
                    
                # Load other settings
                self.is_bridge = data.get("is_bridge", self.is_bridge)
                self.location = data.get("location", self.location)
                
                logger.info(f"Loaded configuration from {config_path}")
                
        except Exception as e:
            logger.warning(f"Failed to load configuration: {str(e)}")
            logger.info("Using default configuration")
            
    def save_config(self):
        """Save configuration to file"""
        try:
            # Create config directory
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create config data
            data = {
                "lora": self.lora.to_dict(),
                "network": self.network.to_dict(),
                "security": self.security.to_dict(),
                "logging": self.logging.to_dict(),
                "visualizer": self.visualizer.to_dict(),
                "is_bridge": self.is_bridge,
                "location": self.location
            }
            
            # Save to file
            with open(config_path, "w") as f:
                json.dump(data, f, indent=4)
                
            logger.info(f"Saved configuration to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            
    def update_config(self, config_data: Dict[str, Any]):
        """Update configuration with new data"""
        try:
            # Update component configs
            if "lora" in config_data:
                self.lora = LoRaConfig.from_dict(config_data["lora"])
            if "network" in config_data:
                self.network = NetworkConfig.from_dict(config_data["network"])
            if "security" in config_data:
                self.security = SecurityConfig.from_dict(config_data["security"])
            if "logging" in config_data:
                self.logging = LoggingConfig.from_dict(config_data["logging"])
            if "visualizer" in config_data:
                self.visualizer = VisualizerConfig.from_dict(config_data["visualizer"])
                
            # Update other settings
            if "is_bridge" in config_data:
                self.is_bridge = config_data["is_bridge"]
            if "location" in config_data:
                self.location = config_data["location"]
                
            # Save updated config
            self.save_config()
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {str(e)}")
            
    def get_config(self) -> Dict[str, Any]:
        """Get complete configuration"""
        return {
            "lora": self.lora.to_dict(),
            "network": self.network.to_dict(),
            "security": self.security.to_dict(),
            "logging": self.logging.to_dict(),
            "visualizer": self.visualizer.to_dict(),
            "is_bridge": self.is_bridge,
            "location": self.location
        }
        
    def validate_config(self) -> bool:
        """Validate configuration settings"""
        try:
            # Validate LoRa config
            if self.lora.frequency < 850000000 or self.lora.frequency > 930000000:
                logger.warning("Invalid LoRa frequency")
                return False
                
            if self.lora.spreading_factor < 6 or self.lora.spreading_factor > 12:
                logger.warning("Invalid spreading factor")
                return False
                
            if self.lora.bandwidth not in [125, 250, 500]:
                logger.warning("Invalid bandwidth")
                return False
                
            if self.lora.tx_power < 0 or self.lora.tx_power > 20:
                logger.warning("Invalid TX power")
                return False
                
            # Validate network config
            if self.network.discovery_interval < 5:
                logger.warning("Discovery interval too short")
                return False
                
            if self.network.node_timeout < self.network.discovery_interval * 2:
                logger.warning("Node timeout too short")
                return False
                
            if self.network.max_peers < self.network.bridge_threshold:
                logger.warning("Max peers less than bridge threshold")
                return False
                
            # Validate security config
            if self.security.key_size < 2048:
                logger.warning("Key size too small")
                return False
                
            if self.security.hash_algorithm not in ["sha256", "sha384", "sha512"]:
                logger.warning("Invalid hash algorithm")
                return False
                
            # Validate logging config
            if self.logging.max_size < 1024 * 1024:  # 1MB
                logger.warning("Log file size too small")
                return False
                
            if self.logging.backup_count < 1:
                logger.warning("Invalid backup count")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            return False 