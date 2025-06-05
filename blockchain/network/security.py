from __future__ import annotations
import ssl
import socket
import hashlib
import logging
import threading
import json
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
import hmac
import secrets
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class NetworkSecurity:
    """
    Implementa segurança de rede para o sistema blockchain.
    Inclui criptografia, autenticação e proteção contra ataques.
    """
    
    def __init__(self):
        self.peers: Dict[str, PeerInfo] = {}
        self.banned_ips: Set[str] = set()
        self.connection_attempts: Dict[str, int] = {}
        self.last_cleanup = datetime.utcnow()
        
        # Configurações de segurança
        self.max_connections_per_ip = 3
        self.ban_threshold = 5
        self.ban_duration = timedelta(hours=24)
        self.connection_window = timedelta(minutes=5)
        
        # Chaves e tokens
        self.network_key = secrets.token_bytes(32)
        self.session_tokens: Dict[str, Dict] = {}
        
        # Tentativas falhas de autenticação
        self.failed_attempts: Dict[str, Dict] = {}
        
        # Configurações
        self.token_validity = timedelta(hours=1)
        self.max_failed_attempts = 3
        self.lockout_duration = timedelta(minutes=15)
        
        # Iniciar tarefas de manutenção
        self._start_maintenance_tasks()
        
        logging.info("Network security module initialized")

    def verify_peer(
        self,
        peer_address: str,
        peer_cert: Optional[Dict] = None
    ) -> bool:
        """
        Verifica um peer antes de aceitar conexão.
        
        Args:
            peer_address: Endereço do peer
            peer_cert: Certificado do peer (opcional)
            
        Returns:
            bool: True se peer é válido
        """
        try:
            # Verificar bloqueio
            if self._is_peer_locked(peer_address):
                return False
                
            # Verificar token de sessão
            if peer_address in self.session_tokens:
                token = self.session_tokens[peer_address]
                if self._is_token_valid(token):
                    return True
                    
            # Verificar certificado
            if not peer_cert:
                self._register_failed_attempt(peer_address)
                return False
                
            # Criar novo token
            self._create_session_token(peer_address)
            return True
            
        except Exception as e:
            logging.error(f"Error verifying peer: {e}")
            return False

    def create_secure_connection(self, socket: socket.socket) -> ssl.SSLSocket:
        """
        Cria uma conexão SSL/TLS segura.
        """
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        
        return context.wrap_socket(socket)

    def generate_session_token(self, peer_address: str) -> str:
        """
        Gera um token de sessão seguro para um peer.
        """
        token = secrets.token_hex(32)
        expires = datetime.utcnow() + timedelta(hours=12)
        
        self.session_tokens[peer_address] = SessionToken(
            token=token,
            expires=expires,
            peer_address=peer_address
        )
        
        return token

    def verify_message(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Verifica a assinatura de uma mensagem.
        """
        try:
            public_key_obj = serialization.load_pem_public_key(
                public_key,
                backend=default_backend()
            )
            
            public_key_obj.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
            
        except Exception:
            return False

    def encrypt_message(self, data: bytes, public_key: bytes) -> bytes:
        """
        Criptografa mensagem para um peer.
        
        Args:
            data: Dados a criptografar
            public_key: Chave pública do destinatário
            
        Returns:
            bytes: Dados criptografados
        """
        try:
            # Carregar chave pública
            key = serialization.load_pem_public_key(public_key)
            
            # Gerar chave de sessão
            session_key = Fernet.generate_key()
            f = Fernet(session_key)
            
            # Criptografar dados com chave de sessão
            encrypted_data = f.encrypt(data)
            
            # Criptografar chave de sessão com chave pública
            encrypted_key = key.encrypt(
                session_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Combinar chave e dados
            return encrypted_key + b":" + encrypted_data
            
        except Exception as e:
            logging.error(f"Error encrypting message: {e}")
            raise

    def decrypt_message(self, encrypted_data: bytes, private_key: bytes) -> Optional[bytes]:
        """
        Descriptografa mensagem recebida.
        
        Args:
            encrypted_data: Dados criptografados
            private_key: Chave privada do receptor
            
        Returns:
            bytes ou None: Dados descriptografados
        """
        try:
            # Separar chave e dados
            encrypted_key, encrypted_message = encrypted_data.split(b":", 1)
            
            # Carregar chave privada
            key = serialization.load_pem_private_key(
                private_key,
                password=None
            )
            
            # Descriptografar chave de sessão
            session_key = key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Descriptografar dados
            f = Fernet(session_key)
            return f.decrypt(encrypted_message)
            
        except Exception as e:
            logging.error(f"Error decrypting message: {e}")
            return None

    def _is_ip_banned(self, ip_address: str) -> bool:
        """Verifica se um IP está banido."""
        if ip_address in self.banned_ips:
            ban_time = self.banned_ips[ip_address]
            if datetime.utcnow() - ban_time < self.ban_duration:
                return True
            else:
                self.banned_ips.remove(ip_address)
        return False

    def _check_connection_limit(self, ip_address: str) -> bool:
        """Verifica limite de conexões por IP."""
        now = datetime.utcnow()
        
        # Limpar tentativas antigas
        self.connection_attempts = {
            ip: count for ip, count in self.connection_attempts.items()
            if now - ip[1] < self.connection_window
        }
        
        # Verificar limite
        count = self.connection_attempts.get(ip_address, 0)
        if count >= self.max_connections_per_ip:
            if count >= self.ban_threshold:
                self.banned_ips.add(ip_address)
            return False
            
        self.connection_attempts[ip_address] = count + 1
        return True

    def _verify_certificate(self, cert: dict) -> bool:
        """Verifica certificado do peer."""
        try:
            # Implementar verificação de certificado
            # (Exemplo básico - expandir conforme necessidade)
            required_fields = ['subject', 'issuer', 'not_before', 'not_after']
            return all(field in cert for field in required_fields)
        except Exception:
            return False

    def _register_peer(self, peer_address: str):
        """Registra informações do peer."""
        self.peers[peer_address] = PeerInfo(
            address=peer_address,
            last_seen=datetime.utcnow(),
            connection_count=1
        )

    def _start_maintenance_tasks(self):
        """Inicia tarefas de manutenção em background."""
        def cleanup_task():
            while True:
                try:
                    now = datetime.utcnow()
                    
                    # Limpar peers inativos
                    inactive_threshold = now - timedelta(hours=1)
                    inactive_peers = [
                        addr for addr, info in self.peers.items()
                        if info.last_seen < inactive_threshold
                    ]
                    for addr in inactive_peers:
                        del self.peers[addr]
                    
                    # Limpar tokens expirados
                    expired_tokens = [
                        addr for addr, token in self.session_tokens.items()
                        if token.expires < now
                    ]
                    for addr in expired_tokens:
                        del self.session_tokens[addr]
                    
                    # Limpar IPs banidos antigos
                    unbanned = {
                        ip for ip in self.banned_ips
                        if now - self.banned_ips[ip] >= self.ban_duration
                    }
                    self.banned_ips -= unbanned
                    
                except Exception as e:
                    logging.error(f"Error in cleanup task: {e}")
                finally:
                    threading.Event().wait(300)  # Executar a cada 5 minutos
        
        threading.Thread(target=cleanup_task, daemon=True).start()

    def _pad_message(self, message: bytes) -> bytes:
        """Adiciona padding à mensagem para criptografia em bloco."""
        block_size = 16
        padding_length = block_size - (len(message) % block_size)
        padding = bytes([padding_length] * padding_length)
        return message + padding

    def _unpad_message(self, padded_message: bytes) -> bytes:
        """Remove padding da mensagem descriptografada."""
        padding_length = padded_message[-1]
        return padded_message[:-padding_length]

    def _create_session_token(self, peer_address: str):
        """
        Cria um novo token de sessão.
        
        Args:
            peer_address: Endereço do peer
        """
        token = {
            'token': secrets.token_hex(32),
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + self.token_validity
        }
        
        self.session_tokens[peer_address] = token
        
        # Limpar tentativas falhas
        self.failed_attempts.pop(peer_address, None)

    def _is_token_valid(self, token: Dict) -> bool:
        """
        Verifica se um token de sessão é válido.
        
        Args:
            token: Token de sessão
            
        Returns:
            bool: True se válido
        """
        return datetime.utcnow() < token['expires_at']

    def _register_failed_attempt(self, peer_address: str):
        """
        Registra uma tentativa falha de autenticação.
        
        Args:
            peer_address: Endereço do peer
        """
        now = datetime.utcnow()
        
        if peer_address not in self.failed_attempts:
            self.failed_attempts[peer_address] = {
                'count': 1,
                'first_attempt': now,
                'last_attempt': now,
                'locked_until': None
            }
        else:
            attempt = self.failed_attempts[peer_address]
            attempt['count'] += 1
            attempt['last_attempt'] = now
            
            # Bloquear se excedeu limite
            if attempt['count'] >= self.max_failed_attempts:
                attempt['locked_until'] = now + self.lockout_duration

    def _is_peer_locked(self, peer_address: str) -> bool:
        """
        Verifica se um peer está bloqueado.
        
        Args:
            peer_address: Endereço do peer
            
        Returns:
            bool: True se bloqueado
        """
        if peer_address not in self.failed_attempts:
            return False
            
        attempt = self.failed_attempts[peer_address]
        if not attempt['locked_until']:
            return False
            
        # Verificar se ainda está bloqueado
        if datetime.utcnow() < attempt['locked_until']:
            return True
            
        # Limpar bloqueio expirado
        self.failed_attempts.pop(peer_address)
        return False


class PeerInfo:
    """Armazena informações sobre um peer."""
    def __init__(self, address: str, last_seen: datetime, connection_count: int):
        self.address = address
        self.last_seen = last_seen
        self.connection_count = connection_count


class SessionToken:
    """Representa um token de sessão."""
    def __init__(self, token: str, expires: datetime, peer_address: str):
        self.token = token
        self.expires = expires
        self.peer_address = peer_address 