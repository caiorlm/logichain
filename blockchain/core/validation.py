"""
Validation system for both online and offline (mesh) networks
"""

import hashlib
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

class NetworkMode(Enum):
    ONLINE = "online"
    OFFLINE_MESH = "offline_mesh"

@dataclass
class BlockHeader:
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    difficulty: int
    nonce: int
    network_mode: NetworkMode

class ValidationSystem:
    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty
        self.offline_buffer = []
        self.mesh_validators = set()
        self.min_confirmations = 6  # Bitcoin-style confirmations
        
    def calculate_block_hash(self, block_header: BlockHeader) -> str:
        """
        Calculate block hash for both online and offline modes with enhanced security
        """
        # Prepare header data with nonce and timestamp
        header_data = {
            "version": block_header.version,
            "previous_hash": block_header.previous_hash,
            "merkle_root": block_header.merkle_root,
            "timestamp": block_header.timestamp,
            "difficulty": block_header.difficulty,
            "nonce": block_header.nonce,
            "mode": block_header.network_mode.value
        }
        
        # Create hash
        header_string = json.dumps(header_data, sort_keys=True)
        
        if block_header.network_mode == NetworkMode.ONLINE:
            # Online: Bitcoin-style SHA256 double hash
            first_hash = hashlib.sha256(header_string.encode()).digest()
            final_hash = hashlib.sha256(first_hash).hexdigest()
            
            # Verify hash meets difficulty target
            hash_int = int(final_hash, 16)
            target = 2 ** (256 - self.difficulty)
            if hash_int >= target:
                return None
                
            return final_hash
        else:
            # Offline: Lightweight hash with timestamp and stake validation
            stake_proof = self._verify_stake(block_header)
            if not stake_proof:
                return None
                
            timestamp_salt = str(int(time.time())).encode()
            final_hash = hashlib.sha256(
                header_string.encode() + timestamp_salt + stake_proof
            ).hexdigest()
            
            return final_hash

    def validate_online_block(
        self,
        block_header: BlockHeader,
        transactions: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Enhanced online validation with Bitcoin-style security
        """
        # Verify POW with target difficulty
        block_hash = self.calculate_block_hash(block_header)
        if not block_hash:
            return False, "Invalid proof of work"
            
        # Verify merkle root (Bitcoin-style)
        calculated_merkle = self._calculate_merkle_root(transactions)
        if calculated_merkle != block_header.merkle_root:
            return False, "Invalid merkle root"
            
        # Verify timestamp (Bitcoin rules)
        current_time = int(time.time())
        if block_header.timestamp > current_time + 7200:  # 2 hours future limit
            return False, "Block timestamp too far in future"
            
        # Verify minimum confirmations
        if block_header.confirmations < self.min_confirmations:
            return False, "Insufficient confirmations"
            
        # Verify transaction sequence
        if not self._verify_transaction_sequence(transactions):
            return False, "Invalid transaction sequence"
            
        return True, "Valid block"

    def _verify_transaction_sequence(self, transactions: List[Dict]) -> bool:
        """Verify transaction ordering and dependencies"""
        tx_ids = set()
        for tx in transactions:
            # Check transaction ID not duplicated
            if tx["id"] in tx_ids:
                return False
            tx_ids.add(tx["id"])
            
            # Verify input transactions exist
            for input_tx in tx.get("inputs", []):
                if input_tx["tx_id"] not in tx_ids:
                    return False
                    
        return True

    def _calculate_merkle_root(self, transactions: List[Dict]) -> str:
        """Calculate merkle root hash (Bitcoin-style)"""
        if not transactions:
            return hashlib.sha256(b"").hexdigest()
            
        # Get transaction hashes
        tx_hashes = [tx["hash"] for tx in transactions]
        
        # Build merkle tree
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 == 1:
                tx_hashes.append(tx_hashes[-1])
                
            next_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i+1]
                next_hash = hashlib.sha256(
                    hashlib.sha256(combined.encode()).digest()
                ).hexdigest()
                next_level.append(next_hash)
            tx_hashes = next_level
            
        return tx_hashes[0]

    def validate_offline_mesh(
        self,
        block_header: BlockHeader,
        transactions: List[Dict],
        mesh_signatures: List[str]
    ) -> Tuple[bool, str]:
        """
        Offline mesh validation with local consensus
        """
        # Verify basic block structure
        block_hash = self.calculate_block_hash(block_header)
        if not block_hash.startswith("0" * (self.difficulty - 2)):  # Reduced difficulty
            return False, "Invalid lightweight proof"
            
        # Verify mesh signatures (minimum 3 validators)
        if len(mesh_signatures) < 3:
            return False, "Insufficient mesh validators"
            
        # Verify local timestamp
        local_time = int(time.time())
        if abs(block_header.timestamp - local_time) > 86400:  # 24 hour limit
            return False, "Block timestamp out of local acceptable range"
            
        # Add to offline buffer for later sync
        self.offline_buffer.append({
            "header": block_header,
            "transactions": transactions,
            "signatures": mesh_signatures,
            "local_timestamp": local_time
        })
            
        return True, "Valid offline block (pending online sync)"

    def calculate_merkle_root(self, transactions: List[Dict]) -> str:
        """Calculate merkle root of transactions"""
        if not transactions:
            return hashlib.sha256("empty".encode()).hexdigest()
            
        # Hash all transactions
        transaction_hashes = [
            hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
            for tx in transactions
        ]
        
        # Build merkle tree
        while len(transaction_hashes) > 1:
            if len(transaction_hashes) % 2 != 0:
                transaction_hashes.append(transaction_hashes[-1])
                
            next_level = []
            for i in range(0, len(transaction_hashes), 2):
                combined = transaction_hashes[i] + transaction_hashes[i+1]
                next_hash = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(next_hash)
            transaction_hashes = next_level
            
        return transaction_hashes[0]

    def sync_offline_blocks(self) -> List[Dict]:
        """
        Sync offline blocks when connection is restored
        Returns list of conflicts for resolution
        """
        conflicts = []
        
        for offline_block in self.offline_buffer:
            # Verify if block was already included
            if self._check_block_exists(offline_block["header"]):
                conflicts.append({
                    "type": "duplicate_block",
                    "block": offline_block,
                    "resolution": "skip"
                })
                continue
                
            # Verify if transactions conflict
            tx_conflicts = self._check_transaction_conflicts(
                offline_block["transactions"]
            )
            if tx_conflicts:
                conflicts.append({
                    "type": "transaction_conflict",
                    "block": offline_block,
                    "conflicts": tx_conflicts,
                    "resolution": "pending"
                })
                continue
                
            # If no conflicts, prepare for inclusion
            conflicts.append({
                "type": "ready_for_inclusion",
                "block": offline_block,
                "resolution": "include"
            })
            
        return conflicts

    def _check_block_exists(self, header: BlockHeader) -> bool:
        """Check if block was already included in main chain"""
        # Implementation depends on blockchain storage system
        pass

    def _check_transaction_conflicts(
        self,
        transactions: List[Dict]
    ) -> List[Dict]:
        """Check for transaction conflicts with main chain"""
        # Implementation depends on transaction storage system
        pass 