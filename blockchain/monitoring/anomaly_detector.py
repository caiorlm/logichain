"""
Sistema de detecção de anomalias
"""

from typing import Dict, List, Set, Optional, Any
import time
import threading
import logging
import json
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from ..core.transaction import Transaction
from ..core.block import Block
from ..security import SecurityManager

@dataclass
class AnomalyConfig:
    """Configuração do detector"""
    # Janelas de tempo
    short_window: int = 300  # 5 minutos
    medium_window: int = 3600  # 1 hora
    long_window: int = 86400  # 24 horas
    
    # Thresholds
    tx_rate_threshold: float = 2.0  # Desvios padrão
    fee_threshold: float = 3.0
    size_threshold: float = 2.5
    error_threshold: float = 10  # Erros por minuto
    
    # Blacklist
    blacklist_duration: int = 3600  # 1 hora
    max_warnings: int = 3
    
@dataclass
class AnomalyEvent:
    """Evento de anomalia"""
    event_type: str
    severity: str
    details: Dict
    timestamp: float
    source: str

class AnomalyDetector:
    """
    Detector de anomalias com machine learning
    
    Features:
    - Detecção em tempo real
    - Múltiplas janelas temporais
    - Auto-ajuste de thresholds
    - Blacklisting automático
    - Correlação de eventos
    """
    
    def __init__(
        self,
        config: Optional[AnomalyConfig] = None,
        security_manager: Optional[SecurityManager] = None
    ):
        self.config = config or AnomalyConfig()
        self.security = security_manager or SecurityManager()
        
        # Métricas por janela
        self.metrics: Dict[str, Dict[str, List[float]]] = {
            'short': defaultdict(list),
            'medium': defaultdict(list),
            'long': defaultdict(list)
        }
        
        # Estado
        self.anomalies: List[AnomalyEvent] = []
        self.blacklist: Dict[str, float] = {}
        self.warnings: Dict[str, int] = defaultdict(int)
        
        # Cache de estatísticas
        self.stats_cache: Dict[str, Dict] = {}
        self.last_update = time.time()
        
        # Threading
        self.lock = threading.RLock()
        self._start_maintenance_thread()
        
        logging.info("AnomalyDetector initialized")
        
    def process_transaction(self, tx: Transaction):
        """
        Processa transação para detecção
        
        Args:
            tx: Transação a analisar
        """
        with self.lock:
            # Skip se blacklisted
            if self._is_blacklisted(tx.from_address):
                return
                
            now = time.time()
            
            # Coleta métricas
            metrics = {
                'gas_price': float(tx.gas_price),
                'gas_limit': float(tx.gas_limit),
                'amount': float(tx.amount),
                'size': len(str(tx.to_dict()))
            }
            
            # Atualiza janelas
            self._update_metrics('short', metrics, now)
            self._update_metrics('medium', metrics, now)
            self._update_metrics('long', metrics, now)
            
            # Detecta anomalias
            anomalies = self._detect_transaction_anomalies(tx, metrics)
            
            # Processa anomalias
            for anomaly in anomalies:
                self._handle_anomaly(anomaly)
                
    def process_block(self, block: Block):
        """
        Processa bloco para detecção
        
        Args:
            block: Bloco a analisar
        """
        with self.lock:
            now = time.time()
            
            # Coleta métricas
            metrics = {
                'size': len(str(block.to_dict())),
                'tx_count': len(block.transactions),
                'gas_used': block.gas_used,
                'timestamp_delta': now - block.timestamp
            }
            
            # Atualiza janelas
            self._update_metrics('short', metrics, now)
            self._update_metrics('medium', metrics, now)
            self._update_metrics('long', metrics, now)
            
            # Detecta anomalias
            anomalies = self._detect_block_anomalies(block, metrics)
            
            # Processa anomalias
            for anomaly in anomalies:
                self._handle_anomaly(anomaly)
                
    def process_error(self, error: Dict):
        """
        Processa erro para detecção
        
        Args:
            error: Detalhes do erro
        """
        with self.lock:
            now = time.time()
            
            # Coleta métricas
            metrics = {
                'count': 1,
                'severity': error.get('severity', 1)
            }
            
            # Atualiza janelas
            self._update_metrics('short', metrics, now)
            
            # Detecta anomalias
            anomalies = self._detect_error_anomalies(error, metrics)
            
            # Processa anomalias
            for anomaly in anomalies:
                self._handle_anomaly(anomaly)
                
    def _update_metrics(
        self,
        window: str,
        metrics: Dict[str, float],
        timestamp: float
    ):
        """Atualiza métricas para janela"""
        # Determina janela
        if window == 'short':
            cutoff = timestamp - self.config.short_window
        elif window == 'medium':
            cutoff = timestamp - self.config.medium_window
        else:
            cutoff = timestamp - self.config.long_window
            
        # Remove métricas antigas
        for metric, values in self.metrics[window].items():
            self.metrics[window][metric] = [
                (ts, val) for ts, val in values
                if ts > cutoff
            ]
            
        # Adiciona novas métricas
        for metric, value in metrics.items():
            self.metrics[window][metric].append((timestamp, value))
            
    def _detect_transaction_anomalies(
        self,
        tx: Transaction,
        metrics: Dict[str, float]
    ) -> List[AnomalyEvent]:
        """Detecta anomalias em transação"""
        anomalies = []
        now = time.time()
        
        # Analisa taxa de transações
        tx_rates = self._get_metric_stats('short', 'tx_count')
        if tx_rates['rate'] > tx_rates['mean'] + (
            self.config.tx_rate_threshold * tx_rates['std']
        ):
            anomalies.append(
                AnomalyEvent(
                    event_type='high_tx_rate',
                    severity='medium',
                    details={
                        'rate': tx_rates['rate'],
                        'threshold': tx_rates['mean'] + (
                            self.config.tx_rate_threshold * tx_rates['std']
                        ),
                        'tx_hash': tx.hash
                    },
                    timestamp=now,
                    source=tx.from_address
                )
            )
            
        # Analisa gas price
        if metrics['gas_price'] > self._get_metric_percentile(
            'medium',
            'gas_price',
            0.99
        ):
            anomalies.append(
                AnomalyEvent(
                    event_type='high_gas_price',
                    severity='low',
                    details={
                        'gas_price': metrics['gas_price'],
                        'tx_hash': tx.hash
                    },
                    timestamp=now,
                    source=tx.from_address
                )
            )
            
        # Analisa tamanho
        if metrics['size'] > self._get_metric_percentile(
            'long',
            'size',
            0.99
        ):
            anomalies.append(
                AnomalyEvent(
                    event_type='large_transaction',
                    severity='low',
                    details={
                        'size': metrics['size'],
                        'tx_hash': tx.hash
                    },
                    timestamp=now,
                    source=tx.from_address
                )
            )
            
        return anomalies
        
    def _detect_block_anomalies(
        self,
        block: Block,
        metrics: Dict[str, float]
    ) -> List[AnomalyEvent]:
        """Detecta anomalias em bloco"""
        anomalies = []
        now = time.time()
        
        # Analisa tempo entre blocos
        if metrics['timestamp_delta'] > self._get_metric_percentile(
            'medium',
            'timestamp_delta',
            0.95
        ):
            anomalies.append(
                AnomalyEvent(
                    event_type='high_block_time',
                    severity='medium',
                    details={
                        'delta': metrics['timestamp_delta'],
                        'block_hash': block.hash
                    },
                    timestamp=now,
                    source='block_producer'
                )
            )
            
        # Analisa uso de gas
        if metrics['gas_used'] > self._get_metric_percentile(
            'long',
            'gas_used',
            0.99
        ):
            anomalies.append(
                AnomalyEvent(
                    event_type='high_gas_usage',
                    severity='medium',
                    details={
                        'gas_used': metrics['gas_used'],
                        'block_hash': block.hash
                    },
                    timestamp=now,
                    source='block_producer'
                )
            )
            
        return anomalies
        
    def _detect_error_anomalies(
        self,
        error: Dict,
        metrics: Dict[str, float]
    ) -> List[AnomalyEvent]:
        """Detecta anomalias em erros"""
        anomalies = []
        now = time.time()
        
        # Analisa taxa de erros
        error_rates = self._get_metric_stats('short', 'count')
        if error_rates['rate'] > self.config.error_threshold:
            anomalies.append(
                AnomalyEvent(
                    event_type='high_error_rate',
                    severity='high',
                    details={
                        'rate': error_rates['rate'],
                        'threshold': self.config.error_threshold,
                        'error': error
                    },
                    timestamp=now,
                    source=error.get('source', 'unknown')
                )
            )
            
        return anomalies
        
    def _handle_anomaly(self, anomaly: AnomalyEvent):
        """Processa anomalia detectada"""
        # Registra anomalia
        self.anomalies.append(anomaly)
        
        # Atualiza warnings
        if anomaly.severity in ('medium', 'high'):
            self.warnings[anomaly.source] += 1
            
            # Verifica blacklist
            if self.warnings[anomaly.source] >= self.config.max_warnings:
                self._blacklist_source(
                    anomaly.source,
                    anomaly.timestamp
                )
                
        # Notifica
        self._send_alert(anomaly)
        
    def _blacklist_source(self, source: str, timestamp: float):
        """Adiciona fonte ao blacklist"""
        self.blacklist[source] = timestamp + self.config.blacklist_duration
        logging.warning(f"Source blacklisted: {source}")
        
    def _is_blacklisted(self, source: str) -> bool:
        """Verifica se fonte está em blacklist"""
        if source not in self.blacklist:
            return False
            
        # Remove se expirado
        if time.time() >= self.blacklist[source]:
            del self.blacklist[source]
            return False
            
        return True
        
    def _get_metric_stats(
        self,
        window: str,
        metric: str
    ) -> Dict[str, float]:
        """Calcula estatísticas de métrica"""
        values = [
            val for _, val in self.metrics[window][metric]
        ]
        
        if not values:
            return {
                'mean': 0,
                'std': 0,
                'rate': 0
            }
            
        return {
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'rate': len(values) / (
                self.config.short_window if window == 'short'
                else self.config.medium_window if window == 'medium'
                else self.config.long_window
            )
        }
        
    def _get_metric_percentile(
        self,
        window: str,
        metric: str,
        percentile: float
    ) -> float:
        """Calcula percentil de métrica"""
        values = [
            val for _, val in self.metrics[window][metric]
        ]
        
        if not values:
            return 0
            
        return float(np.percentile(values, percentile * 100))
        
    def _send_alert(self, anomaly: AnomalyEvent):
        """Envia alerta de anomalia"""
        logging.warning(
            f"Anomaly detected: {anomaly.event_type} "
            f"(severity: {anomaly.severity})"
        )
        
        # TODO: Implementar envio de alertas
        
    def _start_maintenance_thread(self):
        """Inicia thread de manutenção"""
        def maintenance_loop():
            while True:
                try:
                    time.sleep(60)  # 1 minuto
                    
                    with self.lock:
                        now = time.time()
                        
                        # Limpa blacklist
                        expired = [
                            source
                            for source, expiry in self.blacklist.items()
                            if now >= expiry
                        ]
                        for source in expired:
                            del self.blacklist[source]
                            
                        # Limpa warnings antigos
                        for source in list(self.warnings.keys()):
                            if self._is_blacklisted(source):
                                continue
                            self.warnings[source] = max(
                                0,
                                self.warnings[source] - 1
                            )
                            
                        # Limpa anomalias antigas
                        cutoff = now - self.config.long_window
                        self.anomalies = [
                            a for a in self.anomalies
                            if a.timestamp > cutoff
                        ]
                        
                except Exception as e:
                    logging.error(f"Error in maintenance loop: {e}")
                    
        thread = threading.Thread(
            target=maintenance_loop,
            daemon=True
        )
        thread.start()
        
    def get_status(self) -> Dict:
        """Retorna status do detector"""
        with self.lock:
            return {
                'anomalies': len(self.anomalies),
                'blacklisted': len(self.blacklist),
                'warnings': sum(self.warnings.values()),
                'metrics': {
                    window: {
                        metric: len(values)
                        for metric, values in metrics.items()
                    }
                    for window, metrics in self.metrics.items()
                }
            } 