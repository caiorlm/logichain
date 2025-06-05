import hashlib
import time
import random
import math
import os
import secrets
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
import numpy as np
from datetime import datetime
from pathlib import Path
import hmac
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.exceptions import InvalidKey
from functools import cached_property
import inspect
import sys

class SecurityError(Exception):
    """Erro de segurança crítico"""
    pass

class CodeIntegrityError(SecurityError):
    """Erro de integridade do código"""
    pass

class SystemKeyError(SecurityError):
    """Erro na chave do sistema"""
    pass

class BlockchainError(SecurityError):
    """Erro na cadeia de blocos"""
    pass

@dataclass
class SystemSecurity:
    """Gerencia segurança do sistema"""
    __slots__ = ['_system_key', '_code_hash', '_signing_key', '_timestamp_base']
    
    # Hash SHA-256 do código fonte original (será atualizado na primeira execução)
    ORIGINAL_CODE_HASH = None
    
    # Senha interna ofuscada (em produção, usar variável de ambiente)
    _INTERNAL_PASSWORD = b"INTERNAL_PASSWORD_PRODUCTION"
    
    # Modo de desenvolvimento (permite modificações no código)
    _DEVELOPMENT_MODE = True
    
    PHI = (1 + math.sqrt(5)) / 2  # Número áureo
    PI = math.pi
    
    def __init__(self):
        self._code_hash = self._calculate_code_hash()
        if not self.ORIGINAL_CODE_HASH:
            # Na primeira execução, define o hash original
            print("Primeira execução: Definindo hash do código...")
            SystemSecurity.ORIGINAL_CODE_HASH = self._code_hash
            print(f"Hash definido: {self._code_hash}")
        self._verify_code_integrity()
        self._system_key = self._derive_system_key()
        self._signing_key = self._generate_signing_key()
        self._timestamp_base = int(time.time())

    def _calculate_code_hash(self) -> str:
        """Calcula hash SHA-256 do código fonte"""
        try:
            current_file = inspect.getfile(self.__class__)
            with open(current_file, 'rb') as f:
                code = f.read()
            return hashlib.sha256(code).hexdigest()
        except Exception as e:
            raise CodeIntegrityError(f"Erro ao calcular hash do código: {e}")

    def _verify_code_integrity(self):
        """Verifica integridade do código fonte"""
        try:
            # Em modo de desenvolvimento, permite modificações
            if self._DEVELOPMENT_MODE:
                if self.ORIGINAL_CODE_HASH and self._code_hash != self.ORIGINAL_CODE_HASH:
                    print("Aviso: Código fonte modificado (modo desenvolvimento)")
                    # Atualiza o hash para a nova versão
                    SystemSecurity.ORIGINAL_CODE_HASH = self._code_hash
                return True
                
            # Em produção, verifica integridade normalmente
            if self.ORIGINAL_CODE_HASH and not hmac.compare_digest(self._code_hash, self.ORIGINAL_CODE_HASH):
                print(f"Hash atual: {self._code_hash}")
                print(f"Hash original: {self.ORIGINAL_CODE_HASH}")
                raise CodeIntegrityError("Código fonte foi modificado")
                
            return True
            
        except Exception as e:
            if "Código fonte foi modificado" in str(e):
                raise CodeIntegrityError(str(e))
            raise CodeIntegrityError(f"Falha na verificação de integridade: {e}")

    def hash_nts_seed(self, seed: str) -> str:
        """Gera hash SHA-256 da semente NTS"""
        try:
            # Primeira camada: SHA-256 do seed original
            hash1 = hashlib.sha256(seed.encode()).hexdigest()
            
            # Segunda camada: Combina com salt único
            salt = secrets.token_bytes(32)
            hash2 = hashlib.sha256(f"{hash1}:{salt.hex()}".encode()).hexdigest()
            
            # Terceira camada: Combina com chave do sistema
            final_hash = hashlib.sha256(
                f"{hash2}:{self._system_key.hex()}".encode()
            ).hexdigest()
            
            return final_hash
        except Exception as e:
            raise SecurityError(f"Erro ao gerar hash da semente NTS: {e}")

    def _derive_system_key(self) -> bytes:
        """Deriva chave do sistema usando PBKDF2"""
        try:
            # Salt único para esta instância
            salt = secrets.token_bytes(32)
            
            # Configura PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),  # Usa SHA-256 para consistência
                length=32,  # 256 bits
                salt=salt,
                iterations=480000,  # Número alto de iterações
            )
            
            # Deriva chave
            key = kdf.derive(self._INTERNAL_PASSWORD)
            
            # Verifica se chave é válida
            verifier = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            
            try:
                verifier.verify(self._INTERNAL_PASSWORD, key)
            except InvalidKey:
                raise SystemKeyError("Falha na verificação da chave")
                
            return key
            
        except Exception as e:
            raise SystemKeyError(f"Erro na derivação da chave: {e}")

    def _generate_signing_key(self) -> ec.EllipticCurvePrivateKey:
        """Gera chave para assinatura digital"""
        try:
            return ec.generate_private_key(ec.SECP256K1())  # Usa curva compatível com SHA-256
        except Exception as e:
            raise SecurityError(f"Erro na geração da chave de assinatura: {e}")

    @property
    def system_key(self) -> bytes:
        """Retorna chave do sistema"""
        return self._system_key

    @property
    def timestamp_base(self) -> int:
        """Retorna timestamp base"""
        return self._timestamp_base

    def sign_hash(self, hash_value: str) -> Tuple[int, int]:
        """Assina um hash usando ECDSA"""
        try:
            # Usa SHA-256 para assinatura
            signature = self._signing_key.sign(
                hash_value.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return decode_dss_signature(signature)
        except Exception as e:
            raise SecurityError(f"Erro na assinatura digital: {e}")

    def verify_signature(self, hash_value: str, signature: Tuple[int, int]) -> bool:
        """Verifica assinatura digital"""
        try:
            public_key = self._signing_key.public_key()
            signature_bytes = encode_dss_signature(*signature)
            public_key.verify(
                signature_bytes,
                hash_value.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception:
            return False

# Instância global de segurança (criada apenas uma vez)
SECURITY = SystemSecurity()

@dataclass
class IntervalCrypto:
    """Intervalo criptografado"""
    __slots__ = ['raw_interval', 'encrypted_value', 'validation_hash', 'entropy_hash', 'sequence_hash', 'security_salt']
    
    raw_interval: float  # Valor original (usado internamente)
    encrypted_value: str  # Hash SHA-512 do intervalo
    validation_hash: str  # Hash SHA-512 de validação
    entropy_hash: str  # Hash SHA-512 dos fatores de entropia
    sequence_hash: str  # Hash SHA-512 da sequência
    security_salt: bytes  # Salt único para este intervalo

    def __str__(self) -> str:
        """Retorna apenas hash truncado para prevenir análise"""
        return f"{self.encrypted_value[:16]}...{self.encrypted_value[-16:]}"

    def __repr__(self) -> str:
        return self.__str__()

@dataclass
class GPSPoint:
    latitude: float
    longitude: float
    timestamp: int

@dataclass
class RouteMetricsRaw:
    """Valores brutos das métricas (uso interno apenas)"""
    dist_reta_km: float = 0.0
    dist_extra_km: float = 0.0
    dist_total_km: float = 0.0
    dist_total_metros: float = 0.0
    tempo_reta_min: float = 0.0
    tempo_extra_min: float = 0.0
    tempo_total_min: float = 0.0

@dataclass
class RouteMetrics:
    """Métricas da rota com proteção matemática"""
    __slots__ = ['encrypted_dist_reta', 'encrypted_dist_extra', 'encrypted_dist_total', 
                 'encrypted_dist_metros', 'encrypted_tempo_reta', 'encrypted_tempo_extra', 
                 'encrypted_tempo_total', 'security_salt', '_raw']
    
    encrypted_dist_reta: str  # Hash SHA-512 da distância em linha reta
    encrypted_dist_extra: str  # Hash SHA-512 da distância extra
    encrypted_dist_total: str  # Hash SHA-512 da distância total
    encrypted_dist_metros: str  # Hash SHA-512 da distância em metros
    encrypted_tempo_reta: str  # Hash SHA-512 do tempo em linha reta
    encrypted_tempo_extra: str  # Hash SHA-512 do tempo extra
    encrypted_tempo_total: str  # Hash SHA-512 do tempo total
    security_salt: bytes  # Salt único para estas métricas
    
    def __init__(self, encrypted_dist_reta: str, encrypted_dist_extra: str, encrypted_dist_total: str,
                 encrypted_dist_metros: str, encrypted_tempo_reta: str, encrypted_tempo_extra: str,
                 encrypted_tempo_total: str, security_salt: bytes):
        """Initialize the RouteMetrics with required fields"""
        object.__setattr__(self, 'encrypted_dist_reta', encrypted_dist_reta)
        object.__setattr__(self, 'encrypted_dist_extra', encrypted_dist_extra)
        object.__setattr__(self, 'encrypted_dist_total', encrypted_dist_total)
        object.__setattr__(self, 'encrypted_dist_metros', encrypted_dist_metros)
        object.__setattr__(self, 'encrypted_tempo_reta', encrypted_tempo_reta)
        object.__setattr__(self, 'encrypted_tempo_extra', encrypted_tempo_extra)
        object.__setattr__(self, 'encrypted_tempo_total', encrypted_tempo_total)
        object.__setattr__(self, 'security_salt', security_salt)
        object.__setattr__(self, '_raw', RouteMetricsRaw())

    @property
    def raw(self) -> RouteMetricsRaw:
        """Retorna métricas brutas"""
        return self._raw

    @raw.setter
    def raw(self, value: RouteMetricsRaw):
        """Define métricas brutas"""
        object.__setattr__(self, '_raw', value)

    def encrypt_value(self, value: float) -> str:
        """Criptografa um valor usando SHA-512"""
        try:
            # Primeira camada: Combina valor com salt
            value_data = f"{value:.20f}:{self.security_salt.hex()}"
            
            # Segunda camada: Transformação não-linear
            transformed = bytes([
                int((b * SystemSecurity.PHI + ord(str(value)[0]) * SystemSecurity.PI) % 256)
                for b in value_data.encode()
            ])
            
            # Terceira camada: SHA-512
            return hashlib.sha512(transformed + SECURITY.system_key).hexdigest()
        except Exception as e:
            print(f"Aviso: Erro na criptografia do valor: {e}")
            return hashlib.sha512(str(value).encode()).hexdigest()

    def __str__(self) -> str:
        """Retorna apenas métricas públicas com ruído controlado"""
        # Adiciona ruído aleatório para prevenir análise
        noise_dist = 1 + (secrets.SystemRandom().random() * 0.02 - 0.01)  # ±1%
        noise_time = 1 + (secrets.SystemRandom().random() * 0.05 - 0.025)  # ±2.5%
        
        dist = self.raw.dist_total_km * noise_dist
        tempo = self.raw.tempo_total_min * noise_time
        
        return f"Distância total estimada: {dist:.2f} km\nTempo estimado: {tempo:.1f} minutos"

    def __repr__(self) -> str:
        return self.__str__()

@dataclass
class EncryptedMetrics:
    """Métricas criptografadas do bloco"""
    __slots__ = ['encrypted_time', 'encrypted_intervals', 'encrypted_points_count', 
                 'encrypted_distance', 'dist_hash', 'proof_hash', '_raw_metrics', 'security_salt']
    
    encrypted_time: str  # Hash SHA-512 do tempo
    encrypted_intervals: str  # Hash SHA-512 dos intervalos
    encrypted_points_count: str  # Hash SHA-512 do número de pontos
    encrypted_distance: str  # Hash SHA-512 da distância
    dist_hash: str  # Hash SHA-512 da distância
    proof_hash: str  # Hash SHA-512 de prova da validade das métricas
    _raw_metrics: RouteMetrics  # Métricas originais (usadas internamente)
    security_salt: bytes  # Salt único para este conjunto de métricas

    @property
    def raw_metrics(self) -> RouteMetrics:
        """Retorna métricas brutas"""
        return self._raw_metrics

    @raw_metrics.setter
    def raw_metrics(self, value: RouteMetrics):
        """Define métricas brutas"""
        self._raw_metrics = value

    def encrypt_route_data(self, data: str) -> str:
        """Criptografa dados da rota usando SHA-512"""
        try:
            # Primeira camada: Combina com salt
            combined = f"{data}:{self.security_salt.hex()}"
            
            # Segunda camada: Transformação não-linear
            transformed = bytes([
                int((b * SystemSecurity.PHI + i * SystemSecurity.PI) % 256)
                for i, b in enumerate(combined.encode())
            ])
            
            # Terceira camada: SHA-512
            return hashlib.sha512(transformed + SECURITY.system_key).hexdigest()
        except Exception as e:
            print(f"Aviso: Erro na criptografia dos dados da rota: {e}")
            return hashlib.sha512(data.encode()).hexdigest()

    def __str__(self) -> str:
        """Retorna apenas hash truncado para prevenir análise"""
        return f"Prova: {self.proof_hash[:16]}...{self.proof_hash[-16:]}"

    def __repr__(self) -> str:
        return self.__str__()

@dataclass
class Block:
    sequence_number: int
    points: List[GPSPoint]
    interval_rules: List[IntervalCrypto]
    validation_rule: str
    block_hash: str
    metrics: RouteMetrics
    encrypted_metrics: EncryptedMetrics
    previous_block_hash: Optional[str] = None
    timestamp: int = field(default_factory=lambda: SECURITY.timestamp_base)
    signature: Optional[Tuple[int, int]] = None
    is_valid: bool = True

    def __post_init__(self):
        """Inicializa e valida o bloco após criação"""
        if not self.block_hash:
            self.block_hash = self._calculate_hash()
        if not self.signature:
            self.signature = SECURITY.sign_hash(self.block_hash)

    def _calculate_hash(self) -> str:
        """Calcula hash do bloco incluindo hash anterior"""
        try:
            # Combina todos os dados do bloco
            block_data = (
                f"{self.sequence_number}:{self.timestamp}:"
                f"{[str(p) for p in self.points]}:{self.validation_rule}:"
                f"{self.metrics.encrypted_dist_total}:{self.encrypted_metrics.proof_hash}"
            )
            
            if self.previous_block_hash:
                block_data = f"{block_data}:{self.previous_block_hash}"
            
            # Primeira camada: SHA-512 dos dados
            current_hash = hashlib.sha512(block_data.encode()).digest()
            
            # Segunda camada: Combina com chave do sistema
            keyed_hash = bytes([
                a ^ b for a, b in zip(
                    current_hash,
                    SECURITY.system_key * (len(current_hash) // len(SECURITY.system_key) + 1)
                )
            ])
            
            # Terceira camada: SHA-512 final
            return hashlib.sha512(keyed_hash).hexdigest()
            
        except Exception as e:
            raise BlockchainError(f"Erro no cálculo do hash do bloco: {e}")

    def verify_signature(self) -> bool:
        """Verifica assinatura digital do bloco"""
        if not self.signature:
            return False
        return SECURITY.verify_signature(self.block_hash, self.signature)

    def verify_hash(self) -> bool:
        """Verifica se o hash do bloco é válido"""
        try:
            calculated_hash = self._calculate_hash()
            return hmac.compare_digest(calculated_hash, self.block_hash)
        except Exception:
            return False

    def __str__(self) -> str:
        """Retorna apenas hashes para prevenir análise de padrões"""
        return f"Bloco {self.sequence_number}\nHash: {self.block_hash[:8]}...{self.block_hash[-8:]}"

    def __repr__(self) -> str:
        return self.__str__()

@dataclass
class ContractInput:
    point_a_lat: float
    point_a_lon: float
    point_b_lat: float
    point_b_lon: float
    nts_seed: str  # Semente adicional para entropia
    timestamp: int = field(default_factory=lambda: int(time.time()))

@dataclass
class NTSVariables:
    """Variáveis derivadas da semente NTS (criptografadas)"""
    __slots__ = ['_encrypted_values', '_salt', '_system_key', '_values']
    
    def __init__(self, base_numeric: str, time_factor: float, distance_factor: float,
                 interval_modifier: float, point_spread: float, validation_threshold: float,
                 entropy_boost: List[float], system_key: bytes):
        """Inicializa com valores e criptografa"""
        # Inicializa todos os atributos primeiro
        self._salt = secrets.token_bytes(32)
        self._system_key = system_key
        self._encrypted_values = {}
        self._values = {}
        
        # Prepara os valores para criptografia
        values = {
            'base_numeric': base_numeric,
            'time_factor': time_factor,
            'distance_factor': distance_factor,
            'interval_modifier': interval_modifier,
            'point_spread': point_spread,
            'validation_threshold': validation_threshold,
            'entropy_boost': ','.join(map(str, entropy_boost))
        }
        
        # Armazena valores originais de forma segura (apenas em memória)
        self._values = values.copy()
        
        # Criptografa cada valor
        for key, value in values.items():
            self._encrypted_values[key] = self._encrypt_value(str(value))
    
    def _encrypt_value(self, value: str) -> str:
        """Criptografa um valor usando múltiplas camadas"""
        try:
            # Primeira camada: Combina com salt
            value_data = f"{value}:{self._salt.hex()}"
            
            # Segunda camada: Transformação não-linear
            transformed = bytes([
                int((b * SystemSecurity.PHI + i * SystemSecurity.PI) % 256)
                for i, b in enumerate(value_data.encode())
            ])
            
            # Terceira camada: XOR com chave do sistema
            xored = bytes([
                a ^ b for a, b in zip(
                    transformed,
                    self._system_key * (len(transformed) // len(self._system_key) + 1)
                )
            ])
            
            # Quarta camada: SHA-512
            return hashlib.sha512(xored).hexdigest()
        except Exception as e:
            print(f"Aviso: Erro na criptografia do valor NTS: {e}")
            return hashlib.sha512(str(time.time_ns()).encode()).hexdigest()
    
    def get_secure_value(self, key: str, default: any = None) -> any:
        """Retorna um valor de forma segura (apenas para uso interno)"""
        try:
            if key not in self._values:
                return default
            
            value = self._values[key]
            if key == 'entropy_boost':
                return [float(x) for x in value.split(',')]
            return type(default)(value) if default is not None else value
        except Exception:
            return default
    
    def verify_value(self, key: str, test_value: any) -> bool:
        """Verifica se um valor corresponde ao valor criptografado"""
        if key not in self._encrypted_values:
            return False
        
        # Criptografa o valor de teste da mesma forma
        test_encrypted = self._encrypt_value(str(test_value))
        
        # Compara os hashes de forma segura
        return hmac.compare_digest(test_encrypted, self._encrypted_values[key])
    
    def __str__(self) -> str:
        """Retorna apenas indicação de que os valores estão criptografados"""
        return "NTS Variables [encrypted]"
        
    def __repr__(self) -> str:
        return self.__str__()

class ProofOfDelivery:
    def __init__(self):
        # Constantes matemáticas transcendentais
        self.PHI = (1 + math.sqrt(5)) / 2  # Número áureo
        self.EULER = math.e
        self.PI = math.pi
        self.FEIGENBAUM = 4.669201  # Constante de Feigenbaum
        self.APERY = 1.202056903159594  # Constante de Apéry
        self.GAUSS = 0.8346268  # Constante de Gauss
        self.DEFAULT_SPEED = 60  # km/h
        self.R = 6371  # Earth's radius in kilometers
        
        # Gerador de números aleatórios seguro
        self.system_random = secrets.SystemRandom()
        
        # Usa sistema de segurança global
        self.SYSTEM_KEY = SECURITY.system_key
        
        # Verifica integridade do sistema
        if not self._verify_system_integrity():
            raise SecurityError("Sistema comprometido")
    
    def _verify_system_integrity(self) -> bool:
        """Verifica integridade do sistema"""
        try:
            # Em modo de desenvolvimento, verifica apenas módulos críticos
            if SystemSecurity._DEVELOPMENT_MODE:
                # Verifica se módulos críticos estão disponíveis
                required_modules = ['hashlib', 'secrets', 'cryptography']
                for module in required_modules:
                    if module not in sys.modules:
                        return False
                return True

            # Em produção, verifica tudo
            # Verifica se constantes matemáticas não foram alteradas
            if not math.isclose(self.PHI, (1 + math.sqrt(5)) / 2, rel_tol=1e-9):
                return False
            if not math.isclose(self.EULER, math.e, rel_tol=1e-9):
                return False
            if not math.isclose(self.PI, math.pi, rel_tol=1e-9):
                return False
            
            # Verifica se chave do sistema está presente
            if not self.SYSTEM_KEY or len(self.SYSTEM_KEY) != 64:
                return False
            
            # Verifica se módulos críticos estão disponíveis
            required_modules = ['hashlib', 'secrets', 'cryptography']
            for module in required_modules:
                if module not in sys.modules:
                    return False
            
            return True
            
        except Exception:
            return False

    def generate_transcendental_entropy(self, seed: bytes) -> List[float]:
        """Gera entropia usando números transcendentais e teoria do caos"""
        # Converte seed em número inicial
        seed_value = int.from_bytes(seed[:8], 'big') / (2**64)
        
        # Lista de constantes transcendentais
        transcendentals = [
            self.PI, self.EULER, self.PHI, 
            self.FEIGENBAUM, self.APERY, self.GAUSS
        ]
        
        # Aplica mapa logístico com diferentes constantes
        entropy_values = []
        x = seed_value
        
        for i in range(len(transcendentals)):
            # Usa cada constante transcendental como parâmetro
            r = 3.57 + (transcendentals[i] % 0.42)  # Mantém r no regime caótico
            
            # Iterações do mapa logístico
            for _ in range(10):
                x = r * x * (1 - x)
            
            entropy_values.append(x)
            
        return entropy_values

    def apply_kam_theorem(self, values: List[float]) -> List[float]:
        """Aplica princípios do Teorema KAM para garantir não-linearidade"""
        kam_values = []
        
        for i, v in enumerate(values):
            # Frequências irracionais baseadas em números transcendentais
            omega1 = self.PI * v
            omega2 = self.EULER * (1 - v)
            omega3 = self.PHI * (v + 0.5)
            
            # Transformação KAM-like
            kam_value = math.sin(omega1) + math.cos(omega2) + math.sin(omega3)
            kam_value = (kam_value + 3) / 6  # Normaliza para [0,1]
            
            kam_values.append(kam_value)
            
        return kam_values

    def generate_interval_crypto(self, base_entropy: bytes, sequence_number: int) -> IntervalCrypto:
        """Gera intervalo criptografado com múltiplas camadas de entropia"""
        try:
            # Gera entropia inicial com números transcendentais
            entropy_factors = self.generate_transcendental_entropy(base_entropy)
            
            # Aplica Teorema KAM
            chaos_components = self.apply_kam_theorem(entropy_factors)
            
            # Combina todos os fatores de forma não-linear
            combined_entropy = 1.0
            for i, (ef, cc) in enumerate(zip(entropy_factors, chaos_components)):
                try:
                    # Usa diferentes operações não-lineares para cada componente
                    if i % 3 == 0:
                        combined_entropy *= math.sin(ef * self.PI) * cc
                    elif i % 3 == 1:
                        combined_entropy += math.cos(ef * self.EULER) * cc
                    else:
                        # Corrige operação XOR usando inteiros
                        int_value = int((ef * cc * 1000000))
                        combined_entropy = float(int(combined_entropy * 1000000) ^ int_value) / 1000000
                except (ValueError, OverflowError) as e:
                    print(f"Aviso: Erro no cálculo de entropia combinada: {e}")
                    # Usa valor fallback seguro
                    combined_entropy = max(1.0, abs(combined_entropy))
            
            # Normaliza para gerar intervalo base entre 10 e 60 segundos
            base_interval = 10 + abs(combined_entropy % 1) * 50
            
            try:
                # Adiciona ruído baseado em distribuição de Cauchy
                noise = np.random.standard_cauchy() * 0.1
                noise = max(-0.5, min(0.5, noise))  # Limita o ruído
            except Exception as e:
                print(f"Aviso: Erro na geração de ruído: {e}")
                # Usa secrets para gerar ruído
                noise = float(secrets.randbelow(1000) - 500) / 1000  # -0.5 a 0.5
            
            interval = max(5, base_interval * (1 + noise))
            
            # Criptografa o intervalo usando SHA-512
            salt = secrets.token_bytes(32)
            
            # Primeira camada: Combina dados com salt
            interval_data = f"{interval:.20f}:{sequence_number}:{salt.hex()}"
            
            # Segunda camada: Transformação não-linear
            transformed = bytes([
                int((b * self.PHI + sequence_number * self.PI + i * self.EULER) % 256)
                for i, b in enumerate(interval_data.encode())
            ])
            
            # Terceira camada: SHA-512 com chave do sistema
            encrypted_value = hashlib.sha512(transformed + self.SYSTEM_KEY).hexdigest()
            
            # Gera hash de validação (SHA-512)
            validation_data = f"{encrypted_value}:{sequence_number}:{salt.hex()}"
            validation_transformed = bytes([
                int((b * self.EULER + sequence_number * self.GAUSS + i * self.PHI) % 256)
                for i, b in enumerate(validation_data.encode())
            ])
            validation_hash = hashlib.sha512(validation_transformed + self.SYSTEM_KEY).hexdigest()
            
            # Gera hash de entropia (SHA-512)
            entropy_data = f"{entropy_factors}:{chaos_components}:{salt.hex()}"
            entropy_transformed = bytes([
                int((b * self.APERY + sequence_number * self.PHI + i * self.PI) % 256)
                for i, b in enumerate(entropy_data.encode())
            ])
            entropy_hash = hashlib.sha512(entropy_transformed + self.SYSTEM_KEY).hexdigest()
            
            # Gera hash de sequência (SHA-512)
            sequence_data = f"{sequence_number}:{interval:.20f}:{salt.hex()}"
            sequence_transformed = bytes([
                int((b * self.PI + sequence_number * self.EULER + i * self.GAUSS) % 256)
                for i, b in enumerate(sequence_data.encode())
            ])
            sequence_hash = hashlib.sha512(sequence_transformed + self.SYSTEM_KEY).hexdigest()
            
            return IntervalCrypto(
                raw_interval=interval,
                encrypted_value=encrypted_value,
                validation_hash=validation_hash,
                entropy_hash=entropy_hash,
                sequence_hash=sequence_hash,
                security_salt=salt
            )
            
        except Exception as e:
            print(f"Erro crítico na geração de intervalo: {e}")
            # Retorna intervalo fallback seguro
            fallback_salt = secrets.token_bytes(32)
            fallback_base = hashlib.sha512(str(sequence_number).encode() + fallback_salt).hexdigest()
            return IntervalCrypto(
                raw_interval=30.0,  # Intervalo padrão seguro
                encrypted_value=hashlib.sha512(fallback_base.encode() + fallback_salt).hexdigest(),
                validation_hash=hashlib.sha512(fallback_base.encode() + fallback_salt).hexdigest(),
                entropy_hash=hashlib.sha512(fallback_base.encode() + fallback_salt).hexdigest(),
                sequence_hash=hashlib.sha512(fallback_base.encode() + fallback_salt).hexdigest(),
                security_salt=fallback_salt
            )

    def generate_sequence_parameters(self, seed_hash: bytes, distance_km: float) -> Dict:
        """Gera parâmetros de sequência usando teoria do caos avançada"""
        # Gera número base de pontos
        base_points = int(distance_km * 2)  # Base: 2 pontos por km
        
        # Gera entropia inicial
        entropy_factors = self.generate_transcendental_entropy(seed_hash)
        chaos_components = self.apply_kam_theorem(entropy_factors)
        
        # Determina número final de pontos
        chaos_factor = sum(chaos_components) / len(chaos_components)
        num_points = max(5, min(50, int(base_points * (1 + chaos_factor))))
        
        # Gera intervalos criptografados
        intervals = []
        for i in range(num_points - 1):
            # Usa diferentes partes do hash para cada intervalo
            interval_seed = hashlib.sha512(
                seed_hash + i.to_bytes(4, 'big')
            ).digest()
            
            interval_crypto = self.generate_interval_crypto(interval_seed, i)
            intervals.append(interval_crypto)
        
        return {
            "num_points": num_points,
            "intervals": intervals,
            "chaos_sequence": chaos_components
        }

    def validate_interval_crypto(self, interval: IntervalCrypto, sequence_number: int, base_entropy: bytes) -> bool:
        """Valida a prova criptográfica de um intervalo"""
        # Recria a prova criptográfica
        proof_data = f"{base_entropy.hex()}:{sequence_number}:{interval.raw_interval:.6f}"
        for ef, cc in zip(interval.entropy_factors, interval.chaos_components):
            proof_data += f":{ef:.6f}:{cc:.6f}"
        
        # Aplica as mesmas transformações
        current_hash = proof_data.encode()
        for i in range(5):
            transformed = bytes(b ^ int((b * self.PHI + i) % 256) for b in current_hash)
            current_hash = hashlib.sha512(transformed).digest()
        
        return current_hash.hex() == interval.validation_hash

    def generate_genesis_hash(self, point_a: GPSPoint, point_b: GPSPoint, nts_entropy: bytes = None) -> str:
        """Generate initial hash that will determine all route parameters"""
        current_time = time.time_ns()
        salt = self.system_random.randbytes(64)
        
        # Multiple layers of entropy
        base_string = (
            f"{current_time}:{point_a.latitude}:{point_a.longitude}:"
            f"{point_b.latitude}:{point_b.longitude}:{salt.hex()}"
        )
        
        if nts_entropy:
            base_string += f":{nts_entropy.hex()}"
        
        # Apply multiple SHA-512 layers with non-linear operations
        hash_layers = []
        current_hash = base_string.encode()
        
        for i in range(5):
            current_hash = hashlib.sha512(current_hash).digest()
            # Non-linear transformation
            transformed = bytes(b ^ (b * 13 + i * 7) % 256 for b in current_hash)
            hash_layers.append(transformed)
        
        final_hash = hashlib.sha512(b''.join(hash_layers)).hexdigest()
        return final_hash

    def calculate_route_metrics(self, point_a: GPSPoint, point_b: GPSPoint, velocidade_kmh: float = None) -> RouteMetrics:
        """Calculate route metrics with mathematical security"""
        if velocidade_kmh is None:
            velocidade_kmh = self.DEFAULT_SPEED

        # Gera salt único para estas métricas
        security_salt = self.system_random.randbytes(32)
        
        try:
            # Cálculos base com proteção contra timing attacks
            lat1, lon1 = math.radians(point_a.latitude), math.radians(point_a.longitude)
            lat2, lon2 = math.radians(point_b.latitude), math.radians(point_b.longitude)

            # Adiciona operações dummy para mascarar timing
            dummy1 = math.sin(lat1 * self.PHI)
            dummy2 = math.cos(lon1 * self.EULER)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            # Haversine com proteção
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

            # Mais operações dummy
            dummy3 = math.tan(c * self.APERY)
            dummy4 = math.cos(a * self.GAUSS)

            # Base distance in kilometers with controlled noise
            D = self.R * c
            noise = 1 + (self.system_random.random() * 0.06 - 0.03)
            D *= noise

            # Non-linear transformations
            D_extra = D * (0.5 + math.sin(D * self.PHI) * 0.1)  # 50% ±10%
            D_total = D + D_extra
            
            # Time calculations with safety margin (2x) and non-linear adjustment
            base_time = (D / velocidade_kmh) * 60
            time_factor = 2 + math.sin(D * self.EULER) * 0.2  # 2x ±10%
            T_reta = base_time * time_factor
            
            extra_time = (D_extra / (velocidade_kmh * 0.5)) * 60
            extra_factor = 2 + math.cos(D_extra * self.PHI) * 0.2  # 2x ±10%
            T_extra = extra_time * extra_factor
            
            T_total = T_reta + T_extra

            # Cria objeto com valores brutos
            raw_metrics = RouteMetricsRaw(
                dist_reta_km=D,
                dist_extra_km=D_extra,
                dist_total_km=D_total,
                dist_total_metros=D_total * 1000,
                tempo_reta_min=T_reta,
                tempo_extra_min=T_extra,
                tempo_total_min=T_total
            )

            # Criptografa cada valor individualmente
            encrypted_values = {}
            for field_name, value in raw_metrics.__dict__.items():
                # Primeira camada: Combina com salt e números transcendentais
                value_data = f"{value:.20f}:{security_salt.hex()}"
                
                # Segunda camada: Transformação não-linear
                value_transform = bytes([
                    int((b * self.PHI + ord(str(value)[0]) * self.PI + 
                         self.EULER * i + self.APERY) % 256)
                    for i, b in enumerate(value_data.encode())
                ])
                
                # Terceira camada: XOR com chave do sistema
                value_keyed = bytes([
                    a ^ b ^ ord(field_name[i % len(field_name)]) 
                    for i, (a, b) in enumerate(zip(
                        value_transform, 
                        self.SYSTEM_KEY * (len(value_transform) // len(self.SYSTEM_KEY) + 1)
                    ))
                ])
                
                # Quarta camada: Multiple rounds of SHA-512
                current_hash = value_keyed
                for i in range(5):
                    current_hash = hashlib.sha512(current_hash + security_salt).digest()
                
                encrypted_values[f"encrypted_{field_name}"] = current_hash.hex()

            # Cria objeto RouteMetrics e define valores brutos
            metrics = RouteMetrics(
                encrypted_dist_reta=encrypted_values['encrypted_dist_reta_km'],
                encrypted_dist_extra=encrypted_values['encrypted_dist_extra_km'],
                encrypted_dist_total=encrypted_values['encrypted_dist_total_km'],
                encrypted_dist_metros=encrypted_values['encrypted_dist_total_metros'],
                encrypted_tempo_reta=encrypted_values['encrypted_tempo_reta_min'],
                encrypted_tempo_extra=encrypted_values['encrypted_tempo_extra_min'],
                encrypted_tempo_total=encrypted_values['encrypted_tempo_total_min'],
                security_salt=security_salt
            )
            metrics.raw = raw_metrics
            return metrics

        except Exception as e:
            print(f"Erro no cálculo de métricas: {e}")
            # Valores seguros em caso de erro
            raw_metrics = RouteMetricsRaw(
                dist_reta_km=1.0,
                dist_extra_km=0.5,
                dist_total_km=1.5,
                dist_total_metros=1500.0,
                tempo_reta_min=3.0,
                tempo_extra_min=1.5,
                tempo_total_min=4.5
            )
            # Criptografa com salt de erro
            error_salt = self.system_random.randbytes(32)
            error_hash = hashlib.sha512(error_salt).hexdigest()
            metrics = RouteMetrics(
                encrypted_dist_reta=error_hash,
                encrypted_dist_extra=error_hash,
                encrypted_dist_total=error_hash,
                encrypted_dist_metros=error_hash,
                encrypted_tempo_reta=error_hash,
                encrypted_tempo_extra=error_hash,
                encrypted_tempo_total=error_hash,
                security_salt=error_salt
            )
            metrics.raw = raw_metrics
            return metrics

    def haversine_distance(self, point1: GPSPoint, point2: GPSPoint) -> float:
        """Calculate distance between two points using Haversine formula with noise"""
        metrics = self.calculate_route_metrics(point1, point2)
        return metrics.raw.dist_total_km

    def fibonacci_expansion(self, distance: float, genesis_hash: str) -> List[int]:
        """Generate Fibonacci sequence with random jumps based on hash"""
        sequence = [1, 1]
        hash_segments = [int(genesis_hash[i:i+8], 16) for i in range(0, len(genesis_hash), 8)]
        
        target_length = int(distance * 2) + 10  # Base number of elements
        
        while len(sequence) < target_length:
            # Use hash segments to create random jumps
            jump = (hash_segments[len(sequence) % len(hash_segments)] % 5) + 1
            for _ in range(jump):
                sequence.append(sequence[-1] + sequence[-2])
        
        return sequence

    def generate_random_point(self, center_lat: float, center_lon: float, radius_km: float) -> GPSPoint:
        """Generate random point within specified radius"""
        # Convert radius from km to degrees (approximate)
        radius_deg = radius_km / 111.32
        
        while True:
            # Generate random point
            dx = self.system_random.uniform(-radius_deg, radius_deg)
            dy = self.system_random.uniform(-radius_deg, radius_deg)
            
            new_lat = center_lat + dy
            new_lon = center_lon + dx
            
            # Validate point is within radius
            if self.haversine_distance(
                GPSPoint(center_lat, center_lon, 0),
                GPSPoint(new_lat, new_lon, 0)
            ) <= radius_km:
                return GPSPoint(new_lat, new_lon, int(time.time()))

    def generate_validation_rule(self, block_hash: str) -> str:
        """Generate random validation rule based on block hash"""
        rules = [
            "time_consistency",
            "speed_limit",
            "point_proximity",
            "acceleration_check",
            "path_smoothness"
        ]
        rule_index = int(block_hash[:8], 16) % len(rules)
        return rules[rule_index]

    def derive_nts_variables(self, nts_numeric: str, distance_km: float) -> NTSVariables:
        """Deriva variáveis do NTS para afetar diferentes aspectos da geração"""
        try:
            # Divide o hash SHA-256 em segmentos de 8 caracteres
            segments = [nts_numeric[i:i+8] for i in range(0, len(nts_numeric), 8)]
            
            # Converte segmentos para números entre 0 e 1
            base_numbers = []
            for seg in segments:
                # Converte segmento hex para int e normaliza
                value = int(seg, 16) / (16 ** 8)  # Normaliza para [0,1]
                base_numbers.append(value)
            
            # Deriva fator de tempo (afeta intervalos)
            time_base = sum(base_numbers) / len(base_numbers)
            time_factor = (math.sin(time_base * self.PI) + 1) / 2  # Entre 0 e 1
            
            # Deriva fator de distância (afeta distribuição de pontos)
            dist_base = base_numbers[0] if base_numbers else 0.5
            distance_factor = (math.cos(dist_base * self.PHI) + 1) / 2
            
            # Modificador de intervalos (afeta tempo entre pontos)
            interval_base = base_numbers[1] if len(base_numbers) > 1 else 0.5
            interval_modifier = 0.5 + (math.tan(interval_base * self.EULER) % 0.5)
            
            # Espalhamento dos pontos (afeta desvio da rota)
            spread_base = base_numbers[2] if len(base_numbers) > 2 else 0.5
            point_spread = 0.1 + (math.sin(spread_base * self.GAUSS) * 0.1)
            
            # Limiar de validação (afeta tolerância)
            valid_base = base_numbers[3] if len(base_numbers) > 3 else 0.5
            validation_threshold = 0.8 + (math.cos(valid_base * self.APERY) * 0.2)
            
            # Boost de entropia por bloco
            entropy_boost = []
            for i, num in enumerate(base_numbers):
                # Usa a distância para influenciar o boost
                boost = math.sin((num * self.PHI * (i + 1) + distance_km * self.PI))
                entropy_boost.append((boost + 1) / 2)  # Normaliza entre 0 e 1
            
            # Cria instância criptografada
            return NTSVariables(
                base_numeric=nts_numeric,
                time_factor=time_factor,
                distance_factor=distance_factor,
                interval_modifier=interval_modifier,
                point_spread=point_spread,
                validation_threshold=validation_threshold,
                entropy_boost=entropy_boost,
                system_key=self.SYSTEM_KEY
            )
            
        except Exception as e:
            # Em caso de erro, retorna valores seguros criptografados
            return NTSVariables(
                base_numeric=nts_numeric,
                time_factor=0.5,
                distance_factor=0.5,
                interval_modifier=0.5,
                point_spread=0.1,
                validation_threshold=0.8,
                entropy_boost=[0.5] * 5,
                system_key=self.SYSTEM_KEY
            )

    def create_delivery_contract(self, center_lat: float = -23.5505, center_lon: float = -46.6333):
        """Create new delivery contract with random points within São Paulo area"""
        # Generate random points within 5km radius
        point_a = self.generate_random_point(center_lat, center_lon, 5)
        point_b = self.generate_random_point(center_lat, center_lon, 5)
        
        # Generate genesis hash
        genesis_hash = self.generate_genesis_hash(point_a, point_b)
        
        # Calculate distance and create Fibonacci expansion
        distance = self.haversine_distance(point_a, point_b)
        fib_sequence = self.fibonacci_expansion(distance, genesis_hash)
        
        return {
            'point_a': point_a,
            'point_b': point_b,
            'genesis_hash': genesis_hash,
            'distance': distance,
            'fibonacci_sequence': fib_sequence
        }

    def validate_delivery(self, contract: Dict, blocks: List[Block]) -> bool:
        """Validate if delivery meets all requirements with error handling"""
        try:
            if not blocks:
                return False
            
            # Obtém variáveis NTS do contrato
            nts_vars = contract.get('nts_variables')
            
            # Primeiro valida a blockchain como um todo
            if not self.validate_blockchain(blocks):
                print("Erro: Blockchain inválida")
                return False
            
            # Depois valida cada bloco individualmente
            invalid_blocks = 0
            total_blocks = len(blocks)
            
            for block in blocks:
                try:
                    # Verifica se o bloco é válido
                    if not block.is_valid:
                        invalid_blocks += 1
                        continue
                    
                    # Verifica se os timestamps são consistentes
                    if not all(p.timestamp >= SECURITY.timestamp_base for p in block.points):
                        print(f"Erro: Timestamps inválidos no bloco {block.sequence_number}")
                        invalid_blocks += 1
                        continue
                    
                    # Verifica se os intervalos são válidos
                    if len(block.interval_rules) != len(block.points) - 1:
                        print(f"Erro: Número inválido de intervalos no bloco {block.sequence_number}")
                        invalid_blocks += 1
                        continue
                    
                    # Verifica se as métricas são válidas
                    if not block.metrics or not block.encrypted_metrics:
                        print(f"Erro: Métricas ausentes no bloco {block.sequence_number}")
                        invalid_blocks += 1
                        continue
                    
                    # Verifica assinatura digital
                    if not block.verify_signature():
                        print(f"Erro: Assinatura inválida no bloco {block.sequence_number}")
                        invalid_blocks += 1
                        continue
                    
                    # Valida o bloco com as variáveis NTS
                    if not self.validate_block(block, block.points, nts_vars):
                        print(f"Erro: Validação falhou no bloco {block.sequence_number}")
                        invalid_blocks += 1
                        continue
                    
                except Exception as e:
                    print(f"Aviso: Erro na validação do bloco {block.sequence_number}: {e}")
                    invalid_blocks += 1
            
            # Permite até 25% de blocos inválidos
            max_invalid = min(5, total_blocks // 4)
            if invalid_blocks > max_invalid:
                print(f"Erro: Muitos blocos inválidos ({invalid_blocks} de {total_blocks})")
                return False
            
            return True
            
        except Exception as e:
            print(f"Erro na validação da entrega: {e}")
            return False

    def generate_chaos_seed(self, point_a: GPSPoint, point_b: GPSPoint, timestamp: int) -> bytes:
        """Gera uma semente caótica usando múltiplas fontes de entropia"""
        # Combina coordenadas com transformações não-lineares
        lat_transform = math.tan(point_a.latitude * self.PI / 180) * math.cos(point_b.latitude * self.PI / 180)
        lon_transform = math.sin(point_a.longitude * self.PI / 180) * math.tan(point_b.longitude * self.PI / 180)
        
        # Aplica número áureo e e para criar mais caos
        phi_component = (lat_transform * self.PHI) % 1
        euler_component = (lon_transform * self.EULER) % 1
        
        # Mistura com timestamp atual em nanosegundos
        time_component = timestamp / (10**9)
        
        # Cria string com alta entropia
        entropy_str = f"{lat_transform:.20f}:{lon_transform:.20f}:{phi_component:.20f}:{euler_component:.20f}:{time_component:.20f}"
        
        # Aplica SHA-512 múltiplas vezes com transformações não-lineares
        current_hash = entropy_str.encode()
        for i in range(5):
            # Aplica transformação não-linear antes de cada hash
            transformed = bytes(b ^ (int((b * self.PHI) % 256) ^ int((b * self.EULER) % 256)) for b in current_hash)
            current_hash = hashlib.sha512(transformed).digest()
            
        return current_hash

    def generate_block_parameters(self, genesis_hash: str, block_number: int) -> Dict:
        """Generate unique parameters for each block based on genesis hash and chaos theory"""
        # Use block number to select different segments of genesis hash
        segment_size = len(genesis_hash) // 4
        base_segment = genesis_hash[block_number % 4 * segment_size:(block_number % 4 + 1) * segment_size]
        
        # Convert hash segment to bytes for chaos seed
        segment_bytes = bytes.fromhex(base_segment)
        
        # Generate chaos seed
        chaos_seed = self.generate_chaos_seed(
            GPSPoint(float(segment_bytes[0]), float(segment_bytes[1]), int(time.time())),
            GPSPoint(float(segment_bytes[2]), float(segment_bytes[3]), int(time.time())),
            int(time.time_ns())
        )
        
        # Generate sequence parameters using chaos theory
        sequence_params = self.generate_sequence_parameters(chaos_seed, float(int.from_bytes(segment_bytes[:8], 'big') % 100))
        
        return {
            'num_points': sequence_params['num_points'],
            'intervals': sequence_params['intervals'],
            'validation_rule': self.generate_validation_rule(base_segment),
            'chaos_sequence': sequence_params['chaos_sequence']
        }

    def generate_block_points(self, start_point: GPSPoint, end_point: GPSPoint, num_points: int, nts_vars: Optional[NTSVariables] = None) -> List[GPSPoint]:
        """Generate intermediate points using chaos theory and non-linear transformations"""
        points = [start_point]
        
        # Gera semente caótica para os pontos
        chaos_seed = self.generate_chaos_seed(start_point, end_point, int(time.time_ns()))
        sequence_params = self.generate_sequence_parameters(chaos_seed, 
                                                         self.haversine_distance(start_point, end_point))
        
        chaos_sequence = sequence_params['chaos_sequence']
        
        # Obtém parâmetros NTS de forma segura
        point_spread = nts_vars.get_secure_value('point_spread', 0.1) if nts_vars else 0.1
        
        for i in range(1, num_points - 1):
            progress = i / (num_points - 1)
            
            # Usa sequência caótica para desvio
            chaos_value = chaos_sequence[i % len(chaos_sequence)]
            
            # Interpolação não-linear usando múltiplos fatores
            phi_factor = math.sin(progress * self.PI * chaos_value)
            euler_factor = math.cos(progress * self.PI * (1 - chaos_value))
            
            # Calcula posição base
            base_lat = start_point.latitude + (end_point.latitude - start_point.latitude) * progress
            base_lon = start_point.longitude + (end_point.longitude - start_point.longitude) * progress
            
            # Aplica desvio não-linear usando point_spread do NTS
            max_deviation = 0.0002 * point_spread  # Ajusta desvio baseado no NTS
            lat_deviation = max_deviation * phi_factor * euler_factor
            lon_deviation = max_deviation * euler_factor * phi_factor
            
            new_lat = base_lat + lat_deviation
            new_lon = base_lon + lon_deviation
            
            points.append(GPSPoint(new_lat, new_lon, int(time.time())))
            
        points.append(end_point)
        return points

    def encrypt_sensitive_data(self, data: any, salt: bytes = None) -> str:
        """Criptografa dados sensíveis com múltiplas camadas"""
        try:
            # Gera salt único se não fornecido
            if salt is None:
                salt = self.system_random.randbytes(32)

            # Converte dados para string JSON
            data_str = str(data)
            
            # Primeira camada: Combina com salt
            combined = f"{data_str}:{salt.hex()}"
            
            # Segunda camada: Aplica chave do sistema
            keyed_data = bytes([a ^ b for a, b in zip(combined.encode(), 
                              self.SYSTEM_KEY * (len(combined) // len(self.SYSTEM_KEY) + 1))])
            
            # Terceira camada: Múltiplos rounds de SHA-512 com transformações não-lineares
            current_hash = keyed_data
            for i in range(10):
                # Transformação não-linear usando números transcendentais
                transformed = bytes([
                    int((b * self.PHI + i * self.PI) % 256) ^ 
                    int((b * self.EULER + i * self.FEIGENBAUM) % 256)
                    for b in current_hash
                ])
                current_hash = hashlib.sha512(transformed).digest()
            
            # Quarta camada: Combina com mais entropia do sistema
            final_hash = hashlib.sha512(current_hash + self.SYSTEM_KEY + salt).hexdigest()
            
            return final_hash
            
        except Exception as e:
            print(f"Erro na criptografia: {e}")
            # Retorna hash de erro que não pode ser decriptografado
            return hashlib.sha512(str(time.time_ns()).encode()).hexdigest()

    def create_encrypted_metrics(self, metrics: RouteMetrics, intervals: List[IntervalCrypto], 
                               num_points: int) -> EncryptedMetrics:
        """Cria métricas criptografadas com segurança matemática"""
        try:
            # Gera salt único para este conjunto de métricas
            security_salt = secrets.token_bytes(32)
            
            # Cria instância de EncryptedMetrics
            encrypted_metrics = EncryptedMetrics(
                encrypted_time="",
                encrypted_intervals="",
                encrypted_points_count="",
                encrypted_distance="",
                dist_hash="",
                proof_hash="",
                _raw_metrics=metrics,
                security_salt=security_salt
            )
            
            # Criptografa tempo total (SHA-512)
            time_data = f"{metrics.encrypted_tempo_total}:{security_salt.hex()}"
            encrypted_metrics.encrypted_time = encrypted_metrics.encrypt_route_data(time_data)
            
            # Criptografa intervalos (SHA-512)
            intervals_data = f"{[i.encrypted_value for i in intervals]}:{security_salt.hex()}"
            encrypted_metrics.encrypted_intervals = encrypted_metrics.encrypt_route_data(intervals_data)
            
            # Criptografa número de pontos (SHA-512)
            points_data = f"{num_points}:{security_salt.hex()}"
            encrypted_metrics.encrypted_points_count = encrypted_metrics.encrypt_route_data(points_data)
            
            # Criptografa distância total (SHA-512)
            distance_data = f"{metrics.encrypted_dist_total}:{security_salt.hex()}"
            encrypted_metrics.encrypted_distance = encrypted_metrics.encrypt_route_data(distance_data)
            
            # Gera hash da distância (SHA-512)
            dist_data = f"{encrypted_metrics.encrypted_distance}:{security_salt.hex()}"
            encrypted_metrics.dist_hash = encrypted_metrics.encrypt_route_data(dist_data)
            
            # Gera hash de prova com todas as camadas (SHA-512)
            proof_data = (
                f"{encrypted_metrics.encrypted_time}:"
                f"{encrypted_metrics.encrypted_intervals}:"
                f"{encrypted_metrics.encrypted_points_count}:"
                f"{encrypted_metrics.encrypted_distance}:"
                f"{encrypted_metrics.dist_hash}:"
                f"{security_salt.hex()}"
            )
            encrypted_metrics.proof_hash = encrypted_metrics.encrypt_route_data(proof_data)
            
            return encrypted_metrics
            
        except Exception as e:
            print(f"Erro na criação de métricas criptografadas: {e}")
            # Retorna métricas de erro com salt único
            error_salt = secrets.token_bytes(32)
            error_metrics = EncryptedMetrics(
                encrypted_time=hashlib.sha512(error_salt).hexdigest(),
                encrypted_intervals=hashlib.sha512(error_salt).hexdigest(),
                encrypted_points_count=hashlib.sha512(error_salt).hexdigest(),
                encrypted_distance=hashlib.sha512(error_salt).hexdigest(),
                dist_hash=hashlib.sha512(error_salt).hexdigest(),
                proof_hash=hashlib.sha512(error_salt).hexdigest(),
                _raw_metrics=metrics,
                security_salt=error_salt
            )
            return error_metrics

    def create_blocks(self, contract: Dict) -> List[Block]:
        """Create blocks for the delivery route with encrypted metrics"""
        try:
            genesis_hash = contract['genesis_hash']
            point_a = contract['point_a']
            point_b = contract['point_b']
            nts_vars = contract.get('nts_variables')
            
            try:
                route_metrics = self.calculate_route_metrics(point_a, point_b)
                total_distance = route_metrics.raw.dist_total_km
            except Exception as e:
                print(f"Erro no cálculo de métricas da rota: {e}")
                raise
            
            try:
                # Usa sequência Fibonacci para determinar número de blocos
                fib_sequence = contract.get('fibonacci_sequence', [1, 1, 2, 3, 5, 8, 13, 21])
                num_blocks = len([x for x in fib_sequence if x < total_distance * 1000]) // 2
                num_blocks = max(5, min(20, num_blocks))
            except Exception as e:
                print(f"Aviso: Erro no cálculo do número de blocos: {e}")
                num_blocks = max(5, min(20, int(total_distance * 2)))

            # Gera distribuição não-linear das distâncias usando entropia
            try:
                # Usa variáveis NTS para influenciar distribuição de forma segura
                distance_factor = nts_vars.get_secure_value('distance_factor', 0.5) if nts_vars else 0.5
                entropy_boost = nts_vars.get_secure_value('entropy_boost', [0.5] * 5) if nts_vars else [0.5] * 5
                
                # Gera números aleatórios com distribuição não-linear
                raw_distances = []
                for i in range(num_blocks):
                    # Usa múltiplos fatores para gerar variação
                    block_entropy = entropy_boost[i % len(entropy_boost)]
                    phase = (i / num_blocks) * 2 * self.PI
                    
                    # Combina funções trigonométricas para criar padrão não-linear
                    variation = (
                        math.sin(phase) * block_entropy +
                        math.cos(phase * self.PHI) * (1 - block_entropy) +
                        math.sin(phase * self.EULER) * distance_factor
                    )
                    
                    # Normaliza e adiciona ruído controlado
                    distance = (variation + 1) / 2  # Normaliza para [0,1]
                    noise = secrets.SystemRandom().random() * 0.2 - 0.1  # ±10% ruído
                    distance = max(0.1, min(0.9, distance + noise))  # Limita entre 0.1 e 0.9
                    
                    raw_distances.append(distance)
                
                # Normaliza para somar total_distance
                sum_distances = sum(raw_distances)
                block_distances = [d * total_distance / sum_distances for d in raw_distances]
                
            except Exception as e:
                print(f"Aviso: Erro na distribuição de distâncias: {e}")
                # Fallback para distribuição com variação simples
                block_distances = []
                base_distance = total_distance / num_blocks
                for _ in range(num_blocks):
                    variation = secrets.SystemRandom().random() * 0.4 - 0.2  # ±20%
                    block_distances.append(base_distance * (1 + variation))

            blocks = []
            current_point = point_a
            accumulated_distance = 0
            previous_hash = None

            for i in range(num_blocks):
                try:
                    # Calcula progresso não-linear para posição do ponto
                    block_distance = block_distances[i]
                    accumulated_distance += block_distance
                    progress = accumulated_distance / total_distance
                    
                    # Adiciona variação na posição do ponto
                    base_lat = point_a.latitude + (point_b.latitude - point_a.latitude) * progress
                    base_lon = point_a.longitude + (point_b.longitude - point_a.longitude) * progress
                    
                    # Aplica desvio baseado em entropia
                    max_deviation = 0.0002 * (1 + math.sin(progress * self.PI))
                    lat_deviation = max_deviation * (secrets.SystemRandom().random() * 2 - 1)
                    lon_deviation = max_deviation * (secrets.SystemRandom().random() * 2 - 1)
                    
                    block_end = GPSPoint(
                        base_lat + lat_deviation,
                        base_lon + lon_deviation,
                        SECURITY.timestamp_base + i * 300  # 5 minutos entre pontos
                    )
                    
                    try:
                        params = self.generate_block_parameters(genesis_hash, i)
                    except Exception as e:
                        print(f"Aviso: Erro na geração de parâmetros do bloco {i}: {e}")
                        params = {
                            'num_points': 5,
                            'intervals': [self.generate_interval_crypto(hashlib.sha512(str(i).encode()).digest(), i)],
                            'validation_rule': 'time_consistency',
                            'chaos_sequence': [0.5, 0.5, 0.5]
                        }

                    try:
                        block_metrics = self.calculate_route_metrics(current_point, block_end)
                    except Exception as e:
                        print(f"Aviso: Erro no cálculo de métricas do bloco {i}: {e}")
                        raw_metrics = RouteMetricsRaw(
                            dist_reta_km=1.0,
                            dist_extra_km=0.5,
                            dist_total_km=1.5,
                            dist_total_metros=1500.0,
                            tempo_reta_min=3.0,
                            tempo_extra_min=1.5,
                            tempo_total_min=4.5
                        )
                        block_metrics = RouteMetrics(
                            encrypted_dist_reta=hashlib.sha512(str(i).encode()).hexdigest(),
                            encrypted_dist_extra=hashlib.sha512(str(i).encode()).hexdigest(),
                            encrypted_dist_total=hashlib.sha512(str(i).encode()).hexdigest(),
                            encrypted_dist_metros=hashlib.sha512(str(i).encode()).hexdigest(),
                            encrypted_tempo_reta=hashlib.sha512(str(i).encode()).hexdigest(),
                            encrypted_tempo_extra=hashlib.sha512(str(i).encode()).hexdigest(),
                            encrypted_tempo_total=hashlib.sha512(str(i).encode()).hexdigest(),
                            security_salt=secrets.token_bytes(32)
                        )
                        block_metrics.raw = raw_metrics

                    try:
                        points = self.generate_block_points(current_point, block_end, params['num_points'], nts_vars)
                        # Atualiza timestamps dos pontos
                        for j, point in enumerate(points):
                            point.timestamp = SECURITY.timestamp_base + i * 300 + j * 60  # 1 minuto entre pontos
                    except Exception as e:
                        print(f"Aviso: Erro na geração de pontos do bloco {i}: {e}")
                        points = []
                        for j in range(params['num_points']):
                            p = j / (params['num_points'] - 1)
                            lat = current_point.latitude + (block_end.latitude - current_point.latitude) * p
                            lon = current_point.longitude + (block_end.longitude - current_point.longitude) * p
                            points.append(GPSPoint(lat, lon, SECURITY.timestamp_base + i * 300 + j * 60))

                    encrypted_metrics = self.create_encrypted_metrics(
                        block_metrics, 
                        params['intervals'],
                        len(points)
                    )

                    block = Block(
                        sequence_number=i,
                        points=points,
                        interval_rules=params['intervals'],
                        validation_rule=params['validation_rule'],
                        block_hash="",  # Será calculado no __post_init__
                        metrics=block_metrics,
                        encrypted_metrics=encrypted_metrics,
                        previous_block_hash=previous_hash
                    )

                    # Atualiza hash anterior para próximo bloco
                    previous_hash = block.block_hash
                    blocks.append(block)
                    current_point = block_end

                except Exception as e:
                    print(f"Erro na geração do bloco {i}: {e}")
                    # Cria bloco com valores seguros
                    raw_metrics = RouteMetricsRaw(
                        dist_reta_km=1.0,
                        dist_extra_km=0.5,
                        dist_total_km=1.5,
                        dist_total_metros=1500.0,
                        tempo_reta_min=3.0,
                        tempo_extra_min=1.5,
                        tempo_total_min=4.5
                    )
                    safe_metrics = RouteMetrics(
                        encrypted_dist_reta=hashlib.sha512(str(i).encode()).hexdigest(),
                        encrypted_dist_extra=hashlib.sha512(str(i).encode()).hexdigest(),
                        encrypted_dist_total=hashlib.sha512(str(i).encode()).hexdigest(),
                        encrypted_dist_metros=hashlib.sha512(str(i).encode()).hexdigest(),
                        encrypted_tempo_reta=hashlib.sha512(str(i).encode()).hexdigest(),
                        encrypted_tempo_extra=hashlib.sha512(str(i).encode()).hexdigest(),
                        encrypted_tempo_total=hashlib.sha512(str(i).encode()).hexdigest(),
                        security_salt=secrets.token_bytes(32)
                    )
                    safe_metrics.raw = raw_metrics
                    safe_block = Block(
                        sequence_number=i,
                        points=[current_point, block_end],
                        interval_rules=[self.generate_interval_crypto(hashlib.sha512(str(i).encode()).digest(), i)],
                        validation_rule='time_consistency',
                        block_hash="",  # Será calculado no __post_init__
                        metrics=safe_metrics,
                        encrypted_metrics=self.create_encrypted_metrics(safe_metrics, [], 2),
                        previous_block_hash=previous_hash
                    )
                    previous_hash = safe_block.block_hash
                    blocks.append(safe_block)
                    current_point = block_end

            if not blocks:
                raise ValueError("Nenhum bloco foi gerado com sucesso")

            return blocks

        except Exception as e:
            raise RuntimeError(f"Erro fatal na geração de blocos: {e}")

    def validate_blockchain(self, blocks: List[Block]) -> bool:
        """Valida toda a cadeia de blocos"""
        try:
            if not blocks:
                return False
                
            previous_hash = None
            
            for block in blocks:
                try:
                    # Verifica hash do bloco anterior
                    if block.previous_block_hash != previous_hash:
                        return False
                    
                    # Verifica hash do bloco atual
                    if not block.verify_hash():
                        return False
                    
                    # Verifica assinatura digital
                    if not block.verify_signature():
                        return False
                    
                    # Atualiza hash para próxima iteração
                    previous_hash = block.block_hash
                    
                except Exception as e:
                    print(f"Erro na validação do bloco {block.sequence_number}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Erro na validação da blockchain: {e}")
            return False

    def validate_block(self, block: Block, actual_points: List[GPSPoint], nts_vars: Optional[NTSVariables] = None) -> bool:
        """Validate a block against actual GPS points"""
        if len(actual_points) != len(block.points):
            return False
            
        # Validate timestamps against interval rules
        for i in range(len(actual_points) - 1):
            actual_interval = actual_points[i+1].timestamp - actual_points[i].timestamp
            expected_interval = block.interval_rules[i].raw_interval
            
            # Allow 10% deviation from expected interval
            if abs(actual_interval - expected_interval) / expected_interval > 0.1:
                return False
        
        # Validate points based on block's validation rule
        if block.validation_rule == "time_consistency":
            return self._validate_time_consistency(actual_points)
        elif block.validation_rule == "speed_limit":
            return self._validate_speed_limit(actual_points)
        elif block.validation_rule == "point_proximity":
            return self._validate_point_proximity(actual_points, block.points)
        elif block.validation_rule == "acceleration_check":
            return self._validate_acceleration(actual_points)
        elif block.validation_rule == "path_smoothness":
            return self._validate_path_smoothness(actual_points)
            
        return False

    def _validate_time_consistency(self, points: List[GPSPoint]) -> bool:
        """Validate that timestamps are strictly increasing with error handling"""
        try:
            if not points or len(points) < 2:
                return True
                
            for i in range(len(points) - 1):
                try:
                    if points[i+1].timestamp <= points[i].timestamp:
                        return False
                except Exception as e:
                    print(f"Aviso: Erro na validação de timestamp do ponto {i}: {e}")
                    return False
            return True
            
        except Exception as e:
            print(f"Erro na validação de consistência temporal: {e}")
            return False

    def _validate_speed_limit(self, points: List[GPSPoint]) -> bool:
        """Validate that speed between points is reasonable with error handling"""
        try:
            if not points or len(points) < 2:
                return True
                
            for i in range(len(points) - 1):
                try:
                    metrics = self.calculate_route_metrics(points[i], points[i+1])
                    time_diff = (points[i+1].timestamp - points[i].timestamp) / 3600  # Convert to hours
                    
                    if time_diff <= 0:
                        return False
                        
                    speed = metrics.raw.dist_total_km / time_diff
                    
                    if speed > 120:  # Maximum 120 km/h
                        return False
                except Exception as e:
                    print(f"Aviso: Erro no cálculo de velocidade entre pontos {i} e {i+1}: {e}")
                    return False
            return True
            
        except Exception as e:
            print(f"Erro na validação de limite de velocidade: {e}")
            return False

    def _validate_point_proximity(self, actual_points: List[GPSPoint], expected_points: List[GPSPoint]) -> bool:
        """Validate that actual points are close to expected points with error handling"""
        try:
            if len(actual_points) != len(expected_points):
                return False
                
            MAX_DEVIATION = 0.1  # km
            
            for i, (actual, expected) in enumerate(zip(actual_points, expected_points)):
                try:
                    if self.haversine_distance(actual, expected) > MAX_DEVIATION:
                        return False
                except Exception as e:
                    print(f"Aviso: Erro no cálculo de distância do ponto {i}: {e}")
                    return False
            return True
            
        except Exception as e:
            print(f"Erro na validação de proximidade de pontos: {e}")
            return False

    def _validate_acceleration(self, points: List[GPSPoint]) -> bool:
        """Validate that acceleration between points is physically possible with error handling"""
        try:
            if not points or len(points) < 3:
                return True
                
            MAX_ACCELERATION = 5  # m/s²
            speeds = []
            
            # Calcula velocidades
            for i in range(len(points) - 1):
                try:
                    distance = self.haversine_distance(points[i], points[i+1]) * 1000  # Convert to meters
                    time = points[i+1].timestamp - points[i].timestamp
                    
                    if time <= 0:
                        return False
                        
                    speeds.append(distance / time)
                except Exception as e:
                    print(f"Aviso: Erro no cálculo de velocidade do segmento {i}: {e}")
                    return False
            
            # Valida acelerações
            for i in range(len(speeds) - 1):
                try:
                    time_diff = points[i+2].timestamp - points[i+1].timestamp
                    
                    if time_diff <= 0:
                        return False
                        
                    acceleration = abs(speeds[i+1] - speeds[i]) / time_diff
                    
                    if acceleration > MAX_ACCELERATION:
                        return False
                except Exception as e:
                    print(f"Aviso: Erro no cálculo de aceleração do segmento {i}: {e}")
                    return False
                    
            return True
            
        except Exception as e:
            print(f"Erro na validação de aceleração: {e}")
            return False

    def _validate_path_smoothness(self, points: List[GPSPoint]) -> bool:
        """Validate that the path doesn't have sharp turns with error handling"""
        try:
            if len(points) < 3:
                return True
                
            for i in range(len(points) - 2):
                try:
                    # Calculate vectors between consecutive points
                    v1 = (points[i+1].latitude - points[i].latitude, 
                          points[i+1].longitude - points[i].longitude)
                    v2 = (points[i+2].latitude - points[i+1].latitude, 
                          points[i+2].longitude - points[i+1].longitude)
                    
                    # Calculate angle between vectors
                    dot_product = v1[0]*v2[0] + v1[1]*v2[1]
                    v1_mag = math.sqrt(v1[0]**2 + v1[1]**2)
                    v2_mag = math.sqrt(v2[0]**2 + v2[1]**2)
                    
                    if v1_mag == 0 or v2_mag == 0:
                        return False
                        
                    cos_angle = dot_product / (v1_mag * v2_mag)
                    cos_angle = max(-1, min(1, cos_angle))  # Ensure value is in [-1, 1]
                    angle = math.acos(cos_angle)
                    
                    # Check if angle is too sharp (> 90 degrees)
                    if angle > math.pi/2:
                        return False
                except Exception as e:
                    print(f"Aviso: Erro no cálculo de ângulo do segmento {i}: {e}")
                    return False
            return True
            
        except Exception as e:
            print(f"Erro na validação de suavidade do caminho: {e}")
            return False

    def convert_letters_to_numbers(self, text: str) -> str:
        """Converte letras em números usando múltiplas transformações"""
        # Primeira camada: valor ASCII + posição
        ascii_values = []
        for i, char in enumerate(text):
            # Valor base ASCII
            base_value = ord(char)
            
            # Adiciona posição com peso phi
            position_value = int((i + 1) * self.PHI) % 100
            
            # Combina valores de forma não-linear
            combined = (base_value * position_value) % 1000
            
            # Aplica transformação baseada em números transcendentais
            transformed = int(
                (combined * self.PI + 
                 combined * self.EULER + 
                 combined * self.PHI) % 1000
            )
            
            ascii_values.append(str(transformed).zfill(3))
        
        # Segunda camada: aplica XOR entre valores adjacentes
        xor_values = []
        for i in range(len(ascii_values)):
            if i == 0:
                # Primeiro valor usa último como par
                xor_value = int(ascii_values[i]) ^ int(ascii_values[-1])
            else:
                # Outros valores usam anterior
                xor_value = int(ascii_values[i]) ^ int(ascii_values[i-1])
            
            xor_values.append(str(xor_value).zfill(3))
        
        # Terceira camada: soma ponderada com números transcendentais
        weighted_values = []
        for i, (ascii_val, xor_val) in enumerate(zip(ascii_values, xor_values)):
            # Peso baseado em posição e números transcendentais
            weight = (
                (i + 1) * self.PI + 
                (len(text) - i) * self.EULER + 
                (i * 2 + 1) * self.PHI
            )
            
            # Combina valores ASCII e XOR com peso
            combined = int(
                (int(ascii_val) + int(xor_val)) * (weight % 1)
            ) % 1000
            
            weighted_values.append(str(combined).zfill(3))
        
        # Resultado final: intercala valores das três camadas
        final_values = []
        for a, x, w in zip(ascii_values, xor_values, weighted_values):
            # Combina os três valores de forma não-linear
            combined = int(
                (int(a) * self.PI + 
                 int(x) * self.EULER + 
                 int(w) * self.PHI) % 1000
            )
            final_values.append(str(combined).zfill(3))
        
        return "".join(final_values)

    def parse_coordinates(self, input_str: str) -> Tuple[float, float]:
        """Parse coordinates from string input with robust error handling"""
        try:
            # Remove espaços extras e caracteres problemáticos
            input_str = input_str.strip().replace('，', ',')  # Vírgula Unicode
            input_str = input_str.replace('；', ',')  # Ponto e vírgula Unicode
            input_str = input_str.replace(';', ',')  # Ponto e vírgula
            input_str = input_str.replace('|', ',')  # Pipe
            
            # Normaliza separadores decimais
            parts = input_str.replace(',', ' ').split()
            if len(parts) != 2:
                raise ValueError("Formato deve ter exatamente duas coordenadas")
            
            # Tenta converter para float com diferentes formatos
            try:
                lat = float(parts[0].replace(',', '.'))
                lon = float(parts[1].replace(',', '.'))
            except ValueError:
                raise ValueError("Coordenadas devem ser números válidos")
            
            # Valida ranges
            if not -90 <= lat <= 90:
                raise ValueError(f"Latitude {lat} inválida (deve estar entre -90 e 90)")
            if not -180 <= lon <= 180:
                raise ValueError(f"Longitude {lon} inválida (deve estar entre -180 e 180)")
            
            return lat, lon
            
        except Exception as e:
            raise ValueError(f"Erro no formato das coordenadas: {str(e)}")

    def initialize_contract(self) -> ContractInput:
        """Inicializa um novo contrato com inputs do usuário e tratamento de erros"""
        max_attempts = 3
        
        print("\n=== Inicialização de Novo Contrato de Entrega ===")
        print("\nO NTS (Non-Trivial Seed) é uma palavra-chave que afeta:")
        print("1. Distribuição dos pontos no trajeto")
        print("2. Intervalos entre verificações")
        print("3. Tolerância nas validações")
        print("4. Entropia adicional por bloco")
        print("5. Desvios da rota principal")
        
        # Input Ponto A
        attempts = 0
        while attempts < max_attempts:
            try:
                print("\nPonto A (Origem):")
                print("Formatos aceitos:")
                print("- latitude longitude (ex: 38.722087 -9.466213)")
                print("- latitude,longitude (ex: 38.722087,-9.466213)")
                coord_input = input("Coordenadas do ponto A: ")
                point_a_lat, point_a_lon = self.parse_coordinates(coord_input)
                break
            except ValueError as e:
                attempts += 1
                if attempts == max_attempts:
                    raise ValueError(f"Número máximo de tentativas excedido para Ponto A: {e}")
                print(f"Erro: {e}. Tentativa {attempts} de {max_attempts}")
        
        # Input Ponto B
        attempts = 0
        while attempts < max_attempts:
            try:
                print("\nPonto B (Destino):")
                coord_input = input("Coordenadas do ponto B: ")
                point_b_lat, point_b_lon = self.parse_coordinates(coord_input)
                
                # Valida distância mínima entre pontos
                point_a = GPSPoint(point_a_lat, point_a_lon, int(time.time()))
                point_b = GPSPoint(point_b_lat, point_b_lon, int(time.time()))
                metrics = self.calculate_route_metrics(point_a, point_b)
                
                if metrics.raw.dist_total_km < 0.1:  # 100 metros mínimo
                    raise ValueError("Pontos muito próximos. Distância mínima: 100 metros")
                
                break
            except ValueError as e:
                attempts += 1
                if attempts == max_attempts:
                    raise ValueError(f"Número máximo de tentativas excedido para Ponto B: {e}")
                print(f"Erro: {e}. Tentativa {attempts} de {max_attempts}")
        
        # Input NTS
        attempts = 0
        while True:  # Loop infinito até input válido ou máximo de tentativas
            try:
                if attempts >= max_attempts:
                    raise ValueError("Número máximo de tentativas excedido")
                
                print("\nSemente NTS (Non-Trivial Seed):")
                print("Digite uma palavra-chave para influenciar a geração da rota")
                print("Exemplos: nome+data, frase específica, código personalizado")
                print("A palavra-chave deve ter pelo menos 8 caracteres e incluir letras")
                nts_seed = input("Semente NTS: ").strip()
                
                if len(nts_seed) < 8:
                    attempts += 1
                    print(f"Erro: A palavra-chave deve ter pelo menos 8 caracteres. Tentativa {attempts} de {max_attempts}")
                    continue
                
                if not any(c.isalpha() for c in nts_seed):
                    attempts += 1
                    print(f"Erro: A palavra-chave deve conter pelo menos uma letra. Tentativa {attempts} de {max_attempts}")
                    continue
                
                # Gera hash SHA-256 da semente
                try:
                    nts_numeric = SECURITY.hash_nts_seed(nts_seed)
                except Exception as e:
                    attempts += 1
                    print(f"Erro na geração do hash da semente: {e}. Tentativa {attempts} de {max_attempts}")
                    continue
                
                print(f"\nSemente convertida (SHA-256): {nts_numeric}")
                
                # Calcula e mostra as variáveis derivadas com tratamento de erro
                try:
                    # Usa a distância atual para derivar as variáveis
                    nts_vars = self.derive_nts_variables(nts_numeric, metrics.raw.dist_total_km)
                    
                    print("\nVariáveis NTS: [Criptografadas]")
                    print("As variáveis do NTS foram derivadas e criptografadas com sucesso.")
                    print("Os valores são usados internamente de forma segura.")
                    
                except Exception as e:
                    attempts += 1
                    print(f"Erro no cálculo das variáveis NTS: {e}. Tentativa {attempts} de {max_attempts}")
                    continue
                    
                try:
                    confirm = input("\nConfirmar esta semente? (s/n): ").lower()
                    if confirm == 's':
                        nts_seed = nts_numeric
                        break
                    else:
                        attempts += 1
                        if attempts >= max_attempts:
                            raise ValueError("Número máximo de tentativas excedido")
                        continue
                except Exception as e:
                    attempts += 1
                    print(f"Erro na confirmação: {e}. Tentativa {attempts} de {max_attempts}")
                    continue
                
            except ValueError as e:
                raise ValueError(f"Erro na semente NTS: {e}")
        
        contract_input = ContractInput(
            point_a_lat=point_a_lat,
            point_a_lon=point_a_lon,
            point_b_lat=point_b_lat,
            point_b_lon=point_b_lon,
            nts_seed=nts_seed
        )
        
        print("\n=== Métricas Iniciais ===")
        print(f"Coordenadas do Ponto A: {point_a_lat}, {point_a_lon}")
        print(f"Coordenadas do Ponto B: {point_b_lat}, {point_b_lon}")
        print(f"Semente NTS (SHA-256): {nts_seed}")
        print(metrics)  # Usa __str__ modificado que mostra apenas total e tempo
        
        return contract_input

    def create_contract_from_input(self, contract_input: ContractInput) -> Dict:
        """Cria um contrato a partir dos inputs fornecidos"""
        try:
            # Cria pontos GPS
            point_a = GPSPoint(
                contract_input.point_a_lat,
                contract_input.point_a_lon,
                contract_input.timestamp
            )
            point_b = GPSPoint(
                contract_input.point_b_lat,
                contract_input.point_b_lon,
                contract_input.timestamp
            )

            try:
                # Adiciona a semente NTS ao processo de geração do hash
                nts_entropy = hashlib.sha512(contract_input.nts_seed.encode()).digest()
            except Exception as e:
                print(f"Aviso: Erro na geração de entropia NTS: {e}")
                nts_entropy = None

            # Gera o hash genesis com entropia adicional
            try:
                genesis_hash = self.generate_genesis_hash(point_a, point_b, nts_entropy)
            except Exception as e:
                print(f"Aviso: Erro na geração do hash genesis: {e}")
                # Gera hash fallback
                fallback_data = f"{point_a.latitude}:{point_a.longitude}:{point_b.latitude}:{point_b.longitude}:{time.time_ns()}"
                genesis_hash = hashlib.sha512(fallback_data.encode()).hexdigest()

            # Calcula métricas da rota
            try:
                metrics = self.calculate_route_metrics(point_a, point_b)
            except Exception as e:
                print(f"Erro crítico no cálculo de métricas: {e}")
                raise

            # Gera sequência Fibonacci
            try:
                fib_sequence = self.fibonacci_expansion(metrics.raw.dist_total_km, genesis_hash)
            except Exception as e:
                print(f"Aviso: Erro na geração da sequência Fibonacci: {e}")
                # Gera sequência fallback
                fib_sequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]

            # Deriva variáveis do NTS
            try:
                nts_vars = self.derive_nts_variables(contract_input.nts_seed, metrics.raw.dist_total_km)
            except Exception as e:
                print(f"Aviso: Erro na derivação de variáveis NTS: {e}")
                # Usa valores padrão seguros
                nts_vars = NTSVariables(
                    base_numeric=contract_input.nts_seed,
                    time_factor=0.5,
                    distance_factor=0.5,
                    interval_modifier=0.5,
                    point_spread=0.1,
                    validation_threshold=0.8,
                    entropy_boost=[0.5] * 5,
                    system_key=self.SYSTEM_KEY
                )

            return {
                'point_a': point_a,
                'point_b': point_b,
                'genesis_hash': genesis_hash,
                'distance': metrics.raw.dist_total_km,
                'fibonacci_sequence': fib_sequence,
                'metrics': metrics,
                'nts_seed': contract_input.nts_seed,
                'nts_variables': nts_vars
            }

        except Exception as e:
            raise RuntimeError(f"Erro fatal na criação do contrato: {e}")

# Example usage
if __name__ == "__main__":
    try:
        pod = ProofOfDelivery()
        
        try:
            contract_input = pod.initialize_contract()
        except Exception as e:
            print(f"\nErro fatal na inicialização do contrato: {e}")
            exit(1)
        
        try:
            contract = pod.create_contract_from_input(contract_input)
        except Exception as e:
            print(f"\nErro fatal na criação do contrato: {e}")
            exit(1)
        
        print("\n=== Contrato Criado ===")
        print(f"Genesis: {contract['genesis_hash'][:16]}...{contract['genesis_hash'][-16:]}")
        
        try:
            blocks = pod.create_blocks(contract)
            print(f"\nGerados {len(blocks)} blocos")
            
            for block in blocks:
                print(f"\n{block}")  # Usa __str__ modificado do Block
                print(f"{block.encrypted_metrics}")  # Usa __str__ modificado do EncryptedMetrics
                
        except Exception as e:
            print(f"\nErro fatal na geração de blocos: {e}")
            exit(1)
            
    except Exception as e:
        print(f"\nErro fatal no sistema: {e}")
        exit(1)
