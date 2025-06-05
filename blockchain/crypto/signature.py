"""
LogiChain Signature Module
Implementação própria de assinaturas usando apenas bibliotecas padrão Python
"""

import hashlib
import hmac
import secrets
from typing import Tuple, Optional, Dict, Any
import json
import base64

class SignatureManager:
    """Gerenciador de assinaturas da LogiChain"""
    
    def __init__(self):
        self.hash_function = hashlib.sha256
        
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Assinar mensagem com chave privada"""
        # Calcular hash da mensagem
        message_hash = self.hash_function(message).digest()
        
        # Gerar nonce aleatório
        nonce = secrets.token_bytes(32)
        
        # Calcular k = HMAC(private_key, message_hash || nonce)
        k = hmac.new(
            private_key,
            message_hash + nonce,
            self.hash_function
        ).digest()
        
        # Calcular assinatura = HMAC(k, message_hash)
        signature = hmac.new(k, message_hash, self.hash_function).digest()
        
        # Retornar nonce || signature
        return nonce + signature
        
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verificar assinatura com chave pública"""
        try:
            # Extrair nonce e assinatura
            nonce = signature[:32]
            sig = signature[32:]
            
            # Calcular hash da mensagem
            message_hash = self.hash_function(message).digest()
            
            # Calcular k = HMAC(public_key, message_hash || nonce)
            k = hmac.new(
                public_key,
                message_hash + nonce,
                self.hash_function
            ).digest()
            
            # Calcular assinatura esperada
            expected = hmac.new(k, message_hash, self.hash_function).digest()
            
            # Comparar assinaturas
            return hmac.compare_digest(sig, expected)
            
        except Exception:
            return False
            
    def sign_json(self, private_key: bytes, data: Dict[str, Any]) -> str:
        """Assinar dados JSON"""
        # Serializar dados
        message = json.dumps(data, sort_keys=True).encode()
        
        # Assinar
        signature = self.sign(private_key, message)
        
        # Codificar em base64
        return base64.b64encode(signature).decode()
        
    def verify_json(self, public_key: bytes, data: Dict[str, Any], signature: str) -> bool:
        """Verificar assinatura de dados JSON"""
        try:
            # Serializar dados
            message = json.dumps(data, sort_keys=True).encode()
            
            # Decodificar assinatura
            sig_bytes = base64.b64decode(signature)
            
            # Verificar
            return self.verify(public_key, message, sig_bytes)
            
        except Exception:
            return False 