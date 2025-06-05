"""
LogiChain Contract Validator
Handles contract validation with time checks and sync blocking
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .time_validation import TimeValidationSystem, TimeProof
from .sync_blocker import SyncBlocker, SyncState
from .quorum import TrustedNodeQuorum, QuorumState
from .offline_cache import OfflineCache, OfflineState
from .mesh_network import MeshNetwork, NetworkMode

class ContractState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    INVALID = "invalid"

@dataclass
class ContractValidation:
    """Contract validation result"""
    valid: bool
    state: ContractState
    error: Optional[str] = None
    details: Optional[Dict] = None

class ContractValidator:
    """Validates contracts with time and sync checks"""
    
    def __init__(
        self,
        time_validator: TimeValidationSystem,
        sync_blocker: SyncBlocker,
        quorum: TrustedNodeQuorum,
        offline_cache: OfflineCache,
        mesh_network: MeshNetwork,
        contract_timeout: int = 3600  # 1 hour
    ):
        self.time_validator = time_validator
        self.sync_blocker = sync_blocker
        self.quorum = quorum
        self.offline_cache = offline_cache
        self.mesh_network = mesh_network
        self.contract_timeout = contract_timeout
        
    async def validate_contract_accept(
        self,
        contract_id: str,
        timestamp: float,
        block_hash: str,
        previous_hash: str,
        allow_offline: bool = True
    ) -> ContractValidation:
        """Validate contract acceptance"""
        try:
            # Get current network mode
            network_mode, state = self.mesh_network.get_network_state()
            
            # If we're offline and offline not allowed
            if network_mode == NetworkMode.OFFLINE and not allow_offline:
                return ContractValidation(
                    valid=False,
                    state=ContractState.INVALID,
                    error="Network offline and offline mode not allowed"
                )
                
            # Check for existing contract in snapshots
            if self.mesh_network.latest_snapshot:
                if contract_id in self.mesh_network.latest_snapshot.contracts:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Contract already exists"
                    )
                    
            # If offline/hybrid, store in offline cache
            if network_mode in (NetworkMode.OFFLINE, NetworkMode.HYBRID):
                data = {
                    "timestamp": timestamp,
                    "block_hash": block_hash,
                    "previous_hash": previous_hash
                }
                
                # Generate local proof
                local_proof = self.offline_cache.generate_local_proof(data)
                
                # Store offline operation
                operation_id = await self.offline_cache.store_offline_operation(
                    contract_id=contract_id,
                    operation_type="contract_accept",
                    data=data,
                    local_proof=local_proof
                )
                
                # Broadcast to mesh network
                await self.mesh_network.broadcast_transaction({
                    "type": "contract_accept",
                    "contract_id": contract_id,
                    "data": data,
                    "local_proof": local_proof,
                    "operation_id": operation_id
                }, mode=network_mode)
                
                return ContractValidation(
                    valid=True,
                    state=ContractState.PENDING,
                    details={
                        "operation_id": operation_id,
                        "offline": True,
                        "local_proof": local_proof,
                        "network_mode": network_mode.value
                    }
                )
                
            # Online validation
            if network_mode in (NetworkMode.ONLINE, NetworkMode.HYBRID):
                # Validate timestamp
                time_valid, time_error = self.time_validator.validate_timestamp(
                    timestamp,
                    block_hash,
                    previous_hash
                )
                
                if not time_valid:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error=f"Invalid timestamp: {time_error}"
                    )
                    
                # Create time proof
                time_proof = self.time_validator.create_time_proof(
                    timestamp,
                    block_hash,
                    previous_hash
                )
                
                if not time_proof:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Failed to create time proof"
                    )
                    
                # Propose quorum vote
                content = {
                    "contract_id": contract_id,
                    "timestamp": timestamp,
                    "block_hash": block_hash,
                    "previous_hash": previous_hash,
                    "time_proof": time_proof.__dict__
                }
                
                vote_hash, vote_ok = await self.quorum.propose_vote(
                    content,
                    "contract_accept"
                )
                
                if not vote_ok:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Failed to propose vote"
                    )
                    
                # Wait for quorum
                quorum_ok = await self.quorum.wait_for_quorum(
                    vote_hash,
                    timeout=self.contract_timeout
                )
                
                if not quorum_ok:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Failed to reach quorum"
                    )
                    
                # Block operation until complete
                self.sync_blocker.block_operation(f"contract_accept:{contract_id}")
                
                # Broadcast to network
                await self.mesh_network.broadcast_transaction({
                    "type": "contract_accept",
                    "contract_id": contract_id,
                    "content": content,
                    "vote_hash": vote_hash,
                    "time_proof": time_proof.__dict__
                })
                
                return ContractValidation(
                    valid=True,
                    state=ContractState.ACTIVE,
                    details={
                        "vote_hash": vote_hash,
                        "time_proof": time_proof.__dict__,
                        "network_mode": network_mode.value
                    }
                )
                
        except Exception as e:
            return ContractValidation(
                valid=False,
                state=ContractState.INVALID,
                error=f"Validation error: {str(e)}"
            )
            
    async def validate_contract_complete(
        self,
        contract_id: str,
        completion_proof: Dict,
        allow_offline: bool = True
    ) -> ContractValidation:
        """Validate contract completion"""
        try:
            # Get current network mode
            network_mode, state = self.mesh_network.get_network_state()
            
            # If we're offline and offline not allowed
            if network_mode == NetworkMode.OFFLINE and not allow_offline:
                return ContractValidation(
                    valid=False,
                    state=ContractState.INVALID,
                    error="Network offline and offline mode not allowed"
                )
                
            # Check contract exists in latest snapshot
            if self.mesh_network.latest_snapshot:
                if contract_id not in self.mesh_network.latest_snapshot.contracts:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Contract not found"
                    )
                    
            # If offline/hybrid, store in offline cache
            if network_mode in (NetworkMode.OFFLINE, NetworkMode.HYBRID):
                data = {
                    "completion_proof": completion_proof,
                    "timestamp": time.time()
                }
                
                # Generate local proof
                local_proof = self.offline_cache.generate_local_proof(data)
                
                # Store offline operation
                operation_id = await self.offline_cache.store_offline_operation(
                    contract_id=contract_id,
                    operation_type="contract_complete",
                    data=data,
                    local_proof=local_proof
                )
                
                # Broadcast to mesh network
                await self.mesh_network.broadcast_transaction({
                    "type": "contract_complete",
                    "contract_id": contract_id,
                    "data": data,
                    "local_proof": local_proof,
                    "operation_id": operation_id
                }, mode=network_mode)
                
                return ContractValidation(
                    valid=True,
                    state=ContractState.PENDING,
                    details={
                        "operation_id": operation_id,
                        "offline": True,
                        "local_proof": local_proof,
                        "network_mode": network_mode.value
                    }
                )
                
            # Online validation
            if network_mode in (NetworkMode.ONLINE, NetworkMode.HYBRID):
                # Validate completion proof
                if not self._validate_completion_proof(completion_proof):
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Invalid completion proof"
                    )
                    
                # Propose quorum vote
                content = {
                    "contract_id": contract_id,
                    "completion_proof": completion_proof,
                    "timestamp": time.time()
                }
                
                vote_hash, vote_ok = await self.quorum.propose_vote(
                    content,
                    "contract_complete"
                )
                
                if not vote_ok:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Failed to propose vote"
                    )
                    
                # Wait for quorum
                quorum_ok = await self.quorum.wait_for_quorum(
                    vote_hash,
                    timeout=self.contract_timeout
                )
                
                if not quorum_ok:
                    return ContractValidation(
                        valid=False,
                        state=ContractState.INVALID,
                        error="Failed to reach quorum"
                    )
                    
                # Unblock operations
                self.sync_blocker.unblock_operation(f"contract_accept:{contract_id}")
                self.sync_blocker.unblock_operation(f"contract_complete:{contract_id}")
                
                # Broadcast to network
                await self.mesh_network.broadcast_transaction({
                    "type": "contract_complete",
                    "contract_id": contract_id,
                    "content": content,
                    "vote_hash": vote_hash
                })
                
                return ContractValidation(
                    valid=True,
                    state=ContractState.COMPLETED,
                    details={
                        "vote_hash": vote_hash,
                        "network_mode": network_mode.value
                    }
                )
                
        except Exception as e:
            return ContractValidation(
                valid=False,
                state=ContractState.INVALID,
                error=f"Validation error: {str(e)}"
            )
            
    def _validate_completion_proof(self, proof: Dict) -> bool:
        """Validate contract completion proof"""
        try:
            # Check required fields
            required = {"timestamp", "location", "signature"}
            if not all(f in proof for f in required):
                return False
                
            # Validate timestamp
            if proof["timestamp"] > time.time():
                return False
                
            # Additional validation can be added here
            return True
            
        except Exception:
            return False
            
    async def sync_offline_operations(self) -> Dict[str, bool]:
        """Synchronize pending offline operations"""
        try:
            # Sync network snapshots first
            await self.mesh_network.sync_snapshots()
            
            # Get pending operations
            pending = self.offline_cache.get_pending_operations()
            results = {}
            
            for operation in pending:
                try:
                    # Validate local proof
                    if not self.offline_cache.validate_local_proof(operation.local_proof):
                        await self.offline_cache.sync_operation(
                            operation.operation_id,
                            success=False
                        )
                        results[operation.operation_id] = False
                        continue
                        
                    # Check if operation already exists in snapshot
                    if self.mesh_network.latest_snapshot:
                        if operation.contract_id in self.mesh_network.latest_snapshot.contracts:
                            # Contract already processed
                            await self.offline_cache.sync_operation(
                                operation.operation_id,
                                success=True
                            )
                            results[operation.operation_id] = True
                            continue
                            
                    # Process based on operation type
                    if operation.operation_type == "contract_accept":
                        validation = await self.validate_contract_accept(
                            contract_id=operation.contract_id,
                            timestamp=operation.data["timestamp"],
                            block_hash=operation.data["block_hash"],
                            previous_hash=operation.data["previous_hash"],
                            allow_offline=False
                        )
                    elif operation.operation_type == "contract_complete":
                        validation = await self.validate_contract_complete(
                            contract_id=operation.contract_id,
                            completion_proof=operation.data["completion_proof"],
                            allow_offline=False
                        )
                    else:
                        validation = ContractValidation(
                            valid=False,
                            state=ContractState.INVALID,
                            error="Unknown operation type"
                        )
                        
                    # Update operation status
                    success = validation.valid
                    await self.offline_cache.sync_operation(
                        operation.operation_id,
                        success=success
                    )
                    results[operation.operation_id] = success
                    
                except Exception:
                    results[operation.operation_id] = False
                    
            return results
            
        except Exception:
            return {} 