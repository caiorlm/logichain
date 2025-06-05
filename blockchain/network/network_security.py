"""
Gerenciador de segurança da rede P2P
"""

import time
import logging
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
import threading

from ..security import SecurityConfig

class NetworkSecurityManager:
    """Gerencia segurança da rede P2P"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        """Inicializa gerenciador"""
        self.config = config or SecurityConfig()
        
        # Estado
        self.blocked_ips: Dict[str, datetime] = {}
        self.failed_attempts: Dict[str, int] = {}
        self.request_counts: Dict[str, Dict[int, int]] = {}
        self.peer_reputation: Dict[str, float] = {}
        self.peer_credentials: Dict[str, str] = {}
        
        # Lock
        self.lock = threading.RLock()
        
    def is_ip_blocked(self, ip: str) -> bool:
        """Verifica se IP está bloqueado"""
        with self.lock:
            if ip not in self.blocked_ips:
                return False
                
            block_time = self.blocked_ips[ip]
            if datetime.now() - block_time > self.config.ban_duration:
                del self.blocked_ips[ip]
                return False
                
            return True
            
    def block_ip(self, ip: str):
        """Bloqueia um IP"""
        with self.lock:
            self.blocked_ips[ip] = datetime.now()
            
    def report_suspicious_behavior(self, ip: str, behavior: str):
        """Registra comportamento suspeito"""
        with self.lock:
            # Incrementa tentativas falhas
            self.failed_attempts[ip] = self.failed_attempts.get(ip, 0) + 1
            
            # Atualiza reputação
            penalty = self._get_behavior_penalty(behavior)
            current_rep = self.peer_reputation.get(ip, 0)
            self.peer_reputation[ip] = max(-1.0, current_rep - penalty)
            
            # Verifica se deve bloquear
            if self.failed_attempts[ip] >= self.config.max_failed_attempts:
                self.block_ip(ip)
                
    def check_rate_limit(self, ip: str) -> bool:
        """Verifica rate limit"""
        with self.lock:
            now = int(time.time())
            window = now - self.config.rate_limit_window
            
            # Limpa contagens antigas
            if ip in self.request_counts:
                self.request_counts[ip] = {
                    ts: count
                    for ts, count in self.request_counts[ip].items()
                    if ts > window
                }
                
            # Conta requests na janela
            counts = self.request_counts.get(ip, {})
            total = sum(counts.values())
            
            # Verifica limite
            if total >= self.config.max_requests_per_window:
                self.report_suspicious_behavior(ip, "rate_limit_exceeded")
                return False
                
            # Incrementa contagem
            if ip not in self.request_counts:
                self.request_counts[ip] = {}
            self.request_counts[ip][now] = \
                self.request_counts[ip].get(now, 0) + 1
                
            return True
            
    def get_peer_reputation(self, ip: str) -> float:
        """Retorna reputação do peer"""
        return self.peer_reputation.get(ip, 0)
        
    def get_failed_attempts(self, ip: str) -> int:
        """Retorna número de tentativas falhas"""
        return self.failed_attempts.get(ip, 0)
        
    async def generate_peer_credentials(self, peer_id: str) -> str:
        """Gera credenciais para um peer"""
        # TODO: Implementar geração segura de credenciais
        auth_key = "test_key"
        self.peer_credentials[peer_id] = auth_key
        return auth_key
        
    def verify_peer_credentials(
        self,
        peer_id: str,
        auth_key: str
    ) -> bool:
        """Verifica credenciais de um peer"""
        return self.peer_credentials.get(peer_id) == auth_key
        
    def clear_blocks(self):
        """Limpa bloqueios"""
        with self.lock:
            self.blocked_ips.clear()
            self.failed_attempts.clear()
            self.request_counts.clear()
            
    def _get_behavior_penalty(self, behavior: str) -> float:
        """Retorna penalidade para um comportamento"""
        penalties = {
            "invalid_block": 0.3,
            "invalid_transaction": 0.2,
            "flood_attempt": 0.4,
            "malformed_packet": 0.2,
            "rate_limit_exceeded": 0.3,
            "too_many_connections": 0.2
        }
        return penalties.get(behavior, 0.1)
        
    def shutdown(self):
        """Desliga o gerenciador"""
        self.clear_blocks() 