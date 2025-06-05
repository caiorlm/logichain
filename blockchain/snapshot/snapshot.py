"""
LogiChain Snapshot System
Creates and verifies blockchain state snapshots
"""

import json
import gzip
import time
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from ..crypto.signature import SignatureManager
from ..core.blockchain import Blockchain
from ..storage.database import BlockchainDB

@dataclass
class SnapshotMetadata:
    """Metadata for blockchain snapshot"""
    block_height: int
    block_hash: str
    timestamp: float
    version: str
    signature: Optional[str] = None
    
@dataclass
class BlockchainState:
    """Complete blockchain state"""
    utxo_set: Dict[str, Dict]  # UTXO set
    accounts: Dict[str, Dict]  # Account balances and nonces
    stakes: Dict[str, Dict]  # Staking information
    reputation: Dict[str, float]  # Node reputation scores
    validators: Dict[str, Dict]  # Validator information
    delivery_proofs: Dict[str, Dict]  # Proof of Delivery records
    
class SnapshotManager:
    """Manages blockchain state snapshots"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        db: BlockchainDB,
        snapshot_dir: str = "snapshots"
    ):
        self.blockchain = blockchain
        self.db = db
        self.snapshot_dir = snapshot_dir
        
    def create_snapshot(
        self,
        private_key = None
    ) -> str:
        """Create new blockchain state snapshot"""
        # Get current state
        state = self._get_current_state()
        
        # Create metadata
        metadata = SnapshotMetadata(
            block_height=self.blockchain.height,
            block_hash=self.blockchain.get_latest_block().hash,
            timestamp=time.time(),
            version="1.0.0"
        )
        
        # Sign metadata if key provided
        if private_key:
            metadata.signature = self._sign_metadata(
                metadata,
                private_key
            )
            
        # Create snapshot
        snapshot = {
            "metadata": asdict(metadata),
            "state": asdict(state)
        }
        
        # Generate filename
        filename = self._get_snapshot_filename(metadata)
        
        # Save compressed snapshot
        self._save_snapshot(snapshot, filename)
        
        return filename
        
    def load_snapshot(
        self,
        filename: str,
        public_key = None
    ) -> bool:
        """Load and verify snapshot"""
        try:
            # Load snapshot
            snapshot = self._load_snapshot(filename)
            
            # Parse metadata
            metadata = SnapshotMetadata(**snapshot["metadata"])
            
            # Verify signature if key provided
            if public_key and metadata.signature:
                if not self._verify_metadata(
                    metadata,
                    metadata.signature,
                    public_key
                ):
                    return False
                    
            # Parse state
            state = BlockchainState(**snapshot["state"])
            
            # Apply state
            self._apply_state(state)
            
            return True
            
        except Exception as e:
            print(f"Failed to load snapshot: {str(e)}")
            return False
            
    def _get_current_state(self) -> BlockchainState:
        """Get current blockchain state"""
        return BlockchainState(
            utxo_set=self.db.get_utxo_set(),
            accounts=self.db.get_accounts(),
            stakes=self.db.get_stakes(),
            reputation=self.db.get_reputation_scores(),
            validators=self.db.get_validators(),
            delivery_proofs=self.db.get_delivery_proofs()
        )
        
    def _apply_state(self, state: BlockchainState):
        """Apply snapshot state to blockchain"""
        # Clear current state
        self.db.clear_state()
        
        # Apply new state
        self.db.set_utxo_set(state.utxo_set)
        self.db.set_accounts(state.accounts)
        self.db.set_stakes(state.stakes)
        self.db.set_reputation_scores(state.reputation)
        self.db.set_validators(state.validators)
        self.db.set_delivery_proofs(state.delivery_proofs)
        
    def _get_snapshot_filename(
        self,
        metadata: SnapshotMetadata
    ) -> str:
        """Generate snapshot filename"""
        return (
            f"snapshot_"
            f"{metadata.block_height}_"
            f"{metadata.block_hash[:8]}.json.gz"
        )
        
    def _save_snapshot(self, snapshot: Dict, filename: str):
        """Save compressed snapshot to file"""
        # Convert to JSON
        json_data = json.dumps(snapshot, indent=2)
        
        # Compress and save
        with gzip.open(
            f"{self.snapshot_dir}/{filename}",
            "wt",
            encoding="utf-8"
        ) as f:
            f.write(json_data)
            
    def _load_snapshot(self, filename: str) -> Dict:
        """Load compressed snapshot from file"""
        # Load and decompress
        with gzip.open(
            f"{self.snapshot_dir}/{filename}",
            "rt",
            encoding="utf-8"
        ) as f:
            return json.loads(f.read())
            
    def _sign_metadata(
        self,
        metadata: SnapshotMetadata,
        private_key
    ) -> str:
        """Sign snapshot metadata"""
        # Create message
        message = self._get_metadata_message(metadata)
        
        # Sign message
        signature = SignatureManager.sign_canonical(
            private_key,
            message
        )
        
        return signature.hex()
        
    def _verify_metadata(
        self,
        metadata: SnapshotMetadata,
        signature: str,
        public_key
    ) -> bool:
        """Verify snapshot metadata signature"""
        try:
            # Create message
            message = self._get_metadata_message(metadata)
            
            # Verify signature
            return SignatureManager.verify_canonical(
                public_key,
                message,
                bytes.fromhex(signature)
            )
            
        except Exception:
            return False
            
    def _get_metadata_message(
        self,
        metadata: SnapshotMetadata
    ) -> bytes:
        """Get message for metadata signing"""
        # Create copy without signature
        meta_copy = asdict(metadata)
        meta_copy.pop("signature", None)
        
        # Convert to bytes
        return json.dumps(
            meta_copy,
            sort_keys=True
        ).encode()
        
    def verify_snapshot_integrity(
        self,
        filename: str
    ) -> bool:
        """Verify snapshot data integrity"""
        try:
            # Load snapshot
            snapshot = self._load_snapshot(filename)
            
            # Verify metadata
            metadata = SnapshotMetadata(**snapshot["metadata"])
            
            # Verify state format
            state = BlockchainState(**snapshot["state"])
            
            # Verify UTXO set
            for utxo in state.utxo_set.values():
                if not self._verify_utxo(utxo):
                    return False
                    
            # Verify accounts
            for account in state.accounts.values():
                if not self._verify_account(account):
                    return False
                    
            # Verify stakes
            for stake in state.stakes.values():
                if not self._verify_stake(stake):
                    return False
                    
            # Verify reputation scores
            for score in state.reputation.values():
                if not isinstance(score, (int, float)):
                    return False
                if score < 0 or score > 1:
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def _verify_utxo(self, utxo: Dict) -> bool:
        """Verify UTXO entry format"""
        required = {"txid", "vout", "amount", "address"}
        return all(k in utxo for k in required)
        
    def _verify_account(self, account: Dict) -> bool:
        """Verify account entry format"""
        required = {"balance", "nonce"}
        return all(k in account for k in required)
        
    def _verify_stake(self, stake: Dict) -> bool:
        """Verify stake entry format"""
        required = {"amount", "type", "start_time"}
        return all(k in stake for k in required) 