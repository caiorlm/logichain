import asyncio
import json
import logging
import time
from typing import Dict, List
import pytest
from datetime import datetime

from blockchain.network.nat_traversal import NATTraversal
from blockchain.network.gossip_protocol import GossipProtocol
from blockchain.network.sync_manager import SyncManager
from blockchain.dag.dag_manager import DAGManager
from blockchain.security.rate_limiter import RateLimiter, RateLimitStrategy, RateLimitConfig
from blockchain.testing.attacks.replay_attack import ReplayAttackSimulator
from blockchain.monitoring.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityStressTest:
    def __init__(self, num_nodes: int = 10):
        self.num_nodes = num_nodes
        self.nodes = []
        self.metrics_collectors = []
        self.rate_limiters = []
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "num_nodes": num_nodes,
            "circuit_breaker": {},
            "rate_limiting": {},
            "replay_protection": {},
            "snapshots": {}
        }

    async def setup(self):
        """Setup test environment"""
        logger.info(f"Setting up {self.num_nodes} nodes")
        
        for i in range(self.num_nodes):
            # Create components
            nat = NATTraversal()
            gossip = GossipProtocol(f"node_{i}")
            dag = DAGManager(f"node_{i}")
            sync = SyncManager(f"node_{i}", dag, gossip)
            metrics = MetricsCollector(f"node_{i}", 8000 + i)
            
            # Create rate limiter
            config = RateLimitConfig(
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                rate=100.0,
                burst=200,
                window_size=60
            )
            rate_limiter = RateLimiter(config)
            
            self.nodes.append((nat, gossip, dag, sync))
            self.metrics_collectors.append(metrics)
            self.rate_limiters.append(rate_limiter)
            
        # Start nodes
        for nat, gossip, _, sync in self.nodes:
            await nat.start()
            await gossip.start()
            await sync.start()
            
        await self._connect_nodes()

    async def _connect_nodes(self):
        """Connect nodes in mesh topology"""
        for i, (nat1, _, _, _) in enumerate(self.nodes):
            for j, (nat2, _, _, _) in enumerate(self.nodes):
                if i != j:
                    await nat1.register_peer(f"node_{j}", nat2.nat_info)

    async def test_circuit_breaker(self):
        """Test circuit breaker with forced failures"""
        logger.info("Testing circuit breaker...")
        results = {"failures": 0, "breaks": 0, "recovery": 0}
        
        # Force failures to trigger circuit breaker
        for i in range(5):
            try:
                # Simulate network partition
                half = self.num_nodes // 2
                for j in range(half):
                    _, _, _, sync = self.nodes[j]
                    await sync.force_sync_failure()
                results["failures"] += 1
                
                # Check if circuit breaker triggered
                breaker_status = await sync.get_circuit_breaker_status()
                if breaker_status["is_open"]:
                    results["breaks"] += 1
                    
                # Wait for recovery
                await asyncio.sleep(5)
                breaker_status = await sync.get_circuit_breaker_status()
                if not breaker_status["is_open"]:
                    results["recovery"] += 1
                    
            except Exception as e:
                logger.error(f"Circuit breaker test error: {e}")
                
        self.report_data["circuit_breaker"] = results
        return results

    async def test_rate_limiting(self):
        """Test rate limiting under load"""
        logger.info("Testing rate limiting...")
        results = {"requests": 0, "limited": 0, "passed": 0}
        
        # Generate high rate of requests
        for i in range(1000):
            for limiter in self.rate_limiters:
                results["requests"] += 1
                allowed = limiter.check_rate_limit()
                if allowed:
                    results["passed"] += 1
                else:
                    results["limited"] += 1
                    
        self.report_data["rate_limiting"] = results
        return results

    async def test_replay_attack(self):
        """Test replay attack protection"""
        logger.info("Testing replay attack protection...")
        simulator = ReplayAttackSimulator()
        results = await simulator.run_attack_sequence()
        self.report_data["replay_protection"] = results
        return results

    async def generate_snapshots(self):
        """Generate and verify snapshots"""
        logger.info("Testing snapshot generation and verification...")
        results = {"generated": 0, "verified": 0, "failed": 0}
        
        for _, _, dag, sync in self.nodes:
            try:
                # Generate snapshot
                snapshot = await sync.create_snapshot()
                results["generated"] += 1
                
                # Verify snapshot
                if await sync.verify_snapshot(snapshot):
                    results["verified"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.error(f"Snapshot test error: {e}")
                results["failed"] += 1
                
        self.report_data["snapshots"] = results
        return results

    def save_report(self, filename: str = "security_stress_report.json"):
        """Save test results to JSON file"""
        self.report_data["timestamp_end"] = datetime.now().isoformat()
        
        with open(filename, "w") as f:
            json.dump(self.report_data, f, indent=2)
            
        logger.info(f"Report saved to {filename}")

    async def teardown(self):
        """Cleanup test environment"""
        for nat, gossip, _, sync in self.nodes:
            await nat.stop()
            await gossip.stop()
            await sync.stop()

@pytest.mark.asyncio
async def test_security_stress():
    """Run full security stress test suite"""
    test = SecurityStressTest(num_nodes=10)
    
    try:
        await test.setup()
        
        # Run tests
        await test.test_circuit_breaker()
        await test.test_rate_limiting()
        await test.test_replay_attack()
        await test.generate_snapshots()
        
        # Save report
        test.save_report()
        
    finally:
        await test.teardown()

if __name__ == "__main__":
    asyncio.run(test_security_stress()) 