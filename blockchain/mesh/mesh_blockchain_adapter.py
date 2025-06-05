"""
LogiChain Mesh Blockchain Adapter
Integrates mesh storage with blockchain
"""

import time
import logging
from typing import Dict, List, Optional, Any
from ..core.blockchain import Blockchain
from .storage import MeshStorage
from .hybrid_manager import HybridMeshManager
from .mesh_logger import MeshLogger

logger = logging.getLogger(__name__)

class MeshBlockchainAdapter:
    """Adapter between mesh storage and blockchain"""
    
    def __init__(
        self,
        blockchain: Blockchain,
        storage: MeshStorage,
        hybrid_manager: HybridMeshManager,
        mesh_logger: MeshLogger
    ):
        self.blockchain = blockchain
        self.storage = storage
        self.hybrid_manager = hybrid_manager
        self.mesh_logger = mesh_logger
        
    def sync_blockchain_state(self):
        """Synchronize blockchain state with mesh storage"""
        try:
            # Get current blockchain state
            height = self.blockchain.get_height()
            latest_hash = self.blockchain.get_latest_hash()
            state_hash = self.blockchain.get_state_hash()
            timestamp = int(time.time())
            
            # Store sync state
            self.storage.store_sync_state(
                node_id=self.blockchain.node_id,
                height=height,
                latest_hash=latest_hash,
                state_hash=state_hash,
                timestamp=timestamp
            )
            
            self.mesh_logger.log_sync_event(
                node_id=self.blockchain.node_id,
                sync_type="blockchain_state",
                height=height,
                status="success",
                details={
                    "latest_hash": latest_hash,
                    "state_hash": state_hash
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to sync blockchain state: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="blockchain_sync_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def sync_pending_contracts(self):
        """Synchronize pending contracts with blockchain"""
        try:
            # Get pending contracts
            contracts = self.storage.get_pending_contracts()
            
            for contract in contracts:
                try:
                    # Check if contract exists in blockchain
                    if self.blockchain.get_contract(contract.contract_id):
                        continue
                        
                    # Add contract to blockchain
                    if self.blockchain.add_contract({
                        "contract_id": contract.contract_id,
                        "genesis_hash": contract.genesis_hash,
                        "value": contract.value,
                        "snapshot_a": contract.snapshot_a.to_dict(),
                        "snapshot_b": contract.snapshot_b.to_dict() if contract.snapshot_b else None,
                        "status": contract.status.value,
                        "penalties": contract.penalties
                    }):
                        self.mesh_logger.log_contract_event(
                            contract_id=contract.contract_id,
                            event_type="blockchain_sync",
                            status="success",
                            node_id=self.blockchain.node_id
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to sync contract {contract.contract_id}: {str(e)}")
                    
                    self.mesh_logger.log_error(
                        error_type="contract_sync_failed",
                        message=str(e),
                        node_id=self.blockchain.node_id,
                        details={"contract_id": contract.contract_id}
                    )
                    
        except Exception as e:
            error_msg = f"Failed to sync pending contracts: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="contracts_sync_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def sync_node_states(self):
        """Synchronize node states with blockchain"""
        try:
            # Get all nodes
            nodes = self.storage.get_all_nodes()
            
            for node in nodes:
                try:
                    # Update node state in blockchain
                    self.blockchain.update_node_state(
                        node_id=node.node_id,
                        state={
                            "status": node.status.value,
                            "last_seen": node.last_seen,
                            "stake": node.stake,
                            "location": node.location
                        }
                    )
                    
                    self.mesh_logger.log_node_event(
                        node_id=node.node_id,
                        event_type="blockchain_sync",
                        status="success",
                        details={
                            "status": node.status.value,
                            "stake": node.stake
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to sync node {node.node_id}: {str(e)}")
                    
                    self.mesh_logger.log_error(
                        error_type="node_sync_failed",
                        message=str(e),
                        node_id=node.node_id
                    )
                    
        except Exception as e:
            error_msg = f"Failed to sync node states: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="nodes_sync_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def handle_blockchain_event(self, event: Dict[str, Any]):
        """Handle blockchain event"""
        try:
            event_type = event.get("type")
            
            if event_type == "contract_added":
                # Store contract in mesh
                contract_data = event.get("contract")
                if contract_data:
                    self.storage.store_contract(contract_data)
                    
                    self.mesh_logger.log_contract_event(
                        contract_id=contract_data["contract_id"],
                        event_type="blockchain_event",
                        status="stored",
                        node_id=self.blockchain.node_id
                    )
                    
            elif event_type == "node_updated":
                # Store node in mesh
                node_data = event.get("node")
                if node_data:
                    self.storage.store_node(node_data)
                    
                    self.mesh_logger.log_node_event(
                        node_id=node_data["node_id"],
                        event_type="blockchain_event",
                        status="stored",
                        details=node_data
                    )
                    
            elif event_type == "state_changed":
                # Sync blockchain state
                self.sync_blockchain_state()
                
        except Exception as e:
            error_msg = f"Failed to handle blockchain event: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="event_handling_failed",
                message=error_msg,
                node_id=self.blockchain.node_id,
                details={"event_type": event.get("type")}
            )
            
    def cleanup_expired_data(self, expiry_time: Optional[int] = None):
        """Clean up expired data"""
        try:
            # Use current time if not specified
            if expiry_time is None:
                expiry_time = int(time.time()) - (24 * 60 * 60)  # 24 hours
                
            # Clean up storage
            self.storage.cleanup_expired_data(expiry_time)
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="cleanup",
                status="success",
                details={"expiry_time": expiry_time}
            )
            
        except Exception as e:
            error_msg = f"Failed to cleanup expired data: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="cleanup_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def export_mesh_data(self, export_dir: str):
        """Export mesh data"""
        try:
            # Export storage data
            self.storage.export_data(export_dir)
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="export",
                status="success",
                details={"export_dir": export_dir}
            )
            
        except Exception as e:
            error_msg = f"Failed to export mesh data: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="export_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            )
            
    def import_mesh_data(self, import_dir: str):
        """Import mesh data"""
        try:
            # Import storage data
            self.storage.import_data(import_dir)
            
            # Sync with blockchain
            self.sync_blockchain_state()
            self.sync_pending_contracts()
            self.sync_node_states()
            
            self.mesh_logger.log_node_event(
                node_id=self.blockchain.node_id,
                event_type="import",
                status="success",
                details={"import_dir": import_dir}
            )
            
        except Exception as e:
            error_msg = f"Failed to import mesh data: {str(e)}"
            logger.error(error_msg)
            
            self.mesh_logger.log_error(
                error_type="import_failed",
                message=error_msg,
                node_id=self.blockchain.node_id
            ) 