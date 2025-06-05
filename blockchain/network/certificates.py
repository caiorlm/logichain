from __future__ import annotations
import os
import json
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

class CertificateManager:
    """
    Gerencia certificados digitais dos nós.
    """
    
    def __init__(self, base_path: str = None):
        """
        Inicializa o gerenciador de certificados.
        
        Args:
            base_path: Caminho base para armazenamento (opcional)
        """
        self.base_path = base_path or os.path.expanduser("~/.blockchain")
        self.certs_path = os.path.join(self.base_path, "certs")
        self.revoked_path = os.path.join(self.certs_path, "revoked")
        
        # Criar diretórios
        os.makedirs(self.certs_path, exist_ok=True)
        os.makedirs(self.revoked_path, exist_ok=True)
        
        logging.info("Certificate manager initialized")

    def generate_certificate(
        self,
        node_id: str,
        public_key: bytes,
        valid_days: int = 365
    ) -> Optional[Dict]:
        """
        Gera um novo certificado.
        
        Args:
            node_id: Identificador do nó
            public_key: Chave pública em bytes
            valid_days: Validade em dias
            
        Returns:
            Dict ou None: Informações do certificado
        """
        try:
            # Carregar chave pública
            public_key = serialization.load_pem_public_key(public_key)
            
            # Criar certificado
            builder = x509.CertificateBuilder()
            
            # Definir informações do certificado
            name = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, node_id)
            ])
            
            builder = builder.subject_name(name)
            builder = builder.issuer_name(name)  # Self-signed
            
            # Definir validade
            now = datetime.utcnow()
            builder = builder.not_valid_before(now)
            builder = builder.not_valid_after(now + timedelta(days=valid_days))
            
            # Definir chave pública
            builder = builder.public_key(public_key)
            
            # Gerar serial number único
            builder = builder.serial_number(int(time.time() * 1000))
            
            # Assinar certificado
            certificate = builder.sign(
                private_key=public_key,  # Self-signed
                algorithm=hashes.SHA256()
            )
            
            # Serializar certificado
            cert_bytes = certificate.public_bytes(
                encoding=serialization.Encoding.PEM
            )
            
            # Salvar certificado
            cert_path = os.path.join(self.certs_path, f"{node_id}.crt")
            with open(cert_path, 'wb') as f:
                f.write(cert_bytes)
                
            # Retornar informações
            return {
                'node_id': node_id,
                'certificate': cert_bytes,
                'public_key': public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ),
                'valid_from': now.isoformat(),
                'valid_until': (now + timedelta(days=valid_days)).isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error generating certificate: {e}")
            return None

    def verify_certificate(self, certificate: bytes, node_id: str) -> bool:
        """
        Verifica um certificado.
        
        Args:
            certificate: Certificado em bytes
            node_id: Identificador do nó
            
        Returns:
            bool: True se válido
        """
        try:
            # Carregar certificado
            cert = x509.load_pem_x509_certificate(certificate)
            
            # Verificar se está revogado
            if self.is_revoked(node_id):
                return False
                
            # Verificar validade
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                return False
                
            # Verificar node_id
            if cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value != node_id:
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Error verifying certificate: {e}")
            return False

    def revoke_certificate(self, node_id: str) -> bool:
        """
        Revoga um certificado.
        
        Args:
            node_id: Identificador do nó
            
        Returns:
            bool: True se revogado com sucesso
        """
        try:
            cert_path = os.path.join(self.certs_path, f"{node_id}.crt")
            revoked_path = os.path.join(self.revoked_path, f"{node_id}.crt")
            
            if not os.path.exists(cert_path):
                return False
                
            # Mover para diretório de revogados
            os.rename(cert_path, revoked_path)
            
            # Registrar timestamp da revogação
            revoked_info = {
                'node_id': node_id,
                'revoked_at': datetime.utcnow().isoformat(),
                'reason': 'administrative_action'
            }
            
            info_path = os.path.join(self.revoked_path, f"{node_id}.json")
            with open(info_path, 'w') as f:
                json.dump(revoked_info, f, indent=2)
                
            return True
            
        except Exception as e:
            logging.error(f"Error revoking certificate: {e}")
            return False

    def is_revoked(self, node_id: str) -> bool:
        """
        Verifica se um certificado está revogado.
        
        Args:
            node_id: Identificador do nó
            
        Returns:
            bool: True se revogado
        """
        revoked_path = os.path.join(self.revoked_path, f"{node_id}.crt")
        return os.path.exists(revoked_path)

    def get_certificate(self, node_id: str) -> Optional[Dict]:
        """
        Obtém informações de um certificado.
        
        Args:
            node_id: Identificador do nó
            
        Returns:
            Dict ou None: Informações do certificado
        """
        try:
            cert_path = os.path.join(self.certs_path, f"{node_id}.crt")
            
            if not os.path.exists(cert_path):
                return None
                
            # Carregar certificado
            with open(cert_path, 'rb') as f:
                cert_bytes = f.read()
                
            cert = x509.load_pem_x509_certificate(cert_bytes)
            
            return {
                'node_id': node_id,
                'certificate': cert_bytes,
                'public_key': cert.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ),
                'valid_from': cert.not_valid_before.isoformat(),
                'valid_until': cert.not_valid_after.isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error getting certificate: {e}")
            return None 