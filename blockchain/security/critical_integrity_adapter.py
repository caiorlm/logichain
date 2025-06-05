"""
Critical Integrity Adapter
Enforces mandatory integrity checks during system bootstrap
Links all code to genesis block and prevents unauthorized modifications
"""

import os
import sys
import json
import hashlib
import threading
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
from .code_integrity import CodeIntegrityEnforcer
from .genesis_integrator import GenesisIntegrator

class IntegrityState(Enum):
    UNVERIFIED = "unverified"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"

@dataclass
class LayerIntegrity:
    """Represents integrity state of a code layer"""
    layer_name: str
    files: List[str]
    hash_sha512: str
    dependencies: List[str]
    state: IntegrityState
    verification_count: int
    last_verified: float

class CriticalIntegrityAdapter:
    """
    Critical Integrity Adapter
    Enforces mandatory integrity checks during system bootstrap
    Cannot be disabled or removed without breaking the system
    """
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
            
    def __init__(self):
        if self._initialized:
            return
            
        self.layers: Dict[str, LayerIntegrity] = {}
        self.original_manifest: Dict = {}
        self.enforcer = None
        self.integrator = None
        self._system_locked = False
        self._initialized = True
        
    def initialize(self, manifest_path: str, genesis_block: Dict):
        """Initialize adapter with manifest and genesis block"""
        try:
            # Load original manifest
            with open(manifest_path) as f:
                self.original_manifest = json.load(f)
                
            # Initialize integrity components
            self.enforcer = CodeIntegrityEnforcer(
                self.original_manifest["genesis_hash"]
            )
            self.integrator = GenesisIntegrator(genesis_block)
            
            # Extract layers from manifest
            for layer_name, layer_data in self.original_manifest["layers"].items():
                self.layers[layer_name] = LayerIntegrity(
                    layer_name=layer_name,
                    files=layer_data["files"],
                    hash_sha512=layer_data["hash"],
                    dependencies=layer_data["dependencies"],
                    state=IntegrityState.UNVERIFIED,
                    verification_count=0,
                    last_verified=0
                )
                
        except Exception as e:
            raise RuntimeError(f"Failed to initialize integrity adapter: {e}")
            
    def verify_layer(self, layer_name: str) -> bool:
        """Verify integrity of a single layer"""
        layer = self.layers.get(layer_name)
        if not layer:
            return False
            
        try:
            layer.state = IntegrityState.VERIFYING
            
            # Verify dependencies first
            for dep in layer.dependencies:
                if not self.verify_layer(dep):
                    layer.state = IntegrityState.FAILED
                    return False
                    
            # Calculate layer hash
            layer_hash = self._calculate_layer_hash(layer.files)
            
            # Compare with original
            if layer_hash != layer.hash_sha512:
                layer.state = IntegrityState.FAILED
                return False
                
            # Update state
            layer.state = IntegrityState.VERIFIED
            layer.verification_count += 1
            
            return True
            
        except Exception:
            layer.state = IntegrityState.FAILED
            return False
            
    def verify_all_layers(self) -> bool:
        """Verify integrity of all layers"""
        try:
            for layer_name in self.layers:
                if not self.verify_layer(layer_name):
                    return False
            return True
        except Exception:
            return False
            
    def enforce_integrity(self) -> bool:
        """Enforce integrity checks as bootstrap requirement"""
        if self._system_locked:
            return False
            
        try:
            # 1. Verify all layers
            if not self.verify_all_layers():
                self._emergency_shutdown()
                return False
                
            # 2. Verify code integrity
            if not self.enforcer.verify_all():
                self._emergency_shutdown()
                return False
                
            # 3. Verify genesis integration
            if not self.integrator.enforce_genesis_rules():
                self._emergency_shutdown()
                return False
                
            # Lock system after verification
            self._system_locked = True
            return True
            
        except Exception:
            self._emergency_shutdown()
            return False
            
    def _calculate_layer_hash(self, files: List[str]) -> str:
        """Calculate recursive SHA512 hash of layer files"""
        hasher = hashlib.sha512()
        
        for file_path in sorted(files):
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    hasher.update(content)
            except Exception:
                return ""
                
        return hasher.hexdigest()
        
    def _emergency_shutdown(self):
        """Immediate system shutdown on integrity failure"""
        print("CRITICAL INTEGRITY FAILURE - Emergency Shutdown")
        self._system_locked = True
        sys.exit(1)
        
    def get_integrity_status(self) -> Dict:
        """Get integrity status of all layers"""
        return {
            layer_name: {
                "state": layer.state.value,
                "verification_count": layer.verification_count,
                "dependencies": layer.dependencies
            }
            for layer_name, layer in self.layers.items()
        }
        
    @property
    def is_system_locked(self) -> bool:
        """Check if system is locked after verification"""
        return self._system_locked 