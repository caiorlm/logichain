"""
Genesis Block Integration System
Links code integrity to genesis block and enforces rules
"""

import os
import hashlib
import json
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path
from .code_integrity import CodeIntegrityEnforcer, CodeHash

@dataclass
class GenesisRule:
    """Represents a fundamental rule from genesis"""
    rule_id: str
    rule_type: str
    rule_hash: str
    parameters: Dict
    enforced_modules: List[str]
    
class GenesisIntegrator:
    """Integrates code integrity with genesis block"""
    
    def __init__(self, genesis_block: Dict):
        self.genesis_block = genesis_block
        self.genesis_hash = self._calculate_genesis_hash()
        self.enforcer = CodeIntegrityEnforcer(self.genesis_hash)
        self.rules: Dict[str, GenesisRule] = {}
        self.rule_violations: List[Dict] = []
        
        # Extract rules from genesis
        self._extract_genesis_rules()
        
    def _calculate_genesis_hash(self) -> str:
        """Calculate deterministic genesis hash"""
        # Sort genesis block for deterministic hash
        genesis_str = json.dumps(self.genesis_block, sort_keys=True)
        
        # Double SHA256 for genesis hash
        first_hash = hashlib.sha256(genesis_str.encode()).digest()
        final_hash = hashlib.sha256(first_hash).hexdigest()
        
        return final_hash
        
    def _extract_genesis_rules(self):
        """Extract fundamental rules from genesis block"""
        rules_data = self.genesis_block.get("rules", {})
        
        for rule_id, rule_data in rules_data.items():
            # Calculate rule hash
            rule_str = json.dumps(rule_data, sort_keys=True)
            rule_hash = hashlib.sha512(rule_str.encode()).hexdigest()
            
            rule = GenesisRule(
                rule_id=rule_id,
                rule_type=rule_data["type"],
                rule_hash=rule_hash,
                parameters=rule_data["parameters"],
                enforced_modules=rule_data["modules"]
            )
            
            self.rules[rule_id] = rule
            
    def integrate_module(self, module_path: str) -> bool:
        """Integrate module with genesis rules"""
        try:
            # Register module with enforcer
            if not self.enforcer.register_module(module_path):
                return False
                
            # Find applicable rules
            applicable_rules = self._get_applicable_rules(module_path)
            
            # Verify module against rules
            for rule in applicable_rules:
                if not self._verify_rule_compliance(module_path, rule):
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def _get_applicable_rules(self, module_path: str) -> List[GenesisRule]:
        """Get rules applicable to module"""
        module_name = Path(module_path).stem
        
        return [
            rule for rule in self.rules.values()
            if module_name in rule.enforced_modules
        ]
        
    def _verify_rule_compliance(
        self,
        module_path: str,
        rule: GenesisRule
    ) -> bool:
        """Verify module complies with genesis rule"""
        try:
            # Get module hash
            code_hash = self.enforcer.code_hashes[module_path]
            
            # Create rule verification hash
            verification_data = {
                "module": module_path,
                "rule": rule.rule_id,
                "code_sha256": code_hash.hash_sha256,
                "code_sha512": code_hash.hash_sha512,
                "genesis": self.genesis_hash,
                "parameters": rule.parameters
            }
            
            # Calculate verification hash
            verify_str = json.dumps(verification_data, sort_keys=True)
            verify_hash = hashlib.sha512(verify_str.encode()).hexdigest()
            
            # Compare with rule hash
            if verify_hash != rule.rule_hash:
                self._record_violation(module_path, rule)
                return False
                
            return True
            
        except Exception:
            return False
            
    def _record_violation(self, module_path: str, rule: GenesisRule):
        """Record a rule violation"""
        violation = {
            "timestamp": time.time(),
            "module": module_path,
            "rule": rule.rule_id,
            "type": "rule_violation"
        }
        self.rule_violations.append(violation)
        
    def verify_codebase(self, root_dir: str) -> Dict[str, bool]:
        """Verify entire codebase against genesis"""
        results = {}
        
        # Hash all Python files
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    results[path] = self.integrate_module(path)
                    
        return results
        
    def export_integration_proof(self, output_file: str):
        """Export integration proof"""
        proof = {
            "genesis_hash": self.genesis_hash,
            "timestamp": time.time(),
            "rules": {
                rule_id: {
                    "hash": rule.rule_hash,
                    "type": rule.rule_type,
                    "modules": rule.enforced_modules
                }
                for rule_id, rule in self.rules.items()
            },
            "violations": self.rule_violations,
            "integrity": self.enforcer.get_integrity_status()
        }
        
        with open(output_file, 'w') as f:
            json.dump(proof, f, indent=2)
            
    def get_violation_report(self) -> List[Dict]:
        """Get detailed violation report"""
        return self.rule_violations
        
    def enforce_genesis_rules(self) -> bool:
        """Enforce all genesis rules"""
        try:
            # Verify code integrity
            if not self.enforcer.verify_all():
                return False
                
            # Verify all modules against rules
            for module in self.enforcer.code_hashes.keys():
                if not self.integrate_module(module):
                    return False
                    
            return True
            
        except Exception:
            return False
            
    @classmethod
    def create_from_proof(
        cls,
        genesis_block: Dict,
        proof_file: str
    ) -> 'GenesisIntegrator':
        """Create integrator from existing proof"""
        integrator = cls(genesis_block)
        
        with open(proof_file) as f:
            proof = json.load(f)
            
        # Verify proof matches genesis
        if proof["genesis_hash"] != integrator.genesis_hash:
            raise ValueError("Proof does not match genesis block")
            
        # Load integrity status
        for module, status in proof["integrity"].items():
            code_hash = CodeHash(
                file_path=module,
                hash_sha256=status["sha256"],
                hash_sha512=status["sha512"],
                combined_hash=status["combined"],
                timestamp=time.time(),
                last_verified=status["last_verified"],
                verification_count=status["verification_count"],
                dependencies=status["dependencies"]
            )
            integrator.enforcer.code_hashes[module] = code_hash
            
        # Load violations
        integrator.rule_violations = proof["violations"]
        
        return integrator 