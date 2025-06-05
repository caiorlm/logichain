"""
Audit API endpoints for LogiChain
"""

from flask import Blueprint, jsonify
from typing import Dict, List
import logging
from datetime import datetime
from ..audit.reward_auditor import RewardAuditor
from ..core.database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create blueprint
audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/audit/rewards/<address>')
def audit_rewards(address: str):
    """Audit mining rewards for an address"""
    try:
        auditor = RewardAuditor()
        audit_data = auditor.audit_miner_rewards(address)
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'data': audit_data
        })
        
    except Exception as e:
        logger.error(f"Error in audit_rewards: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@audit_bp.route('/audit/chain/integrity')
def audit_chain():
    """Audit entire blockchain integrity"""
    try:
        db = DatabaseManager()
        is_valid, errors = db.verify_chain_integrity()
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'is_valid': is_valid,
                'errors': errors
            }
        })
        
    except Exception as e:
        logger.error(f"Error in audit_chain: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@audit_bp.route('/audit/blocks/orphaned')
def audit_orphaned_blocks():
    """Find orphaned blocks"""
    try:
        db = DatabaseManager()
        orphaned = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Find blocks without proper previous_hash links
            cursor.execute("""
                SELECT b1.hash, b1.timestamp
                FROM blocks b1
                LEFT JOIN blocks b2 ON b1.previous_hash = b2.hash
                WHERE b2.hash IS NULL
                AND b1.previous_hash != ?
                ORDER BY b1.timestamp
            """, ('0' * 64,))  # Exclude genesis block
            
            orphaned = [{
                'hash': row[0],
                'timestamp': row[1]
            } for row in cursor.fetchall()]
            
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'orphaned_count': len(orphaned),
                'orphaned_blocks': orphaned
            }
        })
        
    except Exception as e:
        logger.error(f"Error in audit_orphaned_blocks: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@audit_bp.route('/audit/transactions/missing')
def audit_missing_transactions():
    """Find blocks with missing transactions"""
    try:
        db = DatabaseManager()
        missing = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Find blocks without mining reward transactions
            cursor.execute("""
                SELECT b.hash, b.miner_address, b.timestamp
                FROM blocks b
                LEFT JOIN transactions t ON 
                    t.block_hash = b.hash AND 
                    t.tx_type = 'mining_reward'
                WHERE t.tx_hash IS NULL
                ORDER BY b.timestamp
            """)
            
            missing = [{
                'block_hash': row[0],
                'miner_address': row[1],
                'timestamp': row[2]
            } for row in cursor.fetchall()]
            
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'missing_count': len(missing),
                'missing_rewards': missing
            }
        })
        
    except Exception as e:
        logger.error(f"Error in audit_missing_transactions: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@audit_bp.route('/audit/network/peers')
def audit_network_peers():
    """Audit network peer status"""
    try:
        from ..network.p2p_network import P2PNetwork
        network = P2PNetwork()
        
        peers = network.get_peers()
        versions = {}
        for peer in peers:
            versions[peer.version] = versions.get(peer.version, 0) + 1
            
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'peer_count': len(peers),
                'versions': versions,
                'peers': [{
                    'host': p.host,
                    'port': p.port,
                    'version': p.version,
                    'blocks': p.blocks,
                    'is_mining': p.is_mining,
                    'last_seen': p.last_seen
                } for p in peers]
            }
        })
        
    except Exception as e:
        logger.error(f"Error in audit_network_peers: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 