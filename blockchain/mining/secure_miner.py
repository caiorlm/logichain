import time
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import ed25519
from enum import Enum

class MiningMode(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"

@dataclass
class MiningConfig:
    mode: MiningMode
    max_block_size: int
    max_transactions: int
    target_difficulty: int
    min_pod_count: int
    max_pod_age: int

@dataclass
class Block:
    index: int
    previous_hash: str
    timestamp: float
    transactions: List[Dict]
    pods: List[Dict]
    nonce: int
    difficulty: int
    miner_id: str
    mode: MiningMode
    merkle_root: str
    signature: bytes

class SecureMiner:
    def __init__(self):
        # Configure mining limits
        self.online_config = MiningConfig(
            mode=MiningMode.ONLINE,
            max_block_size=1024 * 1024,  # 1MB
            max_transactions=1000,
            target_difficulty=100000,
            min_pod_count=1,
            max_pod_age=86400  # 24 hours
        )
        
        self.offline_config = MiningConfig(
            mode=MiningMode.OFFLINE,
            max_block_size=1024,  # 1KB
            max_transactions=10,
            target_difficulty=1000,
            min_pod_count=1,
            max_pod_age=86400 * 7  # 7 days
        )
        
        self.mined_blocks: Dict[str, Block] = {}
        self.invalid_attempts: Set[str] = set()
        
    def mine_block(
        self,
        index: int,
        previous_hash: str,
        transactions: List[Dict],
        pods: List[Dict],
        miner_id: str,
        private_key: bytes,
        mode: MiningMode
    ) -> Optional[Block]:
        """Mine a new block with POD validation"""
        try:
            # Get config for mode
            config = (
                self.online_config if mode == MiningMode.ONLINE
                else self.offline_config
            )
            
            # Validate block contents
            if not self._validate_block_contents(
                transactions,
                pods,
                config
            ):
                return None
                
            # Create block template
            block = Block(
                index=index,
                previous_hash=previous_hash,
                timestamp=time.time(),
                transactions=transactions,
                pods=pods,
                nonce=0,
                difficulty=config.target_difficulty,
                miner_id=miner_id,
                mode=mode,
                merkle_root=self._calculate_merkle_root(
                    transactions,
                    pods
                ),
                signature=b""
            )
            
            # Mine block
            mined_block = self._mine_with_pod(
                block,
                config,
                private_key
            )
            
            if mined_block:
                # Store valid block
                block_hash = self._calculate_block_hash(mined_block)
                self.mined_blocks[block_hash] = mined_block
                
            return mined_block
            
        except Exception as e:
            print(f"Mining error: {e}")
            return None
            
    def verify_block(
        self,
        block: Block,
        miner_pubkey: bytes
    ) -> bool:
        """Verify mined block validity"""
        try:
            # Get config for mode
            config = (
                self.online_config if block.mode == MiningMode.ONLINE
                else self.offline_config
            )
            
            # Verify block contents
            if not self._validate_block_contents(
                block.transactions,
                block.pods,
                config
            ):
                return False
                
            # Verify PODs
            if not self._verify_pods(block.pods):
                return False
                
            # Verify merkle root
            if block.merkle_root != self._calculate_merkle_root(
                block.transactions,
                block.pods
            ):
                return False
                
            # Verify mining difficulty
            block_hash = self._calculate_block_hash(block)
            if not self._verify_difficulty(
                block_hash,
                block.difficulty
            ):
                return False
                
            # Verify signature
            if not self._verify_block_signature(
                block,
                miner_pubkey
            ):
                return False
                
            return True
            
        except Exception:
            return False
            
    def _validate_block_contents(
        self,
        transactions: List[Dict],
        pods: List[Dict],
        config: MiningConfig
    ) -> bool:
        """Validate block contents against limits"""
        # Check transaction count
        if len(transactions) > config.max_transactions:
            return False
            
        # Check block size
        block_size = (
            len(str(transactions).encode()) +
            len(str(pods).encode())
        )
        if block_size > config.max_block_size:
            return False
            
        # Check minimum PODs
        if len(pods) < config.min_pod_count:
            return False
            
        # Check POD age
        current_time = time.time()
        for pod in pods:
            pod_time = pod.get("timestamp", 0)
            if current_time - pod_time > config.max_pod_age:
                return False
                
        return True
        
    def _mine_with_pod(
        self,
        block: Block,
        config: MiningConfig,
        private_key: bytes
    ) -> Optional[Block]:
        """Mine block with POD validation"""
        max_nonce = 2**32  # 4 billion attempts max
        
        for nonce in range(max_nonce):
            # Update nonce
            block.nonce = nonce
            
            # Calculate hash
            block_hash = self._calculate_block_hash(block)
            
            # Check difficulty
            if self._verify_difficulty(
                block_hash,
                config.target_difficulty
            ):
                # Sign block
                block.signature = self._sign_block(
                    block,
                    private_key
                )
                return block
                
        return None
        
    def _calculate_merkle_root(
        self,
        transactions: List[Dict],
        pods: List[Dict]
    ) -> str:
        """Calculate Merkle root of transactions and PODs"""
        # Combine all items
        items = [
            hashlib.sha256(str(tx).encode()).hexdigest()
            for tx in transactions
        ] + [
            hashlib.sha256(str(pod).encode()).hexdigest()
            for pod in pods
        ]
        
        # Build Merkle tree
        while len(items) > 1:
            if len(items) % 2 == 1:
                items.append(items[-1])
                
            items = [
                hashlib.sha256(
                    (items[i] + items[i+1]).encode()
                ).hexdigest()
                for i in range(0, len(items), 2)
            ]
            
        return items[0] if items else ""
        
    def _calculate_block_hash(self, block: Block) -> str:
        """Calculate block hash"""
        block_data = (
            f"{block.index}:{block.previous_hash}:"
            f"{block.timestamp}:{block.merkle_root}:"
            f"{block.nonce}:{block.difficulty}:"
            f"{block.miner_id}:{block.mode.value}"
        )
        return hashlib.sha256(block_data.encode()).hexdigest()
        
    def _verify_difficulty(
        self,
        block_hash: str,
        target_difficulty: int
    ) -> bool:
        """Verify block hash meets difficulty target"""
        return int(block_hash, 16) < 2**256 // target_difficulty
        
    def _sign_block(
        self,
        block: Block,
        private_key: bytes
    ) -> bytes:
        """Sign block with miner's private key"""
        block_hash = self._calculate_block_hash(block)
        signing_key = ed25519.SigningKey(private_key)
        return signing_key.sign(block_hash.encode())
        
    def _verify_block_signature(
        self,
        block: Block,
        miner_pubkey: bytes
    ) -> bool:
        """Verify block signature"""
        try:
            block_hash = self._calculate_block_hash(block)
            verifying_key = ed25519.VerifyingKey(miner_pubkey)
            verifying_key.verify(
                block.signature,
                block_hash.encode()
            )
            return True
        except:
            return False
            
    def _verify_pods(self, pods: List[Dict]) -> bool:
        """Verify PODs in block"""
        # Implementation depends on POD validation system
        return True  # Placeholder 