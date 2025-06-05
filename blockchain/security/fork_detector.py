import time
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ForkStatus(Enum):
    VALID = "VALID"
    DIVERGENT = "DIVERGENT"
    MALICIOUS = "MALICIOUS"
    STALE = "STALE"
    ORPHANED = "ORPHANED"

@dataclass
class ChainTip:
    block_hash: str
    height: int
    timestamp: float
    miner: str
    parent_hash: str
    is_offgrid: bool
    score: float

@dataclass
class ForkValidation:
    fork_id: str
    status: ForkStatus
    main_tip: ChainTip
    fork_tip: ChainTip
    common_ancestor: str
    divergence_height: int
    details: Dict

class ForkDetector:
    def __init__(self):
        self.chain_tips: Dict[str, ChainTip] = {}  # block_hash -> tip
        self.fork_validations: Dict[str, ForkValidation] = {}  # fork_id -> validation
        self.malicious_forks: Set[str] = set()  # fork_ids
        self.max_fork_depth = 100  # Max blocks to track back
        self.min_fork_score = 0.8  # Min score to consider valid
        
    def check_fork(
        self,
        block_hash: str,
        height: int,
        timestamp: float,
        miner: str,
        parent_hash: str,
        is_offgrid: bool,
        block_score: float
    ) -> ForkStatus:
        """Check for fork divergence"""
        try:
            # Record new chain tip
            new_tip = ChainTip(
                block_hash=block_hash,
                height=height,
                timestamp=timestamp,
                miner=miner,
                parent_hash=parent_hash,
                is_offgrid=is_offgrid,
                score=block_score
            )
            self.chain_tips[block_hash] = new_tip
            
            # Find potential forks
            forks = self._find_forks(new_tip)
            if not forks:
                return ForkStatus.VALID
                
            # Validate each fork
            for fork_tip in forks:
                # Find common ancestor
                ancestor_hash, divergence_height = self._find_common_ancestor(
                    new_tip,
                    fork_tip
                )
                
                if not ancestor_hash:
                    continue
                    
                # Generate fork ID
                fork_id = self._generate_fork_id(
                    new_tip.block_hash,
                    fork_tip.block_hash
                )
                
                # Check if known malicious
                if fork_id in self.malicious_forks:
                    return ForkStatus.MALICIOUS
                    
                # Validate fork
                status = self._validate_fork(
                    new_tip,
                    fork_tip,
                    ancestor_hash,
                    divergence_height
                )
                
                # Record validation
                self.fork_validations[fork_id] = ForkValidation(
                    fork_id=fork_id,
                    status=status,
                    main_tip=new_tip,
                    fork_tip=fork_tip,
                    common_ancestor=ancestor_hash,
                    divergence_height=divergence_height,
                    details=self._get_fork_details(
                        new_tip,
                        fork_tip,
                        ancestor_hash,
                        divergence_height
                    )
                )
                
                if status == ForkStatus.MALICIOUS:
                    self.malicious_forks.add(fork_id)
                    return status
                    
            # Return worst status if multiple forks
            statuses = [
                v.status
                for v in self.fork_validations.values()
                if v.main_tip.block_hash == block_hash
            ]
            
            return max(statuses, key=lambda s: s.value)
            
        except Exception as e:
            print(f"Error checking fork: {e}")
            return ForkStatus.DIVERGENT
            
    def _find_forks(
        self,
        tip: ChainTip
    ) -> List[ChainTip]:
        """Find potential fork tips"""
        forks = []
        
        for other_tip in self.chain_tips.values():
            # Skip self and old tips
            if (
                other_tip.block_hash == tip.block_hash or
                tip.timestamp - other_tip.timestamp > 3600  # 1 hour
            ):
                continue
                
            # Check height difference
            height_diff = abs(tip.height - other_tip.height)
            if height_diff > self.max_fork_depth:
                continue
                
            # Check if potentially forked
            if (
                other_tip.parent_hash != tip.parent_hash and
                other_tip.height == tip.height
            ):
                forks.append(other_tip)
                
        return forks
        
    def _find_common_ancestor(
        self,
        tip1: ChainTip,
        tip2: ChainTip
    ) -> Tuple[str, int]:
        """Find common ancestor of two chain tips"""
        try:
            # Start at tips
            current1 = tip1
            current2 = tip2
            
            # Track visited blocks
            visited1: Set[str] = {tip1.block_hash}
            visited2: Set[str] = {tip2.block_hash}
            
            # Walk back until common ancestor found
            for _ in range(self.max_fork_depth):
                # Check if tips share parent
                if current1.parent_hash == current2.parent_hash:
                    return current1.parent_hash, current1.height - 1
                    
                # Move back one block
                if current1.parent_hash in self.chain_tips:
                    current1 = self.chain_tips[current1.parent_hash]
                    visited1.add(current1.block_hash)
                    
                if current2.parent_hash in self.chain_tips:
                    current2 = self.chain_tips[current2.parent_hash]
                    visited2.add(current2.block_hash)
                    
                # Check if paths crossed
                if current1.block_hash in visited2:
                    return current1.block_hash, current1.height
                    
                if current2.block_hash in visited1:
                    return current2.block_hash, current2.height
                    
            return "", 0
            
        except Exception:
            return "", 0
            
    def _validate_fork(
        self,
        main_tip: ChainTip,
        fork_tip: ChainTip,
        ancestor_hash: str,
        divergence_height: int
    ) -> ForkStatus:
        """Validate a potential fork"""
        try:
            # Check fork depth
            depth = main_tip.height - divergence_height
            if depth > self.max_fork_depth:
                return ForkStatus.STALE
                
            # Check timestamps
            if (
                fork_tip.timestamp < main_tip.timestamp - 3600 or  # Too old
                fork_tip.timestamp > main_tip.timestamp + 300  # Too new
            ):
                return ForkStatus.STALE
                
            # Check scores
            if (
                fork_tip.score < self.min_fork_score or
                fork_tip.score < main_tip.score * 0.9
            ):
                return ForkStatus.ORPHANED
                
            # Check for malicious patterns
            if self._is_malicious_fork(
                main_tip,
                fork_tip,
                ancestor_hash,
                divergence_height
            ):
                return ForkStatus.MALICIOUS
                
            # Valid fork
            return ForkStatus.DIVERGENT
            
        except Exception:
            return ForkStatus.MALICIOUS
            
    def _is_malicious_fork(
        self,
        main_tip: ChainTip,
        fork_tip: ChainTip,
        ancestor_hash: str,
        divergence_height: int
    ) -> bool:
        """Check for malicious fork patterns"""
        try:
            # Check miner behavior
            miner_forks = len([
                v for v in self.fork_validations.values()
                if (
                    v.fork_tip.miner == fork_tip.miner and
                    main_tip.timestamp - v.fork_tip.timestamp < 86400  # 24h
                )
            ])
            
            if miner_forks > 3:  # More than 3 forks in 24h
                return True
                
            # Check timing patterns
            if (
                fork_tip.timestamp - main_tip.timestamp < 1 or  # Too close
                abs(fork_tip.timestamp - main_tip.timestamp) < 5  # Suspicious timing
            ):
                return True
                
            # Check score manipulation
            if fork_tip.score > main_tip.score * 1.5:  # Suspicious score jump
                return True
                
            return False
            
        except Exception:
            return True
            
    def _generate_fork_id(
        self,
        hash1: str,
        hash2: str
    ) -> str:
        """Generate unique fork ID from two block hashes"""
        return f"{min(hash1, hash2)}:{max(hash1, hash2)}"
        
    def _get_fork_details(
        self,
        main_tip: ChainTip,
        fork_tip: ChainTip,
        ancestor_hash: str,
        divergence_height: int
    ) -> Dict:
        """Get detailed fork information"""
        return {
            "main_chain": {
                "tip_hash": main_tip.block_hash,
                "height": main_tip.height,
                "miner": main_tip.miner,
                "score": main_tip.score,
                "is_offgrid": main_tip.is_offgrid
            },
            "fork_chain": {
                "tip_hash": fork_tip.block_hash,
                "height": fork_tip.height,
                "miner": fork_tip.miner,
                "score": fork_tip.score,
                "is_offgrid": fork_tip.is_offgrid
            },
            "divergence": {
                "ancestor": ancestor_hash,
                "height": divergence_height,
                "depth": main_tip.height - divergence_height
            }
        }
        
    def get_fork_status(self, fork_id: str) -> Optional[Dict]:
        """Get fork validation status"""
        if fork_id not in self.fork_validations:
            return None
            
        validation = self.fork_validations[fork_id]
        return {
            "status": validation.status.value,
            "is_malicious": fork_id in self.malicious_forks,
            "details": validation.details
        }
        
    def cleanup_old_tips(self):
        """Cleanup old chain tips"""
        current_time = time.time()
        old_hashes = [
            block_hash
            for block_hash, tip in self.chain_tips.items()
            if current_time - tip.timestamp > 3600  # 1 hour
        ]
        
        for block_hash in old_hashes:
            del self.chain_tips[block_hash]
            
        # Cleanup old validations
        old_forks = [
            fork_id
            for fork_id, validation in self.fork_validations.items()
            if current_time - max(
                validation.main_tip.timestamp,
                validation.fork_tip.timestamp
            ) > 86400  # 24 hours
        ]
        
        for fork_id in old_forks:
            del self.fork_validations[fork_id] 