"""
Code Integrity and Executable Enforcement System
Links all code execution and validation to genesis block
"""

import os
import hashlib
import json
import time
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

class HashAlgorithm(Enum):
    SHA256 = "sha256"
    SHA512 = "sha512"
    DOUBLE_SHA256 = "double_sha256"
    COMBINED = "combined"  # SHA512(SHA256)

@dataclass
class CodeHash:
    """Represents a code hash with metadata"""
    file_path: str
    hash_sha256: str
    hash_sha512: str
    combined_hash: str  # SHA512(SHA256)
    timestamp: float
    last_verified: float
    verification_count: int
    dependencies: List[str]
    
class CodeIntegrityEnforcer:
    """Enforces code integrity linked to genesis block"""
    
    def __init__(self, genesis_hash: str):
        self.genesis_hash = genesis_hash
        self.code_hashes: Dict[str, CodeHash] = {}
        self.execution_hashes: Dict[str, str] = {}
        self.verified_modules: Set[str] = set()
        self.enforcing = True
        
        # Thread pool for parallel verification
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def calculate_file_hashes(self, file_path: str) -> CodeHash:
        """Calculate all hashes for a file"""
        with open(file_path, 'rb') as f:
            content = f.read()
            
        # Calculate SHA256
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        # Calculate SHA512
        sha512_hash = hashlib.sha512(content).hexdigest()
        
        # Calculate combined (SHA512(SHA256))
        combined = hashlib.sha512(sha256_hash.encode()).hexdigest()
        
        # Get dependencies
        dependencies = self._extract_dependencies(content.decode())
        
        return CodeHash(
            file_path=file_path,
            hash_sha256=sha256_hash,
            hash_sha512=sha512_hash,
            combined_hash=combined,
            timestamp=time.time(),
            last_verified=time.time(),
            verification_count=1,
            dependencies=dependencies
        )
        
    def hash_directory(self, directory: str) -> Dict[str, CodeHash]:
        """Hash all Python files in directory recursively"""
        hashes = {}
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    hashes[path] = self.calculate_file_hashes(path)
        return hashes
        
    def verify_code_integrity(self, file_path: str) -> bool:
        """Verify integrity of a single file"""
        if not os.path.exists(file_path):
            return False
            
        current_hash = self.calculate_file_hashes(file_path)
        stored_hash = self.code_hashes.get(file_path)
        
        if not stored_hash:
            return False
            
        # Verify all hash types
        if (current_hash.hash_sha256 != stored_hash.hash_sha256 or
            current_hash.hash_sha512 != stored_hash.hash_sha512 or
            current_hash.combined_hash != stored_hash.combined_hash):
            return False
            
        # Update verification metadata
        stored_hash.last_verified = time.time()
        stored_hash.verification_count += 1
        
        return True
        
    def verify_execution_chain(self, module_name: str) -> bool:
        """Verify execution chain back to genesis"""
        if module_name in self.verified_modules:
            return True
            
        module_hash = self.execution_hashes.get(module_name)
        if not module_hash:
            return False
            
        # Verify module dependencies
        code_hash = self.code_hashes.get(module_name)
        if not code_hash:
            return False
            
        for dep in code_hash.dependencies:
            if not self.verify_execution_chain(dep):
                return False
                
        # Calculate execution hash linked to genesis
        exec_hash = self._calculate_execution_hash(
            module_name,
            code_hash,
            self.genesis_hash
        )
        
        if exec_hash != module_hash:
            return False
            
        self.verified_modules.add(module_name)
        return True
        
    def enforce_integrity(self, module_name: str) -> bool:
        """Enforce both code and execution integrity"""
        if not self.enforcing:
            return True
            
        # Verify code integrity
        if not self.verify_code_integrity(module_name):
            return False
            
        # Verify execution chain
        if not self.verify_execution_chain(module_name):
            return False
            
        return True
        
    def _calculate_execution_hash(
        self,
        module_name: str,
        code_hash: CodeHash,
        genesis_hash: str
    ) -> str:
        """Calculate execution hash linked to genesis"""
        exec_data = {
            "module": module_name,
            "code_sha256": code_hash.hash_sha256,
            "code_sha512": code_hash.hash_sha512,
            "timestamp": time.time(),
            "genesis": genesis_hash
        }
        
        # Double SHA256 for execution hash
        data_bytes = json.dumps(exec_data, sort_keys=True).encode()
        first_hash = hashlib.sha256(data_bytes).digest()
        final_hash = hashlib.sha256(first_hash).hexdigest()
        
        return final_hash
        
    def _extract_dependencies(self, content: str) -> List[str]:
        """Extract module dependencies from code"""
        dependencies = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # Basic dependency extraction
                # TODO: Implement more sophisticated parsing
                dep = line.split()[1].split('.')[0]
                dependencies.append(dep)
                
        return dependencies
        
    def register_module(self, module_name: str) -> bool:
        """Register new module for integrity enforcement"""
        try:
            # Calculate code hashes
            code_hash = self.calculate_file_hashes(module_name)
            self.code_hashes[module_name] = code_hash
            
            # Calculate execution hash
            exec_hash = self._calculate_execution_hash(
                module_name,
                code_hash,
                self.genesis_hash
            )
            self.execution_hashes[module_name] = exec_hash
            
            return True
            
        except Exception:
            return False
            
    def verify_all(self) -> Dict[str, bool]:
        """Verify integrity of all registered modules"""
        results = {}
        
        for module in self.code_hashes.keys():
            results[module] = self.enforce_integrity(module)
            
        return results
        
    def get_integrity_status(self) -> Dict[str, Dict]:
        """Get integrity status of all modules"""
        status = {}
        
        for module, code_hash in self.code_hashes.items():
            status[module] = {
                "verified": module in self.verified_modules,
                "last_verified": code_hash.last_verified,
                "verification_count": code_hash.verification_count,
                "sha256": code_hash.hash_sha256,
                "sha512": code_hash.hash_sha512,
                "combined": code_hash.combined_hash,
                "dependencies": code_hash.dependencies
            }
            
        return status
        
    def export_integrity_proof(self, output_file: str):
        """Export integrity proof to file"""
        proof = {
            "genesis_hash": self.genesis_hash,
            "timestamp": time.time(),
            "modules": self.get_integrity_status()
        }
        
        with open(output_file, 'w') as f:
            json.dump(proof, f, indent=2)
            
    @classmethod
    def import_integrity_proof(cls, proof_file: str) -> 'CodeIntegrityEnforcer':
        """Create enforcer from integrity proof file"""
        with open(proof_file) as f:
            proof = json.load(f)
            
        enforcer = cls(proof["genesis_hash"])
        
        for module, status in proof["modules"].items():
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
            enforcer.code_hashes[module] = code_hash
            
        return enforcer 