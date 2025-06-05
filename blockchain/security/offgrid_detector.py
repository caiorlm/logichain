import time
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from enum import Enum

class BlockStatus(Enum):
    VALID = "VALID"
    INVALID_SIZE = "INVALID_SIZE"
    INVALID_TX_COUNT = "INVALID_TX_COUNT"
    INVALID_POW = "INVALID_POW"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    INVALID_MERKLE = "INVALID_MERKLE"
    SUSPICIOUS = "SUSPICIOUS"

@dataclass
class BlockValidation:
    block_hash: str
    miner: str
    timestamp: float
    status: BlockStatus
    details: Dict
    is_offgrid: bool

class OffgridDetector:
    def __init__(self):
        self.validated_blocks: Dict[str, BlockValidation] = {}  # block_hash -> validation
        self.suspicious_miners: Set[str] = set()
        self.max_block_size = 1024  # 1KB for off-grid
        self.max_tx_count = 10  # Max 10 tx for off-grid
        self.min_pow_difficulty = 0x1fffffff  # Easier POW for off-grid
        
    def validate_block(
        self,
        block_hash: str,
        block_data: bytes,
        miner: str,
        timestamp: float,
        merkle_root: bytes,
        pow_hash: bytes,
        signature: bytes,
        tx_count: int,
        is_offgrid: bool
    ) -> BlockStatus:
        """Validate an off-grid block"""
        try:
            # Different rules for off-grid vs on-grid
            if is_offgrid:
                # Check block size
                if len(block_data) > self.max_block_size:
                    return self._record_validation(
                        BlockValidation(
                            block_hash=block_hash,
                            miner=miner,
                            timestamp=timestamp,
                            status=BlockStatus.INVALID_SIZE,
                            details={
                                "size": len(block_data),
                                "max_size": self.max_block_size
                            },
                            is_offgrid=is_offgrid
                        )
                    )
                    
                # Check transaction count
                if tx_count > self.max_tx_count:
                    return self._record_validation(
                        BlockValidation(
                            block_hash=block_hash,
                            miner=miner,
                            timestamp=timestamp,
                            status=BlockStatus.INVALID_TX_COUNT,
                            details={
                                "tx_count": tx_count,
                                "max_count": self.max_tx_count
                            },
                            is_offgrid=is_offgrid
                        )
                    )
                    
                # Check POW difficulty
                if not self._verify_pow(pow_hash, self.min_pow_difficulty):
                    return self._record_validation(
                        BlockValidation(
                            block_hash=block_hash,
                            miner=miner,
                            timestamp=timestamp,
                            status=BlockStatus.INVALID_POW,
                            details={
                                "pow_hash": pow_hash.hex(),
                                "min_difficulty": hex(self.min_pow_difficulty)
                            },
                            is_offgrid=is_offgrid
                        )
                    )
                    
            # Common validations for both modes
            # Verify merkle root
            if not self._verify_merkle(block_data, merkle_root):
                return self._record_validation(
                    BlockValidation(
                        block_hash=block_hash,
                        miner=miner,
                        timestamp=timestamp,
                        status=BlockStatus.INVALID_MERKLE,
                        details={"merkle_root": merkle_root.hex()},
                        is_offgrid=is_offgrid
                    )
                )
                
            # Verify signature
            if not self._verify_signature(block_hash, miner, signature):
                return self._record_validation(
                    BlockValidation(
                        block_hash=block_hash,
                        miner=miner,
                        timestamp=timestamp,
                        status=BlockStatus.INVALID_SIGNATURE,
                        details={"signature": signature.hex()},
                        is_offgrid=is_offgrid
                    )
                )
                
            # Check for suspicious patterns
            if self._is_suspicious(block_hash, miner, timestamp, is_offgrid):
                self.suspicious_miners.add(miner)
                return self._record_validation(
                    BlockValidation(
                        block_hash=block_hash,
                        miner=miner,
                        timestamp=timestamp,
                        status=BlockStatus.SUSPICIOUS,
                        details={"reason": "Suspicious mining pattern"},
                        is_offgrid=is_offgrid
                    )
                )
                
            # Block is valid
            return self._record_validation(
                BlockValidation(
                    block_hash=block_hash,
                    miner=miner,
                    timestamp=timestamp,
                    status=BlockStatus.VALID,
                    details={},
                    is_offgrid=is_offgrid
                )
            )
            
        except Exception as e:
            print(f"Error validating block: {e}")
            return BlockStatus.INVALID_MERKLE
            
    def _record_validation(
        self,
        validation: BlockValidation
    ) -> BlockStatus:
        """Record block validation result"""
        self.validated_blocks[validation.block_hash] = validation
        return validation.status
        
    def _verify_pow(
        self,
        pow_hash: bytes,
        min_difficulty: int
    ) -> bool:
        """Verify proof of work meets difficulty"""
        try:
            # Convert POW hash to integer
            pow_int = int.from_bytes(pow_hash, byteorder="big")
            return pow_int <= min_difficulty
            
        except Exception:
            return False
            
    def _verify_merkle(
        self,
        block_data: bytes,
        merkle_root: bytes
    ) -> bool:
        """Verify merkle root matches block data"""
        try:
            # Implementation depends on merkle tree algorithm
            return True  # Placeholder
            
        except Exception:
            return False
            
    def _verify_signature(
        self,
        block_hash: str,
        miner: str,
        signature: bytes
    ) -> bool:
        """Verify block signature"""
        try:
            # Implementation depends on signature scheme
            return True  # Placeholder
            
        except Exception:
            return False
            
    def _is_suspicious(
        self,
        block_hash: str,
        miner: str,
        timestamp: float,
        is_offgrid: bool
    ) -> bool:
        """Check for suspicious mining patterns"""
        try:
            # Get miner's recent blocks
            miner_blocks = [
                v for v in self.validated_blocks.values()
                if (
                    v.miner == miner and
                    v.is_offgrid == is_offgrid and
                    timestamp - v.timestamp < 3600  # Last hour
                )
            ]
            
            if not miner_blocks:
                return False
                
            # Check block frequency
            if len(miner_blocks) > 10:  # More than 10 blocks per hour
                return True
                
            # Check time between blocks
            sorted_blocks = sorted(miner_blocks, key=lambda x: x.timestamp)
            for i in range(1, len(sorted_blocks)):
                if sorted_blocks[i].timestamp - sorted_blocks[i-1].timestamp < 30:
                    return True  # Blocks too close together
                    
            return False
            
        except Exception:
            return True
            
    def get_miner_status(self, miner: str) -> Dict:
        """Get miner's validation status"""
        validations = [
            v for v in self.validated_blocks.values()
            if v.miner == miner
        ]
        
        return {
            "total_blocks": len(validations),
            "is_suspicious": miner in self.suspicious_miners,
            "valid_blocks": len([
                v for v in validations
                if v.status == BlockStatus.VALID
            ]),
            "invalid_blocks": len([
                v for v in validations
                if v.status != BlockStatus.VALID
            ]),
            "offgrid_blocks": len([
                v for v in validations
                if v.is_offgrid
            ])
        }
        
    def cleanup_old_validations(self):
        """Cleanup old block validations"""
        current_time = time.time()
        old_hashes = [
            block_hash
            for block_hash, validation in self.validated_blocks.items()
            if current_time - validation.timestamp > 86400  # 24 hours
        ]
        
        for block_hash in old_hashes:
            del self.validated_blocks[block_hash] 