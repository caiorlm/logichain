"""
Blockchain monitoring system with comprehensive metrics and alerts.
Integrates with POD and privacy features.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import time
import logging
import json
import threading
from collections import deque

@dataclass
class MetricPoint:
    """Single metric measurement point"""
    timestamp: float
    value: float
    labels: Dict[str, str]

class MetricBuffer:
    """Thread-safe circular buffer for metrics"""
    def __init__(self, max_size: int = 1000):
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
    
    def add(self, point: MetricPoint):
        """Add metric point to buffer"""
        with self.lock:
            self.buffer.append(point)
    
    def get_range(self, start_time: float, end_time: float) -> List[MetricPoint]:
        """Get metrics within time range"""
        with self.lock:
            return [
                p for p in self.buffer
                if start_time <= p.timestamp <= end_time
            ]

class Monitor:
    """Main monitoring system"""
    
    def __init__(self):
        self.metrics: Dict[str, MetricBuffer] = {}
        self.alerts: List[Dict] = []
        self.alert_callbacks: List[callable] = []
        self.running = False
        self.monitor_thread = None
        
        # Initialize default metrics
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize default metric buffers"""
        default_metrics = [
            # POD metrics
            'pod.proofs.total',
            'pod.proofs.valid',
            'pod.proofs.invalid',
            'pod.offline_proofs.total',
            'pod.offline_proofs.pending',
            'pod.contracts.active',
            'pod.contracts.completed',
            
            # Privacy metrics
            'privacy.encryption_operations',
            'privacy.decryption_operations',
            'privacy.key_rotations',
            
            # Blockchain metrics
            'blockchain.blocks.total',
            'blockchain.transactions.total',
            'blockchain.transactions.pending',
            'blockchain.mining.hashrate',
            'blockchain.mining.difficulty',
            
            # Network metrics
            'network.peers.total',
            'network.bandwidth.in',
            'network.bandwidth.out',
            'network.latency'
        ]
        
        for metric in default_metrics:
            self.metrics[metric] = MetricBuffer()
    
    def start(self):
        """Start monitoring system"""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logging.info("Monitoring system started")
    
    def stop(self):
        """Stop monitoring system"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logging.info("Monitoring system stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self._check_alerts()
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error in monitor loop: {e}")
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a metric value"""
        if name not in self.metrics:
            self.metrics[name] = MetricBuffer()
            
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        
        self.metrics[name].add(point)
    
    def add_alert_callback(self, callback: callable):
        """Add callback for alert notifications"""
        self.alert_callbacks.append(callback)
    
    def _check_alerts(self):
        """Check for alert conditions"""
        now = time.time()
        
        # Example alert checks
        for name, buffer in self.metrics.items():
            recent = buffer.get_range(now - 300, now)  # Last 5 minutes
            
            if not recent:
                continue
                
            avg = sum(p.value for p in recent) / len(recent)
            
            # Example alert conditions
            if name == 'pod.proofs.invalid' and avg > 0.1:  # >10% invalid proofs
                self._trigger_alert(
                    name=name,
                    level='warning',
                    message=f"High rate of invalid proofs: {avg:.2%}",
                    value=avg
                )
            elif name == 'network.latency' and avg > 1000:  # >1s latency
                self._trigger_alert(
                    name=name,
                    level='error', 
                    message=f"High network latency: {avg:.0f}ms",
                    value=avg
                )
    
    def _trigger_alert(self, name: str, level: str, message: str, value: float):
        """Trigger alert and notify callbacks"""
        alert = {
            'timestamp': time.time(),
            'name': name,
            'level': level,
            'message': message,
            'value': value
        }
        
        self.alerts.append(alert)
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logging.error(f"Error in alert callback: {e}")
    
    def get_metrics(self, names: Optional[List[str]] = None, 
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None) -> Dict[str, List[MetricPoint]]:
        """Get metrics data"""
        if end_time is None:
            end_time = time.time()
        if start_time is None:
            start_time = end_time - 3600  # Last hour
            
        result = {}
        for name, buffer in self.metrics.items():
            if names and name not in names:
                continue
            result[name] = buffer.get_range(start_time, end_time)
            
        return result
    
    def get_alerts(self, start_time: Optional[float] = None,
                  end_time: Optional[float] = None,
                  levels: Optional[List[str]] = None) -> List[Dict]:
        """Get alerts within time range and levels"""
        if end_time is None:
            end_time = time.time()
        if start_time is None:
            start_time = end_time - 3600  # Last hour
            
        alerts = [
            alert for alert in self.alerts
            if start_time <= alert['timestamp'] <= end_time
            and (not levels or alert['level'] in levels)
        ]
        
        return alerts 