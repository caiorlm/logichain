"""
LogiChain Sync Manager
Handles synchronization between mesh nodes
"""

import json
import time
import asyncio
import logging
import threading
from typing import Dict, Set, Optional, List
from dataclasses import dataclass
from ..core.blockchain import Blockchain
from .hybrid_manager import HybridMeshManager
from .mesh_logger import MeshLogger
from .validator import MeshValidator, ValidationResult

logger = logging.getLogger(__name__)

@dataclass
class SyncState:
    """Node synchronization state"""
    height: int
    latest_hash: str
    state_hash: str
    timestamp: int
    signature: str

class SyncManager:
    """Mesh network synchronization manager"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        hybrid_manager: HybridMeshManager,
        mesh_logger: MeshLogger,
        validator: MeshValidator
    ):
        self.blockchain = blockchain
        self.hybrid_manager = hybrid_manager
        self.mesh_logger = mesh_logger
        self.validator = validator
        
        # Sync state
        self.running = False
        self.pending_sync: Set[str] = set()
        self.sync_state: Dict[str, SyncState] = {}
        
        # Locks
        self._sync_lock = threading.Lock()
        
    def start(self):
        """Start sync manager"""
        try:
            self.running = True
            
            # Start background tasks
            threading.Thread(
                target=self._sync_loop,
                daemon=True
            ).start()
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="sync_manager_start",
                status="success"
            )
            
            logger.info("Sync manager started")
            
        except Exception as e:
            error_msg = f"Failed to start sync manager: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="sync_manager_start_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def stop(self):
        """Stop sync manager"""
        try:
            self.running = False
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="sync_manager_stop",
                status="success"
            )
            
            logger.info("Sync manager stopped")
            
        except Exception as e:
            error_msg = f"Failed to stop sync manager: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="sync_manager_stop_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def request_sync(self, node_id: str):
        """Request synchronization with node"""
        try:
            with self._sync_lock:
                if node_id not in self.pending_sync:
                    self.pending_sync.add(node_id)
                    
                    self.mesh_logger.log_sync_event(
                        node_id=node_id,
                        sync_type="request",
                        height=self.blockchain.get_height(),
                        status="pending"
                    )
                    
        except Exception as e:
            error_msg = f"Failed to request sync: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="sync_request_failed",
                message=error_msg,
                node_id=node_id
            )
            
    def handle_sync_request(
        self,
        node_id: str,
        request_data: Dict
    ) -> Optional[Dict]:
        """Handle synchronization request"""
        try:
            # Validate request
            result = self.validator.validate_sync(node_id, request_data)
            if not result.valid:
                self.mesh_logger.log_error(
                    error_type="sync_request_invalid",
                    message=result.error or "Invalid sync request",
                    node_id=node_id
                )
                return None
                
            # Get current state
            height = self.blockchain.get_height()
            latest_hash = self.blockchain.get_latest_hash()
            state_hash = self.blockchain.get_state_hash()
            
            # Create response
            response = {
                "height": height,
                "latest_hash": latest_hash,
                "state_hash": state_hash,
                "timestamp": int(time.time())
            }
            
            # Sign response
            response["signature"] = self.blockchain.sign_message(response)
            
            # Update sync state
            with self._sync_lock:
                self.sync_state[node_id] = SyncState(**response)
                
            self.mesh_logger.log_sync_event(
                node_id=node_id,
                sync_type="response",
                height=height,
                status="success",
                details=response
            )
            
            return response
            
        except Exception as e:
            error_msg = f"Failed to handle sync request: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="sync_request_failed",
                message=error_msg,
                node_id=node_id
            )
            
            return None
            
    def handle_sync_response(
        self,
        node_id: str,
        response_data: Dict
    ) -> bool:
        """Handle synchronization response"""
        try:
            # Validate response
            result = self.validator.validate_sync(node_id, response_data)
            if not result.valid:
                self.mesh_logger.log_error(
                    error_type="sync_response_invalid",
                    message=result.error or "Invalid sync response",
                    node_id=node_id
                )
                return False
                
            # Get current state
            height = self.blockchain.get_height()
            state_hash = self.blockchain.get_state_hash()
            
            # Compare states
            their_height = response_data["height"]
            their_state = response_data["state_hash"]
            
            if their_height > height or their_state != state_hash:
                # Request snapshot
                self._request_snapshot(node_id)
                
            # Update sync state
            with self._sync_lock:
                self.sync_state[node_id] = SyncState(**response_data)
                self.pending_sync.discard(node_id)
                
            self.mesh_logger.log_sync_event(
                node_id=node_id,
                sync_type="response_handled",
                height=their_height,
                status="success",
                details={"needs_snapshot": their_height > height}
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to handle sync response: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="sync_response_failed",
                message=error_msg,
                node_id=node_id
            )
            
            return False
            
    def handle_snapshot(
        self,
        node_id: str,
        snapshot_data: Dict
    ) -> bool:
        """Handle blockchain snapshot"""
        try:
            # Validate snapshot
            result = self.validator.validate_snapshot(node_id, snapshot_data)
            if not result.valid:
                self.mesh_logger.log_error(
                    error_type="snapshot_invalid",
                    message=result.error or "Invalid snapshot",
                    node_id=node_id
                )
                return False
                
            # Apply snapshot
            if self.blockchain.apply_snapshot(snapshot_data):
                self.mesh_logger.log_sync_event(
                    node_id=node_id,
                    sync_type="snapshot",
                    height=snapshot_data["height"],
                    status="success",
                    details=result.details
                )
                return True
                
            self.mesh_logger.log_error(
                error_type="snapshot_apply_failed",
                message="Failed to apply snapshot",
                node_id=node_id
            )
            return False
            
        except Exception as e:
            error_msg = f"Failed to handle snapshot: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="snapshot_failed",
                message=error_msg,
                node_id=node_id
            )
            
            return False
            
    def _request_snapshot(self, node_id: str):
        """Request blockchain snapshot"""
        try:
            # Create request
            request = {
                "type": "snapshot_request",
                "node_id": self.blockchain.node_id,
                "height": self.blockchain.get_height(),
                "timestamp": int(time.time())
            }
            
            # Sign request
            request["signature"] = self.blockchain.sign_message(request)
            
            # Send request
            self.hybrid_manager.send_message(node_id, request)
            
            self.mesh_logger.log_sync_event(
                node_id=node_id,
                sync_type="snapshot_request",
                height=request["height"],
                status="sent"
            )
            
        except Exception as e:
            error_msg = f"Failed to request snapshot: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="snapshot_request_failed",
                message=error_msg,
                node_id=node_id
            )
            
    def _sync_loop(self):
        """Background synchronization loop"""
        while self.running:
            try:
                # Get current state
                height = self.blockchain.get_height()
                latest_hash = self.blockchain.get_latest_hash()
                state_hash = self.blockchain.get_state_hash()
                
                # Create sync message
                message = {
                    "type": "sync",
                    "height": height,
                    "latest_hash": latest_hash,
                    "state_hash": state_hash,
                    "timestamp": int(time.time())
                }
                
                # Sign message
                message["signature"] = self.blockchain.sign_message(message)
                
                # Broadcast to pending nodes
                with self._sync_lock:
                    for node_id in self.pending_sync:
                        self.hybrid_manager.send_message(node_id, message)
                        
                        self.mesh_logger.log_sync_event(
                            node_id=node_id,
                            sync_type="broadcast",
                            height=height,
                            status="sent"
                        )
                        
                # Sleep
                time.sleep(self.hybrid_manager.config.network.sync_interval)
                
            except Exception as e:
                error_msg = f"Sync loop error: {str(e)}"
                logger.error(error_msg)
                
                self.mesh_logger.log_error(
                    error_type="sync_loop_failed",
                    message=error_msg,
                    node_id=self.blockchain.node_id
                )
                
                time.sleep(5) 