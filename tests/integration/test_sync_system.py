import unittest
import asyncio
import logging
from datetime import datetime
from typing import List, Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from blockchain.network.nat_traversal import NATTraversal
from blockchain.network.gossip_protocol import GossipProtocol
from blockchain.network.sync_manager import SyncManager
from blockchain.dag.dag_manager import DAGManager, DAGNode, NodeType

class TestSyncSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configura logging
        logging.basicConfig(level=logging.DEBUG)
        
    def setUp(self):
        # Cria par de chaves para teste
        self.private_key = ec.generate_private_key(ec.SECP256K1())
        
        # Cria nós de teste
        self.nodes = self._create_test_nodes(3)
        
    def _create_test_nodes(self, num_nodes: int) -> List[Tuple[NATTraversal, GossipProtocol, DAGManager, SyncManager]]:
        nodes = []
        for i in range(num_nodes):
            # Cria componentes
            nat = NATTraversal()
            gossip = GossipProtocol(f"node_{i}")
            dag = DAGManager(f"node_{i}", self.private_key)
            sync = SyncManager(f"node_{i}", dag, gossip)
            
            nodes.append((nat, gossip, dag, sync))
            
        return nodes
        
    async def _start_nodes(self):
        """Inicia todos os nós"""
        for nat, gossip, _, sync in self.nodes:
            await nat.start()
            await gossip.start()
            await sync.start()
            
    async def _stop_nodes(self):
        """Para todos os nós"""
        for nat, gossip, _, sync in self.nodes:
            await nat.stop()
            await gossip.stop()
            await sync.stop()
            
    async def _connect_nodes(self):
        """Conecta os nós entre si"""
        for i, (nat1, _, _, _) in enumerate(self.nodes):
            for j, (nat2, _, _, _) in enumerate(self.nodes):
                if i != j:
                    # Registra peers
                    await nat1.register_peer(f"node_{j}", nat2.nat_info)
                    
    async def _create_test_dag(self, dag: DAGManager, num_nodes: int = 5):
        """Cria um DAG de teste"""
        nodes = []
        timestamp = datetime.utcnow().timestamp()
        
        # Cria nó raiz
        root = DAGNode(
            node_id="root",
            node_type=NodeType.BLOCK,
            parents=[],
            timestamp=timestamp,
            data={"index": 0}
        )
        dag.sign_node(root)
        dag.add_node(root)
        nodes.append(root)
        
        # Cria nós filhos
        for i in range(1, num_nodes):
            node = DAGNode(
                node_id=f"node_{i}",
                node_type=NodeType.BLOCK,
                parents=[nodes[-1].node_id],
                timestamp=timestamp + i,
                data={"index": i}
            )
            dag.sign_node(node)
            dag.add_node(node)
            nodes.append(node)
            
        return nodes
        
    async def test_full_sync(self):
        """Testa sincronização completa entre nós"""
        # Inicia nós
        await self._start_nodes()
        await self._connect_nodes()
        
        try:
            # Cria DAG no primeiro nó
            _, _, dag1, _ = self.nodes[0]
            test_nodes = await self._create_test_dag(dag1)
            
            # Inicia sincronização
            for _, _, _, sync in self.nodes[1:]:
                await sync.sync_with_network()
                
            # Aguarda sincronização
            await asyncio.sleep(5)
            
            # Verifica se todos os nós têm os mesmos blocos
            for _, _, dag, _ in self.nodes[1:]:
                for test_node in test_nodes:
                    self.assertIn(test_node.node_id, dag.nodes)
                    
        finally:
            await self._stop_nodes()
            
    async def test_partial_sync(self):
        """Testa sincronização parcial de blocos"""
        await self._start_nodes()
        await self._connect_nodes()
        
        try:
            # Cria DAGs diferentes em dois nós
            _, _, dag1, _ = self.nodes[0]
            _, _, dag2, _ = self.nodes[1]
            
            nodes1 = await self._create_test_dag(dag1, 3)
            nodes2 = await self._create_test_dag(dag2, 3)
            
            # Sincroniza terceiro nó
            _, _, _, sync3 = self.nodes[2]
            await sync3.sync_with_network()
            
            # Aguarda sincronização
            await asyncio.sleep(5)
            
            # Verifica se terceiro nó tem todos os blocos
            _, _, dag3, _ = self.nodes[2]
            for node in nodes1 + nodes2:
                self.assertIn(node.node_id, dag3.nodes)
                
        finally:
            await self._stop_nodes()
            
    async def test_sync_recovery(self):
        """Testa recuperação de sincronização após falha"""
        await self._start_nodes()
        await self._connect_nodes()
        
        try:
            # Cria DAG no primeiro nó
            _, _, dag1, _ = self.nodes[0]
            test_nodes = await self._create_test_dag(dag1)
            
            # Simula falha no segundo nó
            nat2, gossip2, _, sync2 = self.nodes[1]
            await nat2.stop()
            await gossip2.stop()
            await sync2.stop()
            
            # Aguarda um pouco
            await asyncio.sleep(2)
            
            # Reinicia segundo nó
            await nat2.start()
            await gossip2.start()
            await sync2.start()
            
            # Tenta sincronizar
            await sync2.sync_with_network()
            
            # Aguarda sincronização
            await asyncio.sleep(5)
            
            # Verifica se recuperou os blocos
            _, _, dag2, _ = self.nodes[1]
            for test_node in test_nodes:
                self.assertIn(test_node.node_id, dag2.nodes)
                
        finally:
            await self._stop_nodes()
            
    async def test_stress_sync(self):
        """Teste de stress do sistema de sincronização"""
        await self._start_nodes()
        await self._connect_nodes()
        
        try:
            # Cria muitos blocos no primeiro nó
            _, _, dag1, _ = self.nodes[0]
            test_nodes = await self._create_test_dag(dag1, 100)
            
            # Inicia várias sincronizações simultâneas
            tasks = []
            for _, _, _, sync in self.nodes[1:]:
                task = asyncio.create_task(sync.sync_with_network())
                tasks.append(task)
                
            # Aguarda todas as sincronizações
            await asyncio.gather(*tasks)
            
            # Verifica se todos sincronizaram corretamente
            for _, _, dag, _ in self.nodes[1:]:
                for test_node in test_nodes:
                    self.assertIn(test_node.node_id, dag.nodes)
                    
        finally:
            await self._stop_nodes()
            
if __name__ == '__main__':
    unittest.main() 