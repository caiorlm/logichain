"""
Trust Core System
Self-verifying core that requires quorum approval for initialization
"""

import os
import sys
import json
import time
import hashlib
import threading
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .critical_integrity_adapter import CriticalIntegrityAdapter
from ..core.quorum import TrustedNodeQuorum, QuorumState

class TrustState(Enum):
    UNINITIALIZED = "uninitialized"
    PENDING_QUORUM = "pending_quorum"
    VERIFYING = "verifying"
    ACTIVE = "active"
    LOCKED = "locked"
    FAILED = "failed"

@dataclass
class TrustRule:
    """Represents a fundamental trust rule"""
    rule_id: str
    rule_hash: str
    code_hash: str
    quorum_required: int
    approvals: Set[str]
    last_verified: float
    
class TrustCore:
    """
    Self-verifying trust core with quorum requirements
    Cannot be modified or executed without approval
    """
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    TRUST_RULES_FILE = "trust_rules.json"
    MIN_QUORUM_NODES = 3
    APPROVAL_THRESHOLD = 0.67  # 67% approval required
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
            
    def __init__(self):
        if self._initialized:
            return
            
        self.state = TrustState.UNINITIALIZED
        self.rules: Dict[str, TrustRule] = {}
        self.quorum = TrustedNodeQuorum()
        self.integrity_adapter = CriticalIntegrityAdapter()
        self._core_hash = None
        self._initialized = True
        
    def initialize(self, trusted_nodes: List[str]) -> bool:
        """Initialize trust core with trusted nodes"""
        try:
            if self.state != TrustState.UNINITIALIZED:
                return False
                
            # Verify minimum nodes
            if len(trusted_nodes) < self.MIN_QUORUM_NODES:
                raise ValueError(
                    f"Minimum {self.MIN_QUORUM_NODES} trusted nodes required"
                )
                
            # Initialize quorum
            self.quorum.add_trusted_nodes(trusted_nodes)
            
            # Load trust rules
            self._load_trust_rules()
            
            # Calculate core hash
            self._core_hash = self._calculate_core_hash()
            
            # Update state
            self.state = TrustState.PENDING_QUORUM
            return True
            
        except Exception as e:
            print(f"Failed to initialize trust core: {e}")
            self.state = TrustState.FAILED
            return False
            
    def verify_core(self) -> bool:
        """Verify trust core integrity"""
        try:
            if self.state != TrustState.ACTIVE:
                return False
                
            # Verify core hash
            current_hash = self._calculate_core_hash()
            if current_hash != self._core_hash:
                self.state = TrustState.FAILED
                return False
                
            # Verify all rules
            for rule in self.rules.values():
                if not self._verify_rule(rule):
                    self.state = TrustState.FAILED
                    return False
                    
            return True
            
        except Exception:
            self.state = TrustState.FAILED
            return False
            
    def request_approval(self, node_id: str, signature: str) -> bool:
        """Request approval from trusted node"""
        try:
            if self.state != TrustState.PENDING_QUORUM:
                return False
                
            # Verify node is trusted
            if not self.quorum.is_trusted_node(node_id):
                return False
                
            # Verify signature
            if not self._verify_signature(node_id, signature):
                return False
                
            # Add approval to all rules
            for rule in self.rules.values():
                rule.approvals.add(node_id)
                
            # Check if we have enough approvals
            if self._check_approval_threshold():
                self.state = TrustState.VERIFYING
                if self.verify_core():
                    self.state = TrustState.ACTIVE
                    return True
                    
            return False
            
        except Exception:
            return False
            
    def enforce_rules(self) -> bool:
        """Enforce trust rules"""
        try:
            if self.state != TrustState.ACTIVE:
                return False
                
            # Verify core first
            if not self.verify_core():
                return False
                
            # Initialize integrity adapter
            if not self.integrity_adapter.enforce_integrity():
                return False
                
            # Lock system
            self.state = TrustState.LOCKED
            return True
            
        except Exception:
            self.state = TrustState.FAILED
            return False
            
    def _load_trust_rules(self):
        """Load trust rules from file"""
        try:
            rules_path = Path(__file__).parent / self.TRUST_RULES_FILE
            
            with open(rules_path) as f:
                rules_data = json.load(f)
                
            for rule_id, rule_data in rules_data.items():
                self.rules[rule_id] = TrustRule(
                    rule_id=rule_id,
                    rule_hash=rule_data["rule_hash"],
                    code_hash=rule_data["code_hash"],
                    quorum_required=rule_data["quorum_required"],
                    approvals=set(),
                    last_verified=0
                )
                
        except Exception as e:
            raise RuntimeError(f"Failed to load trust rules: {e}")
            
    def _verify_rule(self, rule: TrustRule) -> bool:
        """Verify single trust rule"""
        try:
            # Verify rule hash
            rule_hash = self._calculate_rule_hash(rule)
            if rule_hash != rule.rule_hash:
                return False
                
            # Verify code hash
            code_hash = self._calculate_code_hash(rule.rule_id)
            if code_hash != rule.code_hash:
                return False
                
            # Verify quorum
            if len(rule.approvals) < rule.quorum_required:
                return False
                
            # Update verification time
            rule.last_verified = time.time()
            return True
            
        except Exception:
            return False
            
    def _calculate_core_hash(self) -> str:
        """Calculate trust core hash"""
        hasher = hashlib.sha512()
        
        # Add rules
        rules_str = json.dumps(
            {r.rule_id: r.rule_hash for r in self.rules.values()},
            sort_keys=True
        )
        hasher.update(rules_str.encode())
        
        # Add trusted nodes
        nodes_str = json.dumps(
            sorted(self.quorum.trusted_nodes),
            sort_keys=True
        )
        hasher.update(nodes_str.encode())
        
        return hasher.hexdigest()
        
    def _calculate_rule_hash(self, rule: TrustRule) -> str:
        """Calculate hash for single rule"""
        rule_data = {
            "id": rule.rule_id,
            "code_hash": rule.code_hash,
            "quorum_required": rule.quorum_required
        }
        rule_str = json.dumps(rule_data, sort_keys=True)
        return hashlib.sha512(rule_str.encode()).hexdigest()
        
    def _calculate_code_hash(self, rule_id: str) -> str:
        """Calculate hash of rule implementation code"""
        try:
            # Get code file path
            code_file = Path(__file__).parent / f"{rule_id}.py"
            
            with open(code_file, 'rb') as f:
                content = f.read()
                
            return hashlib.sha512(content).hexdigest()
            
        except Exception:
            return ""
            
    def _verify_signature(self, node_id: str, signature: str) -> bool:
        """Verify node signature"""
        try:
            # Get node's public key
            public_key = self.quorum.get_node_key(node_id)
            if not public_key:
                return False
                
            # Create verification message
            message = f"{node_id}:{self._core_hash}"
            
            # Verify signature
            return self.quorum.verify_signature(
                message.encode(),
                signature,
                public_key
            )
            
        except Exception:
            return False
            
    def _check_approval_threshold(self) -> bool:
        """Check if we have enough approvals"""
        try:
            # Get minimum required approvals
            min_approvals = int(
                len(self.quorum.trusted_nodes) * self.APPROVAL_THRESHOLD
            )
            
            # Check each rule has enough approvals
            for rule in self.rules.values():
                if len(rule.approvals) < min_approvals:
                    return False
                    
            return True
            
        except Exception:
            return False
            
    @property
    def is_locked(self) -> bool:
        """Check if trust core is locked"""
        return self.state == TrustState.LOCKED 