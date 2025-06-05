import asyncio
import logging
import random
import time
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor
import pytest

from blockchain.network.nat_traversal import NATTraversal
from blockchain.network.gossip_protocol import GossipProtocol
from blockchain.network.sync_manager import SyncManager
from blockchain.dag.dag_manager import DAGManager, DAGNode, NodeType
from blockchain.monitoring.metrics_collector import MetricsCollector

from cryptography.hazmat.primitives.asymmetric import ec

logger = logging.getLogger(__name__)

class NetworkStressTest:
    def __init__(self, num_nodes: int = 10):
        self.num_nodes = num_nodes
        self.nodes: List[Tuple] = []
        self.metrics_collectors: List[MetricsCollector] = []
        self.executor = ThreadPoolExecutor(max_workers=num_nodes)
        
    async def setup(self):
        """Configura ambiente de teste"""
        logger.info(f"Setting up {self.num_nodes} nodes")
        
        # Cria nós
        for i in range(self.num_nodes):
            # Cria chaves
            private_key = ec.generate_private_key(ec.SECP256K1())
            
            # Cria componentes
            nat = NATTraversal()
            gossip = GossipProtocol(f"node_{i}")
            dag = DAGManager(f"node_{i}", private_key)
            sync = SyncManager(f"node_{i}", dag, gossip)
            metrics = MetricsCollector(f"node_{i}", 8000 + i)
            
            self.nodes.append((nat, gossip, dag, sync))
            self.metrics_collectors.append(metrics)
            
        # Inicia nós
        for nat, gossip, _, sync in self.nodes:
            await nat.start()
            await gossip.start()
            await sync.start()
            
        # Conecta nós
        await self._connect_nodes()
        
    async def _connect_nodes(self):
        """Conecta os nós em uma topologia mesh"""
        for i, (nat1, _, _, _) in enumerate(self.nodes):
            for j, (nat2, _, _, _) in enumerate(self.nodes):
                if i != j:
                    await nat1.register_peer(f"node_{j}", nat2.nat_info)
                    
    async def teardown(self):
        """Limpa ambiente de teste"""
        for nat, gossip, _, sync in self.nodes:
            await nat.stop()
            await gossip.stop()
            await sync.stop()
            
        self.executor.shutdown()
        
    async def test_message_flood(self, num_messages: int = 1000):
        """Teste de flood de mensagens"""
        logger.info(f"Starting message flood test with {num_messages} messages")
        
        start_time = time.time()
        tasks = []
        
        # Cada nó envia mensagens para todos os outros
        for i, (_, gossip, _, _) in enumerate(self.nodes):
            for _ in range(num_messages // self.num_nodes):
                message = gossip.create_message(
                    "BLOCK",
                    {"data": f"test_message_{random.randint(0, 1000000)}"}
                )
                task = asyncio.create_task(gossip.broadcast(message))
                tasks.append(task)
                
        # Aguarda todas as mensagens
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        logger.info(f"Message flood test completed in {duration:.2f} seconds")
        
        # Coleta métricas
        for metrics in self.metrics_collectors:
            summary = metrics.get_metrics_summary()
            logger.info(f"Node {metrics.node_id} metrics: {summary}")
            
    async def test_sync_stress(self, num_blocks: int = 100):
        """Teste de stress de sincronização"""
        logger.info(f"Starting sync stress test with {num_blocks} blocks")
        
        # Cria blocos no primeiro nó
        _, _, dag1, _ = self.nodes[0]
        
        start_time = time.time()
        timestamp = start_time
        
        # Cria blocos
        for i in range(num_blocks):
            node = DAGNode(
                node_id=f"block_{i}",
                node_type=NodeType.BLOCK,
                parents=[f"block_{i-1}"] if i > 0 else [],
                timestamp=timestamp + i,
                data={"index": i}
            )
            dag1.sign_node(node)
            dag1.add_node(node)
            
        # Sincroniza outros nós
        tasks = []
        for _, _, _, sync in self.nodes[1:]:
            task = asyncio.create_task(sync.sync_with_network())
            tasks.append(task)
            
        # Aguarda sincronização
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        logger.info(f"Sync stress test completed in {duration:.2f} seconds")
        
        # Verifica sincronização
        for _, _, dag, _ in self.nodes[1:]:
            assert len(dag.nodes) == num_blocks
            
    async def test_network_partition(self):
        """Teste de partição de rede"""
        logger.info("Starting network partition test")
        
        # Divide nós em dois grupos
        group1 = self.nodes[:self.num_nodes//2]
        group2 = self.nodes[self.num_nodes//2:]
        
        # Desconecta grupos
        for nat1, _, _, _ in group1:
            for j in range(self.num_nodes//2, self.num_nodes):
                nat1.peers.pop(f"node_{j}", None)
                
        # Cria blocos em ambos os grupos
        _, _, dag1, _ = group1[0]
        _, _, dag2, _ = group2[0]
        
        timestamp = time.time()
        
        # Grupo 1
        for i in range(10):
            node = DAGNode(
                node_id=f"group1_block_{i}",
                node_type=NodeType.BLOCK,
                parents=[f"group1_block_{i-1}"] if i > 0 else [],
                timestamp=timestamp + i,
                data={"group": 1, "index": i}
            )
            dag1.sign_node(node)
            dag1.add_node(node)
            
        # Grupo 2
        for i in range(10):
            node = DAGNode(
                node_id=f"group2_block_{i}",
                node_type=NodeType.BLOCK,
                parents=[f"group2_block_{i-1}"] if i > 0 else [],
                timestamp=timestamp + i,
                data={"group": 2, "index": i}
            )
            dag2.sign_node(node)
            dag2.add_node(node)
            
        # Reconecta grupos
        await self._connect_nodes()
        
        # Sincroniza
        tasks = []
        for _, _, _, sync in self.nodes:
            task = asyncio.create_task(sync.sync_with_network())
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        
        # Verifica resolução de fork
        for _, _, dag, _ in self.nodes:
            assert len(dag.nodes) == 20
            assert len(dag.fork_points) > 0
            
    async def test_malicious_messages(self):
        """Teste de mensagens maliciosas"""
        logger.info("Starting malicious message test")
        
        # Cria mensagens maliciosas
        _, gossip, _, _ = self.nodes[0]
        
        # Mensagem com timestamp futuro
        future_msg = gossip.create_message(
            "BLOCK",
            {"data": "future"}
        )
        future_msg.timestamp = time.time() + 3600
        
        # Mensagem com assinatura inválida
        invalid_sig_msg = gossip.create_message(
            "BLOCK",
            {"data": "invalid_sig"}
        )
        invalid_sig_msg.signature = "invalid"
        
        # Mensagem com ciclo no DAG
        cycle_msg = gossip.create_message(
            "BLOCK",
            {"data": "cycle"}
        )
        cycle_msg.payload["parents"] = [cycle_msg.message_id]
        
        # Tenta broadcast
        for msg in [future_msg, invalid_sig_msg, cycle_msg]:
            try:
                await gossip.broadcast(msg)
            except Exception as e:
                logger.info(f"Expected error: {e}")
                
        # Verifica se mensagens foram rejeitadas
        for _, _, dag, _ in self.nodes[1:]:
            assert len(dag.nodes) == 0
            assert len(dag.invalid_nodes) > 0
            
@pytest.mark.asyncio
async def test_network_stress():
    """Executa suite de testes de stress"""
    test = NetworkStressTest(num_nodes=10)
    
    try:
        await test.setup()
        
        # Executa testes
        await test.test_message_flood(num_messages=1000)
        await test.test_sync_stress(num_blocks=100)
        await test.test_network_partition()
        await test.test_malicious_messages()
        
    finally:
        await test.teardown()
        
if __name__ == "__main__":
    asyncio.run(test_network_stress()) 