import pytest
import time
import asyncio
from blockchain.security.monitor import (
    SecurityMonitor,
    AlertLevel,
    Alert,
    HealthStatus,
    MetricsCollector,
    AlertSystem
)

@pytest.fixture
def monitor():
    return SecurityMonitor()

@pytest.fixture
def metrics_collector():
    return MetricsCollector()

@pytest.fixture
def alert_system():
    return AlertSystem()

@pytest.mark.asyncio
async def test_metrics_collection(metrics_collector):
    metrics = await metrics_collector.collect()
    
    # Check system metrics
    assert "system" in metrics
    assert "cpu_usage" in metrics["system"]
    assert "memory_usage" in metrics["system"]
    assert "disk_usage" in metrics["system"]
    
    # Check blockchain metrics
    assert "blockchain" in metrics
    assert "block_height" in metrics["blockchain"]
    assert "transaction_count" in metrics["blockchain"]
    
    # Check network metrics
    assert "network" in metrics
    assert "connected_peers" in metrics["network"]
    assert "network_latency" in metrics["network"]

@pytest.mark.asyncio
async def test_alert_system(alert_system):
    # Test info alert
    await alert_system.send_alert(
        "Test info message",
        level=AlertLevel.INFO,
        component="test",
        details={"test": "info"}
    )
    
    # Test warning alert
    await alert_system.send_alert(
        "Test warning message",
        level=AlertLevel.WARNING,
        component="test",
        details={"test": "warning"}
    )
    
    # Test critical alert
    await alert_system.send_alert(
        "Test critical message",
        level=AlertLevel.CRITICAL,
        component="test",
        details={"test": "critical"}
    )
    
    # Check alert history
    alerts = alert_system.get_alerts()
    assert len(alerts) == 3
    
    # Check alert filtering
    critical_alerts = alert_system.get_alerts(level=AlertLevel.CRITICAL)
    assert len(critical_alerts) == 1
    assert critical_alerts[0].level == AlertLevel.CRITICAL

@pytest.mark.asyncio
async def test_metrics_history(metrics_collector):
    # Collect metrics multiple times
    for _ in range(5):
        await metrics_collector.collect()
        await asyncio.sleep(0.1)
        
    # Check history for a specific metric
    history = metrics_collector.get_metric_history("system.cpu_usage")
    assert len(history) > 0
    
    # Check time range filtering
    recent_history = metrics_collector.get_metric_history(
        "system.cpu_usage",
        time_range=1.0  # Last second
    )
    assert len(recent_history) > 0

@pytest.mark.asyncio
async def test_health_check(monitor):
    # Start monitoring
    monitor_task = asyncio.create_task(monitor.start())
    
    # Wait for first health check
    await asyncio.sleep(0.1)
    
    # Stop monitoring
    await monitor.stop()
    await monitor_task
    
    # Health check should have run
    assert isinstance(monitor.metrics, MetricsCollector)
    assert isinstance(monitor.alerts, AlertSystem)

@pytest.mark.asyncio
async def test_alert_thresholds(monitor):
    # Start monitoring
    monitor_task = asyncio.create_task(monitor.start())
    
    # Wait for metrics collection
    await asyncio.sleep(0.1)
    
    # Simulate high CPU usage
    original_collect = monitor.metrics._collect_system_metrics
    
    async def mock_collect_system_metrics():
        metrics = await original_collect()
        metrics["cpu_usage"] = 95.0  # Should trigger alert
        return metrics
        
    monitor.metrics._collect_system_metrics = mock_collect_system_metrics
    
    # Wait for alert generation
    await asyncio.sleep(0.1)
    
    # Check for CPU alert
    alerts = monitor.alerts.get_alerts(
        level=AlertLevel.CRITICAL,
        component="system"
    )
    assert len(alerts) > 0
    assert "CPU" in alerts[0].message
    
    # Stop monitoring
    await monitor.stop()
    await monitor_task

@pytest.mark.asyncio
async def test_metrics_thresholds(metrics_collector):
    # Check threshold values
    assert metrics_collector.metrics_thresholds["cpu_usage"] == 80.0
    assert metrics_collector.metrics_thresholds["memory_usage"] == 85.0
    assert metrics_collector.metrics_thresholds["disk_usage"] == 90.0

@pytest.mark.asyncio
async def test_alert_history_limit(alert_system):
    # Generate many alerts
    for i in range(alert_system.MAX_HISTORY_SIZE + 10):
        await alert_system.send_alert(
            f"Test message {i}",
            level=AlertLevel.INFO
        )
        
    # Check history size limit
    alerts = alert_system.get_alerts()
    assert len(alerts) <= alert_system.MAX_HISTORY_SIZE

@pytest.mark.asyncio
async def test_metrics_history_limit(metrics_collector):
    # Generate many metrics
    for _ in range(metrics_collector.MAX_HISTORY_SIZE + 10):
        await metrics_collector.collect()
        await asyncio.sleep(0.1)
        
    # Check history size limit
    history = metrics_collector.get_metric_history("system.cpu_usage")
    assert len(history) <= metrics_collector.MAX_HISTORY_SIZE

@pytest.mark.asyncio
async def test_alert_component_filtering(alert_system):
    # Generate alerts for different components
    components = ["system", "network", "blockchain"]
    for component in components:
        await alert_system.send_alert(
            f"Test {component} message",
            component=component
        )
        
    # Check component filtering
    for component in components:
        alerts = alert_system.get_alerts(component=component)
        assert len(alerts) == 1
        assert alerts[0].component == component

@pytest.mark.asyncio
async def test_security_dashboard(monitor):
    # Start monitoring
    monitor_task = asyncio.create_task(monitor.start())
    
    # Generate some alerts
    await monitor.alerts.send_alert(
        "Test alert 1",
        level=AlertLevel.WARNING
    )
    await monitor.alerts.send_alert(
        "Test alert 2",
        level=AlertLevel.CRITICAL
    )
    
    # Wait for dashboard update
    await asyncio.sleep(0.1)
    
    # Stop monitoring
    await monitor.stop()
    await monitor_task
    
    # Check recent alerts
    recent_alerts = monitor.alerts.get_alerts(time_range=300)
    assert len(recent_alerts) >= 2 