from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import time
import asyncio
from enum import Enum
import logging
from collections import defaultdict
import json
import os
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

@dataclass
class Alert:
    level: AlertLevel
    message: str
    timestamp: float
    component: str
    details: Dict

@dataclass
class HealthStatus:
    is_healthy: bool
    reason: str = ""
    metrics: Dict = None

class MetricsCollector:
    def __init__(self):
        self.metrics_history = defaultdict(list)
        self.MAX_HISTORY_SIZE = 1000
        self.metrics_thresholds = {
            "cpu_usage": 80.0,  # percentage
            "memory_usage": 85.0,  # percentage
            "disk_usage": 90.0,  # percentage
            "network_latency": 1000.0,  # milliseconds
            "transaction_rate": 100.0,  # tx/sec
            "error_rate": 5.0,  # percentage
            "invalid_block_rate": 1.0,  # percentage
        }
        
    async def collect(self) -> Dict:
        try:
            # Collect system metrics
            system_metrics = await self._collect_system_metrics()
            
            # Collect blockchain metrics
            blockchain_metrics = await self._collect_blockchain_metrics()
            
            # Collect network metrics
            network_metrics = await self._collect_network_metrics()
            
            # Combine all metrics
            metrics = {
                "system": system_metrics,
                "blockchain": blockchain_metrics,
                "network": network_metrics,
                "timestamp": time.time()
            }
            
            # Store in history
            self._store_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            logging.error(f"Error collecting metrics: {str(e)}")
            return {}
            
    async def _collect_system_metrics(self) -> Dict:
        # This would use actual system monitoring libraries
        # Simplified version for demonstration
        return {
            "cpu_usage": 50.0,
            "memory_usage": 60.0,
            "disk_usage": 70.0,
            "uptime": time.time() - 0  # placeholder for start time
        }
        
    async def _collect_blockchain_metrics(self) -> Dict:
        return {
            "block_height": 1000,
            "transaction_count": 500,
            "pending_transactions": 50,
            "average_block_time": 30.0,
            "network_hashrate": 1000000
        }
        
    async def _collect_network_metrics(self) -> Dict:
        return {
            "connected_peers": 10,
            "network_latency": 100.0,
            "bandwidth_usage": 5000000,
            "active_connections": 20
        }
        
    def _store_metrics(self, metrics: Dict):
        timestamp = metrics["timestamp"]
        
        # Store each metric type separately
        for category, values in metrics.items():
            if category != "timestamp":
                for metric_name, value in values.items():
                    key = f"{category}.{metric_name}"
                    self.metrics_history[key].append((timestamp, value))
                    
                    # Maintain history size limit
                    if len(self.metrics_history[key]) > self.MAX_HISTORY_SIZE:
                        self.metrics_history[key].pop(0)
                        
    def get_metric_history(
        self,
        metric_name: str,
        time_range: Optional[float] = None
    ) -> List[tuple]:
        history = self.metrics_history.get(metric_name, [])
        
        if time_range:
            current_time = time.time()
            history = [
                (ts, val) for ts, val in history
                if current_time - ts <= time_range
            ]
            
        return history

class AlertSystem:
    def __init__(self):
        self.alert_history = []
        self.MAX_HISTORY_SIZE = 1000
        self.alert_handlers = {
            AlertLevel.INFO: self._handle_info,
            AlertLevel.WARNING: self._handle_warning,
            AlertLevel.CRITICAL: self._handle_critical
        }
        
    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        component: str = "system",
        details: Dict = None
    ):
        try:
            # Create alert
            alert = Alert(
                level=level,
                message=message,
                timestamp=time.time(),
                component=component,
                details=details or {}
            )
            
            # Store alert
            self._store_alert(alert)
            
            # Handle alert based on level
            await self.alert_handlers[level](alert)
            
        except Exception as e:
            logging.error(f"Error sending alert: {str(e)}")
            
    def _store_alert(self, alert: Alert):
        self.alert_history.append(alert)
        
        # Maintain history size limit
        while len(self.alert_history) > self.MAX_HISTORY_SIZE:
            self.alert_history.pop(0)
            
    async def _handle_info(self, alert: Alert):
        # Log informational alerts
        logging.info(
            f"[{alert.component}] {alert.message}"
        )
        
    async def _handle_warning(self, alert: Alert):
        # Log warning alerts
        logging.warning(
            f"[{alert.component}] {alert.message}\nDetails: {json.dumps(alert.details)}"
        )
        
        # Could send notifications here
        
    async def _handle_critical(self, alert: Alert):
        # Log critical alerts
        logging.critical(
            f"[{alert.component}] {alert.message}\nDetails: {json.dumps(alert.details)}"
        )
        
        # Could trigger immediate actions here
        # Could send emergency notifications
        
    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        component: Optional[str] = None,
        time_range: Optional[float] = None
    ) -> List[Alert]:
        current_time = time.time()
        
        filtered_alerts = self.alert_history
        
        if level:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.level == level
            ]
            
        if component:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.component == component
            ]
            
        if time_range:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if current_time - alert.timestamp <= time_range
            ]
            
        return filtered_alerts

class SecurityMonitor:
    def __init__(self):
        self.alerts = AlertSystem()
        self.metrics = MetricsCollector()
        self.running = False
        self.check_interval = 60  # seconds
        
    async def start(self):
        self.running = True
        await self.monitor()
        
    async def stop(self):
        self.running = False
        
    async def monitor(self):
        while self.running:
            try:
                # 1. Collect metrics
                metrics = await self.metrics.collect()
                
                # 2. Check system health
                health = await self._check_system_health(metrics)
                
                # 3. Analyze metrics for anomalies
                await self._analyze_metrics(metrics)
                
                # 4. Update security dashboard
                await self._update_security_dashboard(metrics, health)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"Error in security monitor: {str(e)}")
                await asyncio.sleep(5)  # Short delay before retry
                
    async def _check_system_health(self, metrics: Dict) -> HealthStatus:
        try:
            issues = []
            
            # Check system metrics
            system = metrics.get("system", {})
            if system.get("cpu_usage", 0) > self.metrics.metrics_thresholds["cpu_usage"]:
                issues.append("High CPU usage")
            if system.get("memory_usage", 0) > self.metrics.metrics_thresholds["memory_usage"]:
                issues.append("High memory usage")
            if system.get("disk_usage", 0) > self.metrics.metrics_thresholds["disk_usage"]:
                issues.append("High disk usage")
                
            # Check network metrics
            network = metrics.get("network", {})
            if network.get("network_latency", 0) > self.metrics.metrics_thresholds["network_latency"]:
                issues.append("High network latency")
                
            # Check blockchain metrics
            blockchain = metrics.get("blockchain", {})
            if blockchain.get("pending_transactions", 0) > 1000:
                issues.append("High pending transaction count")
                
            is_healthy = len(issues) == 0
            reason = ", ".join(issues) if issues else "System healthy"
            
            return HealthStatus(
                is_healthy=is_healthy,
                reason=reason,
                metrics=metrics
            )
            
        except Exception as e:
            return HealthStatus(
                is_healthy=False,
                reason=f"Health check error: {str(e)}"
            )
            
    async def _analyze_metrics(self, metrics: Dict):
        try:
            # Analyze system metrics
            system = metrics.get("system", {})
            if system.get("cpu_usage", 0) > 90:
                await self.alerts.send_alert(
                    "Critical CPU usage detected",
                    level=AlertLevel.CRITICAL,
                    component="system",
                    details={"cpu_usage": system["cpu_usage"]}
                )
                
            # Analyze network metrics
            network = metrics.get("network", {})
            if network.get("connected_peers", 0) < 5:
                await self.alerts.send_alert(
                    "Low peer count detected",
                    level=AlertLevel.WARNING,
                    component="network",
                    details={"peer_count": network["connected_peers"]}
                )
                
            # Analyze blockchain metrics
            blockchain = metrics.get("blockchain", {})
            if blockchain.get("pending_transactions", 0) > 2000:
                await self.alerts.send_alert(
                    "High transaction backlog",
                    level=AlertLevel.WARNING,
                    component="blockchain",
                    details={"pending_tx": blockchain["pending_transactions"]}
                )
                
        except Exception as e:
            logging.error(f"Error analyzing metrics: {str(e)}")
            
    async def _update_security_dashboard(
        self,
        metrics: Dict,
        health: HealthStatus
    ):
        # This would update a real-time dashboard
        # Simplified version logs to console
        logging.info("Security Dashboard Update:")
        logging.info(f"System Health: {'Healthy' if health.is_healthy else 'Unhealthy'}")
        logging.info(f"Reason: {health.reason}")
        logging.info("Recent Alerts:")
        
        recent_alerts = self.alerts.get_alerts(time_range=300)  # Last 5 minutes
        for alert in recent_alerts:
            logging.info(
                f"[{alert.level.value}] {alert.timestamp}: {alert.message}"
            )

class SnapshotManager:
    """Manages blockchain state snapshots"""
    
    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        
    def create_snapshot(self, state: Dict[str, Any], block_height: int) -> str:
        """Create a new snapshot of blockchain state"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{block_height}_{timestamp}.json"
        filepath = self.snapshot_dir / filename
        
        snapshot_data = {
            "block_height": block_height,
            "timestamp": timestamp,
            "state": state
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(snapshot_data, f, indent=2)
            logging.info(f"Created snapshot: {filename}")
            return str(filepath)
        except Exception as e:
            logging.error(f"Failed to create snapshot: {e}")
            raise
            
    def load_snapshot(self, snapshot_path: str) -> Dict[str, Any]:
        """Load blockchain state from snapshot"""
        try:
            with open(snapshot_path, 'r') as f:
                snapshot_data = json.load(f)
            logging.info(f"Loaded snapshot: {snapshot_path}")
            return snapshot_data
        except Exception as e:
            logging.error(f"Failed to load snapshot: {e}")
            raise
            
    def list_snapshots(self) -> list:
        """List available snapshots"""
        snapshots = []
        for file in self.snapshot_dir.glob("snapshot_*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                snapshots.append({
                    "path": str(file),
                    "block_height": data["block_height"],
                    "timestamp": data["timestamp"]
                })
            except Exception as e:
                logging.warning(f"Failed to read snapshot {file}: {e}")
                
        return sorted(snapshots, key=lambda x: x["block_height"])
        
    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get the most recent snapshot"""
        snapshots = self.list_snapshots()
        if not snapshots:
            return None
            
        latest = snapshots[-1]
        return self.load_snapshot(latest["path"])
        
    def cleanup_old_snapshots(self, keep_last: int = 10) -> None:
        """Remove old snapshots, keeping only the specified number"""
        snapshots = self.list_snapshots()
        if len(snapshots) <= keep_last:
            return
            
        for snapshot in snapshots[:-keep_last]:
            try:
                os.remove(snapshot["path"])
                logging.info(f"Removed old snapshot: {snapshot['path']}")
            except Exception as e:
                logging.warning(f"Failed to remove snapshot {snapshot['path']}: {e}")
                
    def verify_snapshot_integrity(self, snapshot_path: str) -> bool:
        """Verify snapshot data integrity"""
        try:
            data = self.load_snapshot(snapshot_path)
            required_fields = ["block_height", "timestamp", "state"]
            
            # Check required fields
            if not all(field in data for field in required_fields):
                return False
                
            # Validate data types
            if not isinstance(data["block_height"], int):
                return False
            if not isinstance(data["timestamp"], str):
                return False
            if not isinstance(data["state"], dict):
                return False
                
            return True
        except Exception:
            return False 