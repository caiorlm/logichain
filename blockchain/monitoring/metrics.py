"""
Sistema de métricas e monitoramento
"""

from typing import Dict, List, Optional, Any
import time
import threading
import logging
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

@dataclass
class MetricConfig:
    """Configuração de métrica"""
    name: str
    type: str  # counter, gauge, histogram
    description: str
    labels: List[str]
    buckets: Optional[List[float]] = None  # Para histograms

class MetricsManager:
    """
    Gerenciador de métricas
    
    Features:
    - Múltiplos tipos de métricas
    - Labels dinâmicos
    - Agregação automática
    - Persistência
    - Exportação para Prometheus
    """
    
    def __init__(self):
        # Estado
        self.metrics: Dict[str, Dict] = defaultdict(dict)
        self.configs: Dict[str, MetricConfig] = {}
        
        # Cache
        self.aggregations: Dict[str, Dict] = {}
        self.last_update = time.time()
        
        # Threading
        self.lock = threading.RLock()
        
        # Inicializa métricas default
        self._initialize_metrics()
        
    def _initialize_metrics(self):
        """Inicializa métricas padrão"""
        # Transações
        self.register_metric(
            MetricConfig(
                name="transactions_total",
                type="counter",
                description="Total de transações processadas",
                labels=["status", "type"]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="transaction_size_bytes",
                type="histogram",
                description="Tamanho das transações em bytes",
                labels=["type"],
                buckets=[64, 128, 256, 512, 1024, 2048, 4096]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="transaction_processing_time",
                type="histogram",
                description="Tempo de processamento de transações",
                labels=["type"],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
            )
        )
        
        # Blocos
        self.register_metric(
            MetricConfig(
                name="blocks_total",
                type="counter",
                description="Total de blocos processados",
                labels=["status"]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="block_size_bytes",
                type="histogram",
                description="Tamanho dos blocos em bytes",
                labels=[],
                buckets=[1024, 2048, 4096, 8192, 16384]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="block_time_seconds",
                type="gauge",
                description="Tempo entre blocos em segundos",
                labels=[]
            )
        )
        
        # Mempool
        self.register_metric(
            MetricConfig(
                name="mempool_size",
                type="gauge",
                description="Número de transações no mempool",
                labels=[]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="mempool_bytes",
                type="gauge",
                description="Tamanho do mempool em bytes",
                labels=[]
            )
        )
        
        # Rede
        self.register_metric(
            MetricConfig(
                name="peer_count",
                type="gauge",
                description="Número de peers conectados",
                labels=["status"]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="bandwidth_bytes",
                type="counter",
                description="Bandwidth utilizada",
                labels=["direction"]
            )
        )
        
        # Recursos
        self.register_metric(
            MetricConfig(
                name="cpu_usage_percent",
                type="gauge",
                description="Uso de CPU em porcentagem",
                labels=["type"]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="memory_usage_bytes",
                type="gauge",
                description="Uso de memória em bytes",
                labels=["type"]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="disk_usage_bytes",
                type="gauge",
                description="Uso de disco em bytes",
                labels=["type"]
            )
        )
        
        # Segurança
        self.register_metric(
            MetricConfig(
                name="security_events_total",
                type="counter",
                description="Total de eventos de segurança",
                labels=["type", "severity"]
            )
        )
        
        self.register_metric(
            MetricConfig(
                name="banned_addresses_total",
                type="gauge",
                description="Número de endereços banidos",
                labels=[]
            )
        )
        
    def register_metric(self, config: MetricConfig):
        """Registra nova métrica"""
        with self.lock:
            self.configs[config.name] = config
            
            # Inicializa estado
            if config.type == "counter":
                self.metrics[config.name] = defaultdict(int)
            elif config.type == "gauge":
                self.metrics[config.name] = defaultdict(float)
            elif config.type == "histogram":
                self.metrics[config.name] = {
                    "sum": defaultdict(float),
                    "count": defaultdict(int),
                    "buckets": defaultdict(lambda: defaultdict(int))
                }
                
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ):
        """Incrementa contador"""
        with self.lock:
            if name not in self.configs:
                raise ValueError(f"Unknown metric: {name}")
                
            config = self.configs[name]
            if config.type != "counter":
                raise ValueError(f"Metric {name} is not a counter")
                
            # Gera label key
            label_key = self._label_key(name, labels)
            
            # Incrementa
            self.metrics[name][label_key] += value
            
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Define valor do gauge"""
        with self.lock:
            if name not in self.configs:
                raise ValueError(f"Unknown metric: {name}")
                
            config = self.configs[name]
            if config.type != "gauge":
                raise ValueError(f"Metric {name} is not a gauge")
                
            # Gera label key
            label_key = self._label_key(name, labels)
            
            # Define valor
            self.metrics[name][label_key] = value
            
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Adiciona observação ao histogram"""
        with self.lock:
            if name not in self.configs:
                raise ValueError(f"Unknown metric: {name}")
                
            config = self.configs[name]
            if config.type != "histogram":
                raise ValueError(f"Metric {name} is not a histogram")
                
            # Gera label key
            label_key = self._label_key(name, labels)
            
            # Atualiza estatísticas
            self.metrics[name]["sum"][label_key] += value
            self.metrics[name]["count"][label_key] += 1
            
            # Atualiza buckets
            for bucket in config.buckets:
                if value <= bucket:
                    self.metrics[name]["buckets"][label_key][bucket] += 1
                    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna todas as métricas"""
        with self.lock:
            result = {}
            
            for name, config in self.configs.items():
                if config.type == "counter":
                    result[name] = dict(self.metrics[name])
                elif config.type == "gauge":
                    result[name] = dict(self.metrics[name])
                elif config.type == "histogram":
                    result[name] = {
                        "sum": dict(self.metrics[name]["sum"]),
                        "count": dict(self.metrics[name]["count"]),
                        "buckets": {
                            label_key: dict(buckets)
                            for label_key, buckets
                            in self.metrics[name]["buckets"].items()
                        }
                    }
                    
            return result
            
    def get_metric(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Any:
        """Retorna valor de métrica específica"""
        with self.lock:
            if name not in self.configs:
                raise ValueError(f"Unknown metric: {name}")
                
            config = self.configs[name]
            label_key = self._label_key(name, labels)
            
            if config.type in ("counter", "gauge"):
                return self.metrics[name][label_key]
            elif config.type == "histogram":
                return {
                    "sum": self.metrics[name]["sum"][label_key],
                    "count": self.metrics[name]["count"][label_key],
                    "buckets": dict(
                        self.metrics[name]["buckets"][label_key]
                    )
                }
                
    def reset_metric(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ):
        """Reseta métrica específica"""
        with self.lock:
            if name not in self.configs:
                raise ValueError(f"Unknown metric: {name}")
                
            config = self.configs[name]
            
            if labels:
                # Reset apenas labels específicos
                label_key = self._label_key(name, labels)
                if config.type in ("counter", "gauge"):
                    del self.metrics[name][label_key]
                elif config.type == "histogram":
                    del self.metrics[name]["sum"][label_key]
                    del self.metrics[name]["count"][label_key]
                    del self.metrics[name]["buckets"][label_key]
            else:
                # Reset completo
                if config.type == "counter":
                    self.metrics[name] = defaultdict(int)
                elif config.type == "gauge":
                    self.metrics[name] = defaultdict(float)
                elif config.type == "histogram":
                    self.metrics[name] = {
                        "sum": defaultdict(float),
                        "count": defaultdict(int),
                        "buckets": defaultdict(lambda: defaultdict(int))
                    }
                    
    def export_prometheus(self) -> str:
        """Exporta métricas no formato Prometheus"""
        lines = []
        
        for name, config in self.configs.items():
            # Header
            lines.append(f"# HELP {name} {config.description}")
            lines.append(f"# TYPE {name} {config.type}")
            
            if config.type in ("counter", "gauge"):
                for label_key, value in self.metrics[name].items():
                    labels = self._parse_label_key(label_key)
                    label_str = self._format_labels(labels)
                    lines.append(f"{name}{label_str} {value}")
                    
            elif config.type == "histogram":
                for label_key in self.metrics[name]["buckets"]:
                    labels = self._parse_label_key(label_key)
                    
                    # Buckets
                    acc = 0
                    for bucket, count in sorted(
                        self.metrics[name]["buckets"][label_key].items()
                    ):
                        acc += count
                        bucket_labels = {
                            **labels,
                            "le": str(bucket)
                        }
                        label_str = self._format_labels(bucket_labels)
                        lines.append(
                            f"{name}_bucket{label_str} {acc}"
                        )
                        
                    # Infinity bucket
                    inf_labels = {
                        **labels,
                        "le": "+Inf"
                    }
                    label_str = self._format_labels(inf_labels)
                    lines.append(
                        f"{name}_bucket{label_str} "
                        f"{self.metrics[name]['count'][label_key]}"
                    )
                    
                    # Sum
                    label_str = self._format_labels(labels)
                    lines.append(
                        f"{name}_sum{label_str} "
                        f"{self.metrics[name]['sum'][label_key]}"
                    )
                    
                    # Count
                    lines.append(
                        f"{name}_count{label_str} "
                        f"{self.metrics[name]['count'][label_key]}"
                    )
                    
        return "\n".join(lines)
        
    def _label_key(
        self,
        name: str,
        labels: Optional[Dict[str, str]]
    ) -> str:
        """Gera chave única para labels"""
        config = self.configs[name]
        
        if not labels:
            return ""
            
        # Valida labels
        for label in labels:
            if label not in config.labels:
                raise ValueError(
                    f"Invalid label {label} for metric {name}"
                )
                
        # Gera chave ordenada
        return ",".join(
            f"{k}={v}"
            for k, v in sorted(labels.items())
        )
        
    def _parse_label_key(self, key: str) -> Dict[str, str]:
        """Converte label key em dicionário"""
        if not key:
            return {}
            
        return dict(
            label.split("=")
            for label in key.split(",")
        )
        
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Formata labels para Prometheus"""
        if not labels:
            return ""
            
        label_str = ",".join(
            f'{k}="{v}"'
            for k, v in sorted(labels.items())
        )
        return f"{{{label_str}}}" 