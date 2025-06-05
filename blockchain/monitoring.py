"""
Sistema de monitoramento com métricas e alertas
"""

from typing import Dict, List, Optional, Any
import threading
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

@dataclass
class Metric:
    """Métrica com valor e tags"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str]

@dataclass
class Alert:
    """Alerta de monitoramento"""
    name: str
    description: str
    severity: str
    timestamp: float
    tags: Dict[str, str]
    value: Optional[float] = None

class Monitor:
    """
    Sistema de monitoramento com:
    - Coleta de métricas
    - Geração de alertas
    - Persistência de dados
    - Exportação para Prometheus
    """
    
    def __init__(self, retention_days: int = 7):
        # Configuração
        self.retention_days = retention_days
        
        # Armazenamento
        self.metrics: List[Metric] = []
        self.alerts: List[Alert] = []
        
        # Thresholds e regras
        self.alert_thresholds: Dict[str, Dict] = {
            'transaction_rate': {
                'warning': 1000,  # txs/s
                'critical': 5000
            },
            'block_time': {
                'warning': 30,  # segundos
                'critical': 60
            },
            'memory_usage': {
                'warning': 0.8,  # 80%
                'critical': 0.9
            },
            'peer_count': {
                'warning': 5,  # peers
                'critical': 3
            }
        }
        
        # Threading
        self.lock = threading.RLock()
        self._start_cleanup_thread()
        
        logging.info("Monitor initialized")
        
    def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Registra uma métrica"""
        with self.lock:
            metric = Metric(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {}
            )
            self.metrics.append(metric)
            
            # Verifica alertas
            self._check_alerts(metric)
            
    def add_alert(
        self,
        name: str,
        description: str,
        severity: str,
        tags: Optional[Dict[str, str]] = None,
        value: Optional[float] = None
    ):
        """Adiciona um alerta"""
        with self.lock:
            alert = Alert(
                name=name,
                description=description,
                severity=severity,
                timestamp=time.time(),
                tags=tags or {},
                value=value
            )
            self.alerts.append(alert)
            logging.warning(
                f"Alert: {name} - {description} "
                f"[severity={severity}]"
            )
            
    def get_metrics(
        self,
        name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Metric]:
        """Retorna métricas filtradas"""
        with self.lock:
            filtered = self.metrics
            
            if name:
                filtered = [m for m in filtered if m.name == name]
                
            if tags:
                filtered = [
                    m for m in filtered
                    if all(m.tags.get(k) == v for k, v in tags.items())
                ]
                
            if start_time:
                filtered = [m for m in filtered if m.timestamp >= start_time]
                
            if end_time:
                filtered = [m for m in filtered if m.timestamp <= end_time]
                
            return filtered
            
    def get_alerts(
        self,
        severity: Optional[str] = None,
        start_time: Optional[float] = None
    ) -> List[Alert]:
        """Retorna alertas filtrados"""
        with self.lock:
            filtered = self.alerts
            
            if severity:
                filtered = [a for a in filtered if a.severity == severity]
                
            if start_time:
                filtered = [a for a in filtered if a.timestamp >= start_time]
                
            return filtered
            
    def export_prometheus(self) -> str:
        """Exporta métricas no formato Prometheus"""
        with self.lock:
            lines = []
            
            # Agrupa por nome
            by_name: Dict[str, List[Metric]] = {}
            for metric in self.metrics:
                if metric.name not in by_name:
                    by_name[metric.name] = []
                by_name[metric.name].append(metric)
                
            # Gera linhas
            for name, metrics in by_name.items():
                # Help e type
                lines.append(f"# HELP {name} Blockchain metric")
                lines.append(f"# TYPE {name} gauge")
                
                # Métricas
                for m in metrics:
                    tags_str = ','.join(
                        f'{k}="{v}"'
                        for k, v in m.tags.items()
                    )
                    if tags_str:
                        tags_str = '{' + tags_str + '}'
                    lines.append(f"{name}{tags_str} {m.value}")
                    
            return '\n'.join(lines)
            
    def export_json(self) -> str:
        """Exporta métricas e alertas em JSON"""
        with self.lock:
            data = {
                'metrics': [
                    {
                        'name': m.name,
                        'value': m.value,
                        'timestamp': m.timestamp,
                        'tags': m.tags
                    }
                    for m in self.metrics
                ],
                'alerts': [
                    {
                        'name': a.name,
                        'description': a.description,
                        'severity': a.severity,
                        'timestamp': a.timestamp,
                        'tags': a.tags,
                        'value': a.value
                    }
                    for a in self.alerts
                ]
            }
            return json.dumps(data, indent=2)
            
    def _check_alerts(self, metric: Metric):
        """Verifica thresholds e gera alertas"""
        if metric.name in self.alert_thresholds:
            thresholds = self.alert_thresholds[metric.name]
            
            # Verifica critical primeiro
            if 'critical' in thresholds and metric.value >= thresholds['critical']:
                self.add_alert(
                    f"{metric.name}_critical",
                    f"{metric.name} above critical threshold "
                    f"({metric.value} >= {thresholds['critical']})",
                    'critical',
                    metric.tags,
                    metric.value
                )
            # Depois warning
            elif 'warning' in thresholds and metric.value >= thresholds['warning']:
                self.add_alert(
                    f"{metric.name}_warning",
                    f"{metric.name} above warning threshold "
                    f"({metric.value} >= {thresholds['warning']})",
                    'warning',
                    metric.tags,
                    metric.value
                )
                
    def _cleanup_old_data(self):
        """Remove dados antigos"""
        with self.lock:
            now = time.time()
            cutoff = now - (self.retention_days * 24 * 3600)
            
            self.metrics = [
                m for m in self.metrics
                if m.timestamp > cutoff
            ]
            self.alerts = [
                a for a in self.alerts
                if a.timestamp > cutoff
            ]
            
    def _start_cleanup_thread(self):
        """Inicia thread de limpeza"""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(3600)  # 1 hora
                    self._cleanup_old_data()
                except Exception as e:
                    logging.error(f"Cleanup error: {e}")
                    
        thread = threading.Thread(
            target=cleanup_loop,
            daemon=True
        )
        thread.start() 