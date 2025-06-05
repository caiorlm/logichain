"""
Sybil attack protection module.
Implements multiple mechanisms to prevent Sybil attacks:
1. Proof of Stake (minimum stake requirement)
2. Reputation System
3. Activity Analysis
4. Network Behavior Monitoring
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import time
import math
import logging
from web3 import Web3
from ..wallet.wallet import Wallet

@dataclass
class NodeActivity:
    """Tracks node activity for Sybil detection"""
    address: str
    join_time: float
    last_active: float
    message_count: int
    consensus_participations: int
    successful_validations: int
    failed_validations: int
    suspicious_activities: int
    connection_patterns: List[Tuple[float, str]]  # [(timestamp, ip)]

class SybilProtection:
    """
    Implements multi-layered Sybil attack protection.
    """
    
    def __init__(
        self,
        min_stake: float = 1000.0,
        min_reputation: float = 0.7,
        activity_window: int = 3600,  # 1 hour window for rate limiting
        max_message_rate: int = 1000,  # Max messages per window
        connection_threshold: int = 5,  # Max simultaneous connections from same IP
        suspicious_threshold: int = 10  # Max suspicious activities before ban
    ):
        self.min_stake = min_stake
        self.min_reputation = min_reputation
        self.activity_window = activity_window
        self.max_message_rate = max_message_rate
        self.connection_threshold = connection_threshold
        self.suspicious_threshold = suspicious_threshold
        
        # Node tracking
        self.nodes: Dict[str, NodeActivity] = {}  # address -> activity
        self.ip_connections: Dict[str, Set[str]] = {}  # ip -> set of addresses
        self.banned_addresses: Set[str] = set()
        self.banned_ips: Set[str] = set()
        
        logging.info("Sybil protection initialized")
    
    def register_node(
        self,
        address: str,
        stake: float,
        reputation: float,
        ip: str
    ) -> bool:
        """
        Register a new node with initial stake and reputation
        
        Args:
            address: Node's blockchain address
            stake: Amount staked by node
            reputation: Node's reputation score (0-1)
            ip: Node's IP address
            
        Returns:
            bool: True if node was registered
        """
        # Check if banned
        if self._is_banned(address, ip):
            logging.warning(f"Banned node attempted registration: {address}")
            return False
        
        # Validate stake and reputation
        if stake < self.min_stake:
            logging.warning(f"Node {address} has insufficient stake")
            return False
            
        if reputation < self.min_reputation:
            logging.warning(f"Node {address} has insufficient reputation")
            return False
            
        # Check IP connection limit
        if ip in self.ip_connections:
            if len(self.ip_connections[ip]) >= self.connection_threshold:
                logging.warning(f"Too many connections from IP: {ip}")
                return False
                
        # Register node
        now = time.time()
        self.nodes[address] = NodeActivity(
            address=address,
            join_time=now,
            last_active=now,
            message_count=0,
            consensus_participations=0,
            successful_validations=0,
            failed_validations=0,
            suspicious_activities=0,
            connection_patterns=[(now, ip)]
        )
        
        # Track IP connection
        if ip not in self.ip_connections:
            self.ip_connections[ip] = set()
        self.ip_connections[ip].add(address)
        
        logging.info(f"Node registered: {address} from {ip}")
        return True
    
    def record_activity(
        self,
        address: str,
        activity_type: str,
        ip: str,
        success: bool = True
    ):
        """
        Record node activity for analysis
        
        Args:
            address: Node address
            activity_type: Type of activity (message, consensus, validation)
            ip: Node's current IP
            success: Whether the activity was successful
        """
        if address not in self.nodes:
            logging.warning(f"Activity from unregistered node: {address}")
            return
            
        node = self.nodes[address]
        now = time.time()
        
        # Update activity timestamp
        node.last_active = now
        
        # Record activity based on type
        if activity_type == "message":
            node.message_count += 1
            
            # Check message rate
            if self._is_rate_limited(node):
                self._record_suspicious_activity(address)
                
        elif activity_type == "consensus":
            node.consensus_participations += 1
            
        elif activity_type == "validation":
            if success:
                node.successful_validations += 1
            else:
                node.failed_validations += 1
                if self._has_high_failure_rate(node):
                    self._record_suspicious_activity(address)
        
        # Check for IP changes
        last_ip = node.connection_patterns[-1][1]
        if ip != last_ip:
            node.connection_patterns.append((now, ip))
            
            # Check for suspicious IP switching
            if self._has_suspicious_ip_pattern(node):
                self._record_suspicious_activity(address)
    
    def _is_rate_limited(self, node: NodeActivity) -> bool:
        """Check if node is exceeding message rate limit"""
        now = time.time()
        window_start = now - self.activity_window
        
        # Count messages in current window
        window_messages = node.message_count
        return window_messages > self.max_message_rate
    
    def _has_high_failure_rate(self, node: NodeActivity) -> bool:
        """Check if node has suspiciously high validation failure rate"""
        total_validations = node.successful_validations + node.failed_validations
        if total_validations < 10:  # Need minimum sample size
            return False
            
        failure_rate = node.failed_validations / total_validations
        return failure_rate > 0.3  # Over 30% failure rate is suspicious
    
    def _has_suspicious_ip_pattern(self, node: NodeActivity) -> bool:
        """Check for suspicious IP switching patterns"""
        if len(node.connection_patterns) < 3:
            return False
            
        # Check frequency of IP changes
        now = time.time()
        recent_changes = [
            p for p in node.connection_patterns
            if now - p[0] <= self.activity_window
        ]
        
        return len(recent_changes) > 5  # More than 5 IP changes per window
    
    def _record_suspicious_activity(self, address: str):
        """Record suspicious activity and check ban threshold"""
        node = self.nodes[address]
        node.suspicious_activities += 1
        
        if node.suspicious_activities >= self.suspicious_threshold:
            self._ban_node(address)
    
    def _ban_node(self, address: str):
        """Ban a node for suspicious behavior"""
        if address not in self.nodes:
            return
            
        node = self.nodes[address]
        self.banned_addresses.add(address)
        
        # Ban all IPs used by node
        for _, ip in node.connection_patterns:
            self.banned_ips.add(ip)
            if ip in self.ip_connections:
                del self.ip_connections[ip]
        
        del self.nodes[address]
        logging.warning(f"Node banned for suspicious activity: {address}")
    
    def _is_banned(self, address: str, ip: str) -> bool:
        """Check if address or IP is banned"""
        return address in self.banned_addresses or ip in self.banned_ips
    
    def analyze_network_behavior(self):
        """
        Analyze overall network behavior for Sybil patterns
        Should be called periodically (e.g. every hour)
        """
        now = time.time()
        
        # Analyze node join patterns
        join_times = [node.join_time for node in self.nodes.values()]
        if self._detect_join_attack(join_times):
            logging.warning("Detected suspicious node join pattern")
            
        # Analyze IP distribution
        ip_counts = {}
        for ip_set in self.ip_connections.values():
            for ip in ip_set:
                ip_counts[ip] = ip_counts.get(ip, 0) + 1
                
        if self._detect_ip_concentration(ip_counts):
            logging.warning("Detected suspicious IP concentration")
            
        # Clean up old data
        self._cleanup_old_data(now)
    
    def _detect_join_attack(self, join_times: List[float]) -> bool:
        """Detect suspicious patterns in node join times"""
        if len(join_times) < 10:
            return False
            
        # Sort join times
        join_times.sort()
        
        # Check for unusually rapid joins
        for i in range(len(join_times) - 5):
            time_span = join_times[i + 5] - join_times[i]
            if time_span < 60:  # 5 nodes joining within 1 minute
                return True
                
        return False
    
    def _detect_ip_concentration(self, ip_counts: Dict[str, int]) -> bool:
        """Detect suspicious concentration of nodes per IP"""
        if not ip_counts:
            return False
            
        total_nodes = sum(ip_counts.values())
        avg_per_ip = total_nodes / len(ip_counts)
        
        # Check for IPs with much higher than average nodes
        return any(count > avg_per_ip * 3 for count in ip_counts.values())
    
    def _cleanup_old_data(self, current_time: float):
        """Clean up old activity data"""
        cutoff = current_time - (self.activity_window * 24)  # Keep 24 windows
        
        # Clean up old connection patterns
        for node in self.nodes.values():
            node.connection_patterns = [
                p for p in node.connection_patterns
                if p[0] > cutoff
            ]
            
        # Reset message counts periodically
        if current_time % self.activity_window == 0:
            for node in self.nodes.values():
                node.message_count = 0
    
    def get_node_stats(self, address: str) -> Optional[Dict]:
        """Get statistics for a node"""
        if address not in self.nodes:
            return None
            
        node = self.nodes[address]
        return {
            'address': node.address,
            'join_time': node.join_time,
            'last_active': node.last_active,
            'message_count': node.message_count,
            'consensus_participations': node.consensus_participations,
            'successful_validations': node.successful_validations,
            'failed_validations': node.failed_validations,
            'suspicious_activities': node.suspicious_activities,
            'ip_changes': len(node.connection_patterns)
        }
    
    def get_network_stats(self) -> Dict:
        """Get overall network statistics"""
        return {
            'total_nodes': len(self.nodes),
            'banned_addresses': len(self.banned_addresses),
            'banned_ips': len(self.banned_ips),
            'unique_ips': len(self.ip_connections),
            'avg_message_rate': sum(n.message_count for n in self.nodes.values()) / len(self.nodes) if self.nodes else 0,
            'avg_success_rate': sum(
                n.successful_validations / (n.successful_validations + n.failed_validations)
                for n in self.nodes.values()
                if n.successful_validations + n.failed_validations > 0
            ) / len(self.nodes) if self.nodes else 0
        } 