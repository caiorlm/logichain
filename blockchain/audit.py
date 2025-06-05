"""
Módulo de auditoria e monitoramento da blockchain
"""

import json
import time
import hashlib
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal
from collections import defaultdict

from .block import Block
from .wallet import Wallet
from .contract import DeliveryContract, TokenConversionContract

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('blockchain.audit')

@dataclass
class AuditEvent:
    """Evento de auditoria"""
    timestamp: float
    event_type: str
    data: Dict
    hash: Optional[str] = None
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
            
    def calculate_hash(self) -> str:
        """Calcula hash do evento"""
        event_data = {
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data
        }
        event_string = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(event_string.encode()).hexdigest()

class AuditTrail:
    """
    Trilha de auditoria
    Registra e monitora todas as operações
    """
    
    def __init__(self):
        self.events: List[AuditEvent] = []
        self.event_types: Set[str] = set()
        self.metrics: Dict[str, Dict] = defaultdict(lambda: defaultdict(int))
        
    def log_event(
        self,
        event_type: str,
        data: Dict,
        timestamp: Optional[float] = None
    ) -> AuditEvent:
        """
        Registra evento de auditoria
        
        Args:
            event_type: Tipo do evento (block_added, tx_validated, etc)
            data: Dados do evento
            timestamp: Timestamp opcional (default: now)
        """
        event = AuditEvent(
            timestamp=timestamp or time.time(),
            event_type=event_type,
            data=data
        )
        
        self.events.append(event)
        self.event_types.add(event_type)
        
        # Atualiza métricas
        self._update_metrics(event)
        
        # Log para arquivo
        self._log_to_file(event)
        
        return event
        
    def get_events(
        self,
        event_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[AuditEvent]:
        """
        Retorna eventos filtrados
        
        Args:
            event_type: Filtrar por tipo
            start_time: Timestamp inicial
            end_time: Timestamp final
        """
        events = self.events
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
            
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
            
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
            
        return events
        
    def get_metrics(
        self,
        metric_type: Optional[str] = None
    ) -> Dict:
        """
        Retorna métricas agregadas
        
        Args:
            metric_type: Tipo de métrica (opcional)
        """
        if metric_type:
            return self.metrics[metric_type]
        return dict(self.metrics)
        
    def verify_chain(self) -> bool:
        """
        Verifica integridade da cadeia de eventos
        """
        for i, event in enumerate(self.events[1:], 1):
            previous = self.events[i-1]
            
            # Verifica ordem temporal
            if event.timestamp < previous.timestamp:
                return False
                
            # Verifica hashes
            if event.hash != event.calculate_hash():
                return False
                
        return True
        
    def export_audit_log(self) -> Dict:
        """
        Exporta log de auditoria completo
        """
        return {
            'events': [asdict(e) for e in self.events],
            'metrics': dict(self.metrics),
            'event_types': list(self.event_types)
        }
        
    def _update_metrics(self, event: AuditEvent):
        """Atualiza métricas baseado no evento"""
        
        # Contadores por tipo
        self.metrics['event_counts'][event.event_type] += 1
        
        # Métricas específicas por tipo
        if event.event_type == 'block_added':
            self._update_block_metrics(event.data)
        elif event.event_type == 'tx_validated':
            self._update_transaction_metrics(event.data)
        elif event.event_type == 'contract_created':
            self._update_contract_metrics(event.data)
            
    def _update_block_metrics(self, data: Dict):
        """Atualiza métricas de blocos"""
        
        self.metrics['blocks']['total'] += 1
        
        if data.get('transactions'):
            self.metrics['blocks']['with_transactions'] += 1
            self.metrics['transactions']['total'] += len(data['transactions'])
            
        if data.get('reward'):
            self.metrics['rewards']['total'] += Decimal(str(data['reward']))
            
    def _update_transaction_metrics(self, data: Dict):
        """Atualiza métricas de transações"""
        
        token_type = data.get('token_type', 'unknown')
        self.metrics['transactions'][f'by_type_{token_type}'] += 1
        
        if amount := data.get('amount'):
            self.metrics['transactions'][f'volume_{token_type}'] += Decimal(str(amount))
            
    def _update_contract_metrics(self, data: Dict):
        """Atualiza métricas de contratos"""
        
        contract_type = data.get('contract_type', 'unknown')
        self.metrics['contracts'][f'by_type_{contract_type}'] += 1
        
        if value := data.get('value'):
            self.metrics['contracts'][f'value_{contract_type}'] += Decimal(str(value))
            
    def _log_to_file(self, event: AuditEvent):
        """Registra evento em arquivo de log"""
        
        logger.info(
            f"Event: {event.event_type} - "
            f"Hash: {event.hash} - "
            f"Data: {json.dumps(event.data, sort_keys=True)}"
        )

class SecurityMonitor:
    """
    Monitor de segurança
    Detecta anomalias e tentativas de ataque
    """
    
    def __init__(self, audit_trail: AuditTrail):
        self.audit_trail = audit_trail
        self.alerts: List[Dict] = []
        
    def check_double_spend(self, transaction: Dict) -> bool:
        """
        Verifica tentativa de double spend
        """
        tx_events = self.audit_trail.get_events('tx_validated')
        
        for event in tx_events:
            tx = event.data
            if (tx['from_address'] == transaction['from_address'] and
                tx['nonce'] == transaction['nonce']):
                self._create_alert(
                    'double_spend_attempt',
                    f"Double spend attempt from {tx['from_address']}"
                )
                return True
                
        return False
        
    def check_replay_attack(self, transaction: Dict) -> bool:
        """
        Verifica tentativa de replay attack
        """
        tx_events = self.audit_trail.get_events('tx_validated')
        
        for event in tx_events:
            tx = event.data
            if (tx['signature'] == transaction['signature'] and
                tx['hash'] != transaction['hash']):
                self._create_alert(
                    'replay_attack',
                    f"Replay attack detected for tx {tx['hash']}"
                )
                return True
                
        return False
        
    def check_supply_manipulation(self, block: Block) -> bool:
        """
        Verifica tentativa de manipulação de supply
        """
        if not hasattr(block, 'reward'):
            return False
            
        total_supply = sum(
            Decimal(str(e.data['reward']))
            for e in self.audit_trail.get_events('block_added')
            if 'reward' in e.data
        )
        
        if total_supply + Decimal(str(block.reward)) > Decimal('21_000_000'):
            self._create_alert(
                'supply_manipulation',
                f"Supply manipulation attempt in block {block.hash}"
            )
            return True
            
        return False
        
    def check_timestamp_manipulation(self, block: Block) -> bool:
        """
        Verifica manipulação de timestamp
        """
        block_events = self.audit_trail.get_events('block_added')
        
        if block_events:
            last_block = block_events[-1].data
            if block.timestamp <= last_block['timestamp']:
                self._create_alert(
                    'timestamp_manipulation',
                    f"Timestamp manipulation in block {block.hash}"
                )
                return True
                
        return False
        
    def get_alerts(
        self,
        alert_type: Optional[str] = None,
        start_time: Optional[float] = None
    ) -> List[Dict]:
        """
        Retorna alertas filtrados
        """
        alerts = self.alerts
        
        if alert_type:
            alerts = [a for a in alerts if a['type'] == alert_type]
            
        if start_time:
            alerts = [a for a in alerts if a['timestamp'] >= start_time]
            
        return alerts
        
    def _create_alert(self, alert_type: str, message: str):
        """Cria novo alerta"""
        
        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': time.time()
        }
        
        self.alerts.append(alert)
        logger.warning(f"Security Alert: {message}")

class AuditLog:
    """
    Classe principal de auditoria que combina AuditTrail e SecurityMonitor
    """
    
    def __init__(self):
        self.audit_trail = AuditTrail()
        self.security_monitor = SecurityMonitor(self.audit_trail)
        
    def start(self):
        """Inicia o sistema de auditoria"""
        logger.info("Sistema de auditoria iniciado")
        
    def log_event(self, event_type: str, data: Dict) -> AuditEvent:
        """Registra um evento"""
        return self.audit_trail.log_event(event_type, data)
        
    def check_transaction(self, transaction: Dict) -> bool:
        """Verifica uma transação"""
        if not self.security_monitor.check_double_spend(transaction):
            return False
        if not self.security_monitor.check_replay_attack(transaction):
            return False
        return True
        
    def check_block(self, block: Block) -> bool:
        """Verifica um bloco"""
        if not self.security_monitor.check_supply_manipulation(block):
            return False
        if not self.security_monitor.check_timestamp_manipulation(block):
            return False
        return True
        
    def get_metrics(self) -> Dict:
        """Retorna métricas do sistema"""
        return self.audit_trail.get_metrics()
        
    def get_alerts(self) -> List[Dict]:
        """Retorna alertas de segurança"""
        return self.security_monitor.get_alerts()
        
    def verify_integrity(self) -> bool:
        """Verifica integridade do log de auditoria"""
        return self.audit_trail.verify_chain() 