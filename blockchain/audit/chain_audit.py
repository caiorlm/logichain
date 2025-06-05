import time
import hashlib
import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

class AuditStatus(Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    SUSPICIOUS = "SUSPICIOUS"
    COMPROMISED = "COMPROMISED"

@dataclass
class AuditResult:
    status: AuditStatus
    issues: List[str]
    metrics: Dict
    timestamp: float

@dataclass
class AuditMetrics:
    total_blocks: int
    total_transactions: int
    total_pods: int
    invalid_blocks: int
    invalid_transactions: int
    invalid_pods: int
    sync_attempts: int
    validation_time: float

class ChainAuditor:
    def __init__(self):
        self.audit_history: List[AuditResult] = []
        self.invalid_blocks: Set[str] = set()  # block hashes
        self.suspicious_nodes: Set[str] = set()  # node IDs
        self.audit_metrics: Dict[str, AuditMetrics] = {}  # chain_id -> metrics
        
    def audit_chain(
        self,
        chain: List[Dict],
        genesis_block: Dict
    ) -> AuditResult:
        """Perform full chain audit from genesis"""
        start_time = time.time()
        issues = []
        metrics = AuditMetrics(
            total_blocks=len(chain),
            total_transactions=0,
            total_pods=0,
            invalid_blocks=0,
            invalid_transactions=0,
            invalid_pods=0,
            sync_attempts=0,
            validation_time=0
        )
        
        try:
            # Verify genesis block
            if not self._verify_genesis(chain[0], genesis_block):
                issues.append("Genesis block mismatch")
                return self._create_invalid_result(
                    issues,
                    metrics,
                    start_time
                )
                
            # Verify block chain
            current_hash = genesis_block["hash"]
            
            for i, block in enumerate(chain):
                # Update metrics
                metrics.total_transactions += len(
                    block.get("transactions", [])
                )
                metrics.total_pods += len(
                    block.get("pods", [])
                )
                
                # Verify block
                if not self._verify_block(block, current_hash):
                    issues.append(
                        f"Invalid block at height {block['index']}"
                    )
                    metrics.invalid_blocks += 1
                    self.invalid_blocks.add(block["hash"])
                    
                # Verify transactions
                invalid_tx = self._verify_transactions(
                    block.get("transactions", [])
                )
                if invalid_tx:
                    issues.append(
                        f"Invalid transactions in block {block['index']}: "
                        f"{invalid_tx}"
                    )
                    metrics.invalid_transactions += len(invalid_tx)
                    
                # Verify PODs
                invalid_pods = self._verify_pods(
                    block.get("pods", [])
                )
                if invalid_pods:
                    issues.append(
                        f"Invalid PODs in block {block['index']}: "
                        f"{invalid_pods}"
                    )
                    metrics.invalid_pods += len(invalid_pods)
                    
                # Update current hash
                current_hash = block["hash"]
                
            # Check for suspicious patterns
            if self._is_chain_suspicious(chain):
                issues.append("Suspicious chain patterns detected")
                
            # Create audit result
            status = self._determine_audit_status(
                issues,
                metrics
            )
            
            result = AuditResult(
                status=status,
                issues=issues,
                metrics=metrics.__dict__,
                timestamp=time.time()
            )
            
            # Store audit result
            self.audit_history.append(result)
            self.audit_metrics[chain[0]["hash"]] = metrics
            
            return result
            
        except Exception as e:
            issues.append(f"Audit error: {str(e)}")
            return self._create_invalid_result(
                issues,
                metrics,
                start_time
            )
            
    def verify_immutability(
        self,
        chain: List[Dict],
        target_block_hash: str
    ) -> bool:
        """Verify chain immutability up to target block"""
        try:
            # Find target block
            target_index = -1
            for i, block in enumerate(chain):
                if block["hash"] == target_block_hash:
                    target_index = i
                    break
                    
            if target_index == -1:
                return False
                
            # Verify chain up to target
            current_hash = chain[0]["hash"]
            
            for i in range(1, target_index + 1):
                block = chain[i]
                
                # Verify block links
                if block["previous_hash"] != current_hash:
                    return False
                    
                # Verify block hash
                if not self._verify_block_hash(block):
                    return False
                    
                current_hash = block["hash"]
                
            return True
            
        except Exception:
            return False
            
    def export_audit_log(self, chain_id: str) -> Dict:
        """Export audit log for chain"""
        metrics = self.audit_metrics.get(chain_id)
        if not metrics:
            return {}
            
        relevant_audits = [
            audit for audit in self.audit_history
            if audit.metrics.get("chain_id") == chain_id
        ]
        
        return {
            "chain_id": chain_id,
            "metrics": metrics.__dict__,
            "audit_history": [
                {
                    "timestamp": audit.timestamp,
                    "status": audit.status.value,
                    "issues": audit.issues
                }
                for audit in relevant_audits
            ],
            "invalid_blocks": list(self.invalid_blocks),
            "suspicious_nodes": list(self.suspicious_nodes)
        }
        
    def _verify_genesis(
        self,
        block: Dict,
        genesis: Dict
    ) -> bool:
        """Verify genesis block hasn't been modified"""
        return all(
            block.get(key) == genesis.get(key)
            for key in genesis.keys()
        )
        
    def _verify_block(
        self,
        block: Dict,
        previous_hash: str
    ) -> bool:
        """Verify block validity and links"""
        try:
            # Check previous hash
            if block["previous_hash"] != previous_hash:
                return False
                
            # Verify block hash
            if not self._verify_block_hash(block):
                return False
                
            # Verify block signature
            if not self._verify_block_signature(block):
                return False
                
            # Verify merkle root
            if not self._verify_merkle_root(block):
                return False
                
            return True
            
        except Exception:
            return False
            
    def _verify_block_hash(self, block: Dict) -> bool:
        """Verify block hash is valid"""
        try:
            # Recreate block hash
            block_data = {
                k: v for k, v in block.items()
                if k != "hash"
            }
            calculated_hash = hashlib.sha256(
                json.dumps(block_data, sort_keys=True).encode()
            ).hexdigest()
            
            return block["hash"] == calculated_hash
            
        except Exception:
            return False
            
    def _verify_block_signature(self, block: Dict) -> bool:
        """Verify block signature"""
        try:
            # Implementation depends on signature scheme
            return True  # Placeholder
            
        except Exception:
            return False
            
    def _verify_merkle_root(self, block: Dict) -> bool:
        """Verify block's merkle root"""
        try:
            # Combine transactions and PODs
            items = (
                block.get("transactions", []) +
                block.get("pods", [])
            )
            
            # Calculate merkle root
            merkle_root = self._calculate_merkle_root(items)
            
            return block["merkle_root"] == merkle_root
            
        except Exception:
            return False
            
    def _verify_transactions(
        self,
        transactions: List[Dict]
    ) -> List[str]:
        """Verify transactions in block"""
        invalid = []
        
        for tx in transactions:
            if not self._verify_transaction(tx):
                invalid.append(tx["tx_id"])
                
        return invalid
        
    def _verify_transaction(self, tx: Dict) -> bool:
        """Verify single transaction"""
        try:
            # Implementation depends on transaction format
            return True  # Placeholder
            
        except Exception:
            return False
            
    def _verify_pods(self, pods: List[Dict]) -> List[str]:
        """Verify PODs in block"""
        invalid = []
        
        for pod in pods:
            if not self._verify_pod(pod):
                invalid.append(pod["pod_id"])
                
        return invalid
        
    def _verify_pod(self, pod: Dict) -> bool:
        """Verify single POD"""
        try:
            # Implementation depends on POD format
            return True  # Placeholder
            
        except Exception:
            return False
            
    def _is_chain_suspicious(self, chain: List[Dict]) -> bool:
        """Check for suspicious patterns in chain"""
        try:
            # Check timestamp sequence
            times = [b["timestamp"] for b in chain]
            if not all(t1 < t2 for t1, t2 in zip(times, times[1:])):
                return True
                
            # Check difficulty changes
            difficulties = [b["difficulty"] for b in chain]
            changes = [
                d2/d1 if d1 > 0 else 1
                for d1, d2 in zip(difficulties, difficulties[1:])
            ]
            if any(c > 2 or c < 0.5 for c in changes):
                return True
                
            # Check miner distribution
            miners = [b["miner_id"] for b in chain]
            miner_counts = {}
            for m in miners:
                miner_counts[m] = miner_counts.get(m, 0) + 1
                
            total = len(miners)
            if any(count/total > 0.5 for count in miner_counts.values()):
                return True
                
            return False
            
        except Exception:
            return True
            
    def _determine_audit_status(
        self,
        issues: List[str],
        metrics: AuditMetrics
    ) -> AuditStatus:
        """Determine overall audit status"""
        if not issues:
            return AuditStatus.VALID
            
        if metrics.invalid_blocks > 0:
            return AuditStatus.INVALID
            
        if (
            metrics.invalid_transactions > 0 or
            metrics.invalid_pods > 0
        ):
            return AuditStatus.SUSPICIOUS
            
        return AuditStatus.COMPROMISED
        
    def _create_invalid_result(
        self,
        issues: List[str],
        metrics: AuditMetrics,
        start_time: float
    ) -> AuditResult:
        """Create result for invalid chain"""
        metrics.validation_time = time.time() - start_time
        return AuditResult(
            status=AuditStatus.INVALID,
            issues=issues,
            metrics=metrics.__dict__,
            timestamp=time.time()
        )
        
    def _calculate_merkle_root(self, items: List[Dict]) -> str:
        """Calculate merkle root of items"""
        if not items:
            return ""
            
        # Create leaf nodes
        leaves = [
            hashlib.sha256(
                json.dumps(item, sort_keys=True).encode()
            ).hexdigest()
            for item in items
        ]
        
        # Build tree
        tree = leaves.copy()
        while len(tree) > 1:
            if len(tree) % 2 == 1:
                tree.append(tree[-1])
                
            tree = [
                hashlib.sha256(
                    (tree[i] + tree[i+1]).encode()
                ).hexdigest()
                for i in range(0, len(tree), 2)
            ]
            
        return tree[0] 