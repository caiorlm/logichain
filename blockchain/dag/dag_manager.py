import asyncio
import hashlib
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)

class NodeType(Enum):
    BLOCK = "block"
    CHECKPOINT = "checkpoint"
    MERGE = "merge"

@dataclass
class DAGNode:
    node_id: str
    node_type: NodeType
    parents: List[str]
    timestamp: float
    data: dict
    signature: Optional[str] = None
    height: int = 0
    weight: float = 1.0
    
class DAGManager:
    def __init__(self, node_id: str, private_key: ec.EllipticCurvePrivateKey):
        self.node_id = node_id
        self.private_key = private_key
        self.public_key = private_key.public_key()
        
        # Estrutura do DAG
        self.nodes: Dict[str, DAGNode] = {}
        self.tips: Set[str] = set()  # Nós sem filhos
        self.roots: Set[str] = set()  # Nós sem pais
        
        # Cache de validação
        self.validated_paths: Dict[str, Set[str]] = {}
        self.invalid_nodes: Set[str] = set()
        
        # Controle de fork
        self.fork_points: Dict[str, List[str]] = {}
        self.suspicious_nodes: Dict[str, int] = {}
        
    def add_node(self, node: DAGNode, validate: bool = True) -> bool:
        """Adiciona um novo nó ao DAG"""
        # Valida o nó
        if validate and not self._validate_node(node):
            logger.warning(f"Node validation failed: {node.node_id}")
            return False
            
        # Verifica ancestralidade
        if not self._verify_ancestry(node):
            logger.warning(f"Invalid ancestry: {node.node_id}")
            return False
            
        # Verifica assinatura
        if not self._verify_signature(node):
            logger.warning(f"Invalid signature: {node.node_id}")
            return False
            
        # Adiciona o nó
        self.nodes[node.node_id] = node
        
        # Atualiza tips
        self.tips.add(node.node_id)
        for parent in node.parents:
            self.tips.discard(parent)
            
        # Atualiza roots
        if not node.parents:
            self.roots.add(node.node_id)
            
        # Detecta e registra pontos de fork
        self._detect_forks(node)
        
        # Atualiza altura e peso
        self._update_metrics(node)
        
        return True
        
    def _validate_node(self, node: DAGNode) -> bool:
        """Valida um nó antes de adicionar ao DAG"""
        # Verifica se já existe
        if node.node_id in self.nodes:
            return False
            
        # Verifica timestamp
        now = datetime.utcnow().timestamp()
        if abs(now - node.timestamp) > 300:  # 5 minutos de tolerância
            return False
            
        # Verifica parents
        for parent in node.parents:
            if parent not in self.nodes:
                return False
                
        # Verifica ciclos
        if self._would_create_cycle(node):
            return False
            
        return True
        
    def _verify_ancestry(self, node: DAGNode) -> bool:
        """Verifica a ancestralidade do nó"""
        # Verifica se todos os parents existem
        for parent in node.parents:
            if parent not in self.nodes:
                return False
                
        # Verifica consistência temporal
        for parent in node.parents:
            parent_node = self.nodes[parent]
            if parent_node.timestamp >= node.timestamp:
                return False
                
        # Verifica path de validação
        valid_path = set()
        for parent in node.parents:
            if parent in self.validated_paths:
                valid_path.update(self.validated_paths[parent])
        valid_path.update(node.parents)
        self.validated_paths[node.node_id] = valid_path
        
        return True
        
    def _verify_signature(self, node: DAGNode) -> bool:
        """Verifica a assinatura do nó"""
        if not node.signature:
            return False
            
        try:
            # Recria os dados assinados
            data = self._get_signing_data(node)
            
            # Verifica a assinatura
            self.public_key.verify(
                bytes.fromhex(node.signature),
                data.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return True
            
        except (InvalidSignature, ValueError):
            return False
            
    def _get_signing_data(self, node: DAGNode) -> str:
        """Gera os dados para assinatura"""
        data = {
            "node_id": node.node_id,
            "type": node.node_type.value,
            "parents": sorted(node.parents),
            "timestamp": node.timestamp,
            "data": node.data
        }
        return json.dumps(data, sort_keys=True)
        
    def _would_create_cycle(self, node: DAGNode) -> bool:
        """Verifica se adicionar o nó criaria um ciclo"""
        visited = set()
        
        def dfs(current: str) -> bool:
            if current in visited:
                return True
            if current not in self.nodes:
                return False
                
            visited.add(current)
            current_node = self.nodes[current]
            
            for parent in current_node.parents:
                if dfs(parent):
                    return True
                    
            visited.remove(current)
            return False
            
        # Simula o nó no grafo
        self.nodes[node.node_id] = node
        has_cycle = dfs(node.node_id)
        del self.nodes[node.node_id]
        
        return has_cycle
        
    def _detect_forks(self, node: DAGNode):
        """Detecta e registra pontos de fork"""
        # Verifica se há múltiplos filhos para os parents
        for parent in node.parents:
            children = self._get_children(parent)
            if len(children) > 1:
                if parent not in self.fork_points:
                    self.fork_points[parent] = []
                self.fork_points[parent].append(node.node_id)
                
                # Registra nó suspeito se criar muitos forks
                if len(self.fork_points[parent]) > 3:
                    self.suspicious_nodes[node.node_id] = \
                        self.suspicious_nodes.get(node.node_id, 0) + 1
                    
    def _get_children(self, node_id: str) -> List[str]:
        """Retorna os filhos de um nó"""
        return [
            n.node_id for n in self.nodes.values()
            if node_id in n.parents
        ]
        
    def _update_metrics(self, node: DAGNode):
        """Atualiza altura e peso do nó"""
        # Calcula altura
        max_parent_height = 0
        total_parent_weight = 0
        
        for parent in node.parents:
            parent_node = self.nodes[parent]
            max_parent_height = max(max_parent_height, parent_node.height)
            total_parent_weight += parent_node.weight
            
        node.height = max_parent_height + 1
        
        # Calcula peso
        node.weight = 1.0
        if node.parents:
            node.weight += total_parent_weight / len(node.parents)
            
    def get_tips(self) -> List[DAGNode]:
        """Retorna os nós tips atuais"""
        return [self.nodes[tip] for tip in self.tips]
        
    def get_path_to_root(self, node_id: str) -> List[str]:
        """Retorna o caminho até a root"""
        if node_id not in self.nodes:
            return []
            
        path = []
        current = node_id
        
        while current not in self.roots:
            path.append(current)
            current_node = self.nodes[current]
            if not current_node.parents:
                break
            current = current_node.parents[0]  # Pega primeiro parent
            
        path.append(current)
        return path
        
    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """Verifica se um nó é ancestral de outro"""
        if descendant not in self.nodes:
            return False
            
        visited = set()
        
        def dfs(current: str) -> bool:
            if current == ancestor:
                return True
            if current in visited or current not in self.nodes:
                return False
                
            visited.add(current)
            current_node = self.nodes[current]
            
            for parent in current_node.parents:
                if dfs(parent):
                    return True
                    
            return False
            
        return dfs(descendant)
        
    def get_common_ancestor(self, node1: str, node2: str) -> Optional[str]:
        """Encontra o ancestral comum mais recente"""
        if node1 not in self.nodes or node2 not in self.nodes:
            return None
            
        ancestors1 = set()
        current = node1
        
        while current not in self.roots:
            ancestors1.add(current)
            current_node = self.nodes[current]
            if not current_node.parents:
                break
            current = current_node.parents[0]
            
        current = node2
        while current not in self.roots:
            if current in ancestors1:
                return current
            current_node = self.nodes[current]
            if not current_node.parents:
                break
            current = current_node.parents[0]
            
        return None
        
    def prune_old_nodes(self, max_age: float = 3600):
        """Remove nós antigos do DAG"""
        now = datetime.utcnow().timestamp()
        to_remove = []
        
        for node_id, node in self.nodes.items():
            if now - node.timestamp > max_age:
                to_remove.append(node_id)
                
        for node_id in to_remove:
            self._remove_node(node_id)
            
    def _remove_node(self, node_id: str):
        """Remove um nó do DAG"""
        if node_id not in self.nodes:
            return
            
        node = self.nodes[node_id]
        
        # Remove das estruturas
        del self.nodes[node_id]
        self.tips.discard(node_id)
        self.roots.discard(node_id)
        self.validated_paths.pop(node_id, None)
        
        # Atualiza fork points
        for fork_list in self.fork_points.values():
            if node_id in fork_list:
                fork_list.remove(node_id)
                
        # Remove fork points vazios
        self.fork_points = {k: v for k, v in self.fork_points.items() if v}
        
        # Remove das suspeitas
        self.suspicious_nodes.pop(node_id, None)
        
    def get_suspicious_nodes(self) -> Dict[str, int]:
        """Retorna nós com comportamento suspeito"""
        return {k: v for k, v in self.suspicious_nodes.items() if v > 3}
        
    def sign_node(self, node: DAGNode):
        """Assina um nó com a chave privada"""
        data = self._get_signing_data(node)
        signature = self.private_key.sign(
            data.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        node.signature = signature.hex() 