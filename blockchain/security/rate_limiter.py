"""
Rate limiter com múltiplas estratégias
"""

from __future__ import annotations
from typing import Dict, Optional, List, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import time
import threading
import logging
from collections import deque
from datetime import datetime, timedelta

class RateLimitStrategy(Enum):
    """Estratégias de rate limiting"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"

@dataclass
class RateLimitConfig:
    """Configuração do rate limiter"""
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    rate: float = 100.0  # Requisições por segundo
    burst: int = 200  # Burst máximo permitido
    window_size: int = 60  # Tamanho da janela em segundos (para sliding/fixed window)
    max_requests: int = 100
    time_window: int = 60  # seconds
    cooldown_period: int = 300  # seconds
    failure_threshold: float = 0.5  # 50% failure rate triggers circuit breaker

class TokenBucket:
    """Implementação aprimorada do algoritmo Token Bucket"""
    
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self.lock = threading.Lock()
        self.ip_buckets: Dict[str, float] = {}
        self.ip_last_update: Dict[str, float] = {}
        self.ip_rate_limit = rate / 2  # Limite por IP é metade do limite global
        
    def check_rate_limit(self, ip: Optional[str] = None) -> bool:
        with self.lock:
            now = time.time()
            
            # Atualiza bucket global
            time_passed = now - self.last_update
            self.tokens = min(
                self.burst,
                self.tokens + time_passed * self.rate
            )
            self.last_update = now
            
            # Se não tem IP, só verifica global
            if not ip:
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
                return False
                
            # Atualiza bucket do IP
            if ip not in self.ip_buckets:
                self.ip_buckets[ip] = self.burst / 2  # Burst inicial por IP
                self.ip_last_update[ip] = now
                
            time_passed = now - self.ip_last_update[ip]
            self.ip_buckets[ip] = min(
                self.burst / 2,  # Burst máximo por IP
                self.ip_buckets[ip] + time_passed * self.ip_rate_limit
            )
            self.ip_last_update[ip] = now
            
            # Verifica limites global e por IP
            if self.tokens >= 1 and self.ip_buckets[ip] >= 1:
                self.tokens -= 1
                self.ip_buckets[ip] -= 1
                return True
                
            return False
            
    def get_stats(self) -> Dict:
        return {
            'tokens': self.tokens,
            'rate': self.rate,
            'burst': self.burst,
            'ip_buckets': len(self.ip_buckets),
            'ip_rate_limit': self.ip_rate_limit
        }

class SlidingWindow:
    """Implementação do algoritmo Sliding Window"""
    
    def __init__(self, rate: float, window_size: int):
        self.rate = rate
        self.window_size = window_size
        self.requests = []
        self.lock = threading.Lock()
        
    def check_rate_limit(self) -> bool:
        with self.lock:
            now = time.time()
            
            # Remove requisições antigas
            self.requests = [
                ts for ts in self.requests
                if now - ts <= self.window_size
            ]
            
            # Verifica limite
            if len(self.requests) < self.rate * self.window_size:
                self.requests.append(now)
                return True
            return False
            
    def get_stats(self) -> Dict:
        now = time.time()
        active_requests = len([
            ts for ts in self.requests
            if now - ts <= self.window_size
        ])
        return {
            'active_requests': active_requests,
            'rate': self.rate,
            'window_size': self.window_size
        }

class FixedWindow:
    """Implementação do algoritmo Fixed Window"""
    
    def __init__(self, rate: float, window_size: int):
        self.rate = rate
        self.window_size = window_size
        self.current_window = time.time() // window_size
        self.request_count = 0
        self.lock = threading.Lock()
        
    def check_rate_limit(self) -> bool:
        with self.lock:
            now = time.time()
            current_window = now // self.window_size
            
            # Nova janela
            if current_window > self.current_window:
                self.current_window = current_window
                self.request_count = 0
                
            # Verifica limite
            if self.request_count < self.rate * self.window_size:
                self.request_count += 1
                return True
            return False
            
    def get_stats(self) -> Dict:
        return {
            'request_count': self.request_count,
            'rate': self.rate,
            'window_size': self.window_size,
            'current_window': self.current_window
        }

class RateLimiter:
    """Rate limiter principal com suporte a múltiplas estratégias e limites por IP"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        
        # Cria implementação baseada na estratégia
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.impl = TokenBucket(config.rate, config.burst)
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.impl = SlidingWindow(config.rate, config.window_size)
        elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
            self.impl = FixedWindow(config.rate, config.window_size)
        else:
            raise ValueError(f"Invalid rate limit strategy: {config.strategy}")
            
        # Cache de violações
        self.violations: Dict[str, List[float]] = {}
        self.violation_window = 3600  # 1 hora
        self.max_violations = 10
        self.banned_ips: Set[str] = set()
        
    def check_rate_limit(self, ip: Optional[str] = None) -> bool:
        """Verifica se a requisição está dentro do limite"""
        # Verifica ban
        if ip and ip in self.banned_ips:
            return False
            
        # Verifica limite
        allowed = self.impl.check_rate_limit(ip)
        
        # Registra violação
        if not allowed and ip:
            self._record_violation(ip)
            
        return allowed
        
    def _record_violation(self, ip: str):
        """Registra violação de rate limit"""
        now = time.time()
        
        # Remove violações antigas
        if ip in self.violations:
            self.violations[ip] = [
                ts for ts in self.violations[ip]
                if now - ts <= self.violation_window
            ]
        else:
            self.violations[ip] = []
            
        # Adiciona nova violação
        self.violations[ip].append(now)
        
        # Verifica ban
        if len(self.violations[ip]) >= self.max_violations:
            self.banned_ips.add(ip)
            logging.warning(f"IP banned due to rate limit violations: {ip}")
            
    def get_stats(self) -> Dict:
        """Retorna estatísticas do rate limiter"""
        stats = self.impl.get_stats()
        stats.update({
            'strategy': self.config.strategy.value,
            'violations': len(self.violations),
            'banned_ips': len(self.banned_ips)
        })
        return stats

def rate_limit(
    rate: int,
    burst: Optional[int] = None,
    window: int = 1,
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
):
    """
    Decorator for rate limiting functions
    
    Args:
        rate: Requests per second/window
        burst: Maximum burst size (for token/leaky bucket)
        window: Window size in seconds (for fixed/sliding window)
        strategy: Rate limiting strategy
    """
    def decorator(func):
        config = RateLimitConfig(
            strategy=strategy,
            rate=rate,
            burst=burst or rate,
            window_size=window
        )
        limiter = RateLimiter(config)
        
        def wrapper(*args, **kwargs):
            if not limiter.check_rate_limit():
                raise Exception("Rate limit exceeded")
            return func(*args, **kwargs)
            
        return wrapper
    return decorator 

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.failures = 0
        self.total_requests = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.lock = threading.Lock()
        
    def record_success(self) -> None:
        """Record successful request"""
        with self.lock:
            self.total_requests += 1
            if self.state == "HALF-OPEN":
                self.state = "CLOSED"
                self.failures = 0
                logging.info("Circuit breaker reset to CLOSED state")
                
    def record_failure(self) -> None:
        """Record failed request"""
        with self.lock:
            self.failures += 1
            self.total_requests += 1
            self.last_failure_time = datetime.now()
            
            if self.state == "CLOSED":
                failure_rate = self.failures / self.total_requests
                if failure_rate >= self.config.failure_threshold:
                    self.state = "OPEN"
                    logging.warning("Circuit breaker OPENED due to high failure rate")
                    
    def allow_request(self) -> bool:
        """Check if request should be allowed"""
        with self.lock:
            if self.state == "CLOSED":
                return True
                
            if self.state == "OPEN":
                if not self.last_failure_time:
                    return True
                    
                cooldown_end = self.last_failure_time + timedelta(
                    seconds=self.config.cooldown_period
                )
                if datetime.now() >= cooldown_end:
                    self.state = "HALF-OPEN"
                    logging.info("Circuit breaker entering HALF-OPEN state")
                    return True
                    
                return False
                
            # HALF-OPEN state
            return True
            
    def reset(self) -> None:
        """Reset circuit breaker state"""
        with self.lock:
            self.failures = 0
            self.total_requests = 0
            self.last_failure_time = None
            self.state = "CLOSED" 