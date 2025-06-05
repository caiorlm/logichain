"""
Metrics Collector for LogiChain
"""

from typing import Dict, Any
import time

class MetricsCollector:
    """
    Collects and manages metrics for the blockchain system
    """
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.start_time = time.time()

    def record_metric(self, name: str, value: Any) -> None:
        """
        Record a metric value
        """
        self.metrics[name] = value

    def get_metric(self, name: str) -> Any:
        """
        Get a metric value
        """
        return self.metrics.get(name)

    def get_uptime(self) -> float:
        """
        Get system uptime in seconds
        """
        return time.time() - self.start_time

    def clear_metrics(self) -> None:
        """
        Clear all metrics
        """
        self.metrics.clear() 