"""
LogiChain Mesh Storage
Handles persistent storage for mesh network data
"""

import os
import json
import sqlite3
import logging
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import asdict
from .hybrid_manager import NodeStatus, MeshNode
from .validator import ContractStatus, MeshContract, ContractSnapshot

logger = logging.getLogger(__name__)

class MeshStorage:
    """Mesh network storage manager"""
    
    def __init__(
        self,
        storage_dir: str = "mesh_data",
        db_file: str = "mesh.db"
    ):
        self.storage_dir = Path(storage_dir)
        self.db_file = self.storage_dir / db_file
        
        # Create storage directory
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Thread lock
        self._lock = threading.Lock()
        
    def _init_database(self):
        """Initialize SQLite database"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Create nodes table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS nodes (
                        node_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        last_seen INTEGER NOT NULL,
                        stake REAL NOT NULL,
                        location TEXT,
                        is_bridge INTEGER NOT NULL
                    )
                """)
                
                # Create contracts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS contracts (
                        contract_id TEXT PRIMARY KEY,
                        genesis_hash TEXT NOT NULL,
                        value REAL NOT NULL,
                        status TEXT NOT NULL,
                        snapshot_a TEXT NOT NULL,
                        snapshot_b TEXT,
                        penalties TEXT,
                        timestamp INTEGER NOT NULL
                    )
                """)
                
                # Create sync state table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sync_state (
                        node_id TEXT PRIMARY KEY,
                        height INTEGER NOT NULL,
                        latest_hash TEXT NOT NULL,
                        state_hash TEXT NOT NULL,
                        timestamp INTEGER NOT NULL
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
            
    def store_node(self, node: MeshNode):
        """Store node data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO nodes
                    (node_id, status, last_seen, stake, location, is_bridge)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    node.node_id,
                    node.status.value,
                    node.last_seen,
                    node.stake,
                    node.location,
                    1 if node.node_id in self.bridge_nodes else 0
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store node: {str(e)}")
            raise
            
    def get_node(self, node_id: str) -> Optional[MeshNode]:
        """Get node data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT status, last_seen, stake, location, is_bridge
                    FROM nodes
                    WHERE node_id = ?
                """, (node_id,))
                
                row = cursor.fetchone()
                if row:
                    return MeshNode(
                        node_id=node_id,
                        status=NodeStatus(row[0]),
                        last_seen=row[1],
                        stake=row[2],
                        location=row[3]
                    )
                    
                return None
                
        except Exception as e:
            logger.error(f"Failed to get node: {str(e)}")
            raise
            
    def get_all_nodes(self) -> List[MeshNode]:
        """Get all nodes"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM nodes")
                
                nodes = []
                for row in cursor.fetchall():
                    nodes.append(MeshNode(
                        node_id=row[0],
                        status=NodeStatus(row[1]),
                        last_seen=row[2],
                        stake=row[3],
                        location=row[4]
                    ))
                    
                return nodes
                
        except Exception as e:
            logger.error(f"Failed to get nodes: {str(e)}")
            raise
            
    def delete_node(self, node_id: str):
        """Delete node data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to delete node: {str(e)}")
            raise
            
    def store_contract(self, contract: MeshContract):
        """Store contract data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO contracts
                    (contract_id, genesis_hash, value, status, snapshot_a,
                     snapshot_b, penalties, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    contract.contract_id,
                    contract.genesis_hash,
                    contract.value,
                    contract.status.value,
                    json.dumps(asdict(contract.snapshot_a)),
                    json.dumps(asdict(contract.snapshot_b)) if contract.snapshot_b else None,
                    json.dumps(contract.penalties),
                    int(contract.snapshot_a.timestamp)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store contract: {str(e)}")
            raise
            
    def get_contract(self, contract_id: str) -> Optional[MeshContract]:
        """Get contract data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT genesis_hash, value, status, snapshot_a,
                           snapshot_b, penalties
                    FROM contracts
                    WHERE contract_id = ?
                """, (contract_id,))
                
                row = cursor.fetchone()
                if row:
                    return MeshContract(
                        contract_id=contract_id,
                        genesis_hash=row[0],
                        value=row[1],
                        status=ContractStatus(row[2]),
                        snapshot_a=ContractSnapshot(**json.loads(row[3])),
                        snapshot_b=ContractSnapshot(**json.loads(row[4])) if row[4] else None,
                        penalties=json.loads(row[5])
                    )
                    
                return None
                
        except Exception as e:
            logger.error(f"Failed to get contract: {str(e)}")
            raise
            
    def get_pending_contracts(self) -> List[MeshContract]:
        """Get pending contracts"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT contract_id, genesis_hash, value, status,
                           snapshot_a, snapshot_b, penalties
                    FROM contracts
                    WHERE status IN ('pending', 'handshake')
                """)
                
                contracts = []
                for row in cursor.fetchall():
                    contracts.append(MeshContract(
                        contract_id=row[0],
                        genesis_hash=row[1],
                        value=row[2],
                        status=ContractStatus(row[3]),
                        snapshot_a=ContractSnapshot(**json.loads(row[4])),
                        snapshot_b=ContractSnapshot(**json.loads(row[5])) if row[5] else None,
                        penalties=json.loads(row[6])
                    ))
                    
                return contracts
                
        except Exception as e:
            logger.error(f"Failed to get pending contracts: {str(e)}")
            raise
            
    def delete_contract(self, contract_id: str):
        """Delete contract data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM contracts WHERE contract_id = ?", (contract_id,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to delete contract: {str(e)}")
            raise
            
    def store_sync_state(
        self,
        node_id: str,
        height: int,
        latest_hash: str,
        state_hash: str,
        timestamp: int
    ):
        """Store sync state"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO sync_state
                    (node_id, height, latest_hash, state_hash, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (node_id, height, latest_hash, state_hash, timestamp))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store sync state: {str(e)}")
            raise
            
    def get_sync_state(
        self,
        node_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get sync state"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT height, latest_hash, state_hash, timestamp
                    FROM sync_state
                    WHERE node_id = ?
                """, (node_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        "height": row[0],
                        "latest_hash": row[1],
                        "state_hash": row[2],
                        "timestamp": row[3]
                    }
                    
                return None
                
        except Exception as e:
            logger.error(f"Failed to get sync state: {str(e)}")
            raise
            
    def delete_sync_state(self, node_id: str):
        """Delete sync state"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sync_state WHERE node_id = ?", (node_id,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to delete sync state: {str(e)}")
            raise
            
    def cleanup_expired_data(self, expiry_time: int):
        """Clean up expired data"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Delete expired nodes
                cursor.execute("""
                    DELETE FROM nodes
                    WHERE last_seen < ?
                """, (expiry_time,))
                
                # Delete expired contracts
                cursor.execute("""
                    DELETE FROM contracts
                    WHERE timestamp < ?
                """, (expiry_time,))
                
                # Delete expired sync states
                cursor.execute("""
                    DELETE FROM sync_state
                    WHERE timestamp < ?
                """, (expiry_time,))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {str(e)}")
            raise
            
    def export_data(self, export_dir: str):
        """Export storage data"""
        try:
            export_path = Path(export_dir)
            export_path.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Export nodes
                cursor.execute("SELECT * FROM nodes")
                nodes = cursor.fetchall()
                with open(export_path / "nodes.json", "w") as f:
                    json.dump(nodes, f, indent=2)
                    
                # Export contracts
                cursor.execute("SELECT * FROM contracts")
                contracts = cursor.fetchall()
                with open(export_path / "contracts.json", "w") as f:
                    json.dump(contracts, f, indent=2)
                    
                # Export sync states
                cursor.execute("SELECT * FROM sync_state")
                sync_states = cursor.fetchall()
                with open(export_path / "sync_states.json", "w") as f:
                    json.dump(sync_states, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Failed to export data: {str(e)}")
            raise
            
    def import_data(self, import_dir: str):
        """Import storage data"""
        try:
            import_path = Path(import_dir)
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Import nodes
                if (import_path / "nodes.json").exists():
                    with open(import_path / "nodes.json", "r") as f:
                        nodes = json.load(f)
                        cursor.executemany("""
                            INSERT OR REPLACE INTO nodes
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, nodes)
                        
                # Import contracts
                if (import_path / "contracts.json").exists():
                    with open(import_path / "contracts.json", "r") as f:
                        contracts = json.load(f)
                        cursor.executemany("""
                            INSERT OR REPLACE INTO contracts
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, contracts)
                        
                # Import sync states
                if (import_path / "sync_states.json").exists():
                    with open(import_path / "sync_states.json", "r") as f:
                        sync_states = json.load(f)
                        cursor.executemany("""
                            INSERT OR REPLACE INTO sync_state
                            VALUES (?, ?, ?, ?, ?)
                        """, sync_states)
                        
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to import data: {str(e)}")
            raise 