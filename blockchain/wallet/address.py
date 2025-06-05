import hashlib
import base58
from typing import Tuple
from dataclasses import dataclass

@dataclass
class Address:
    """
    Implementação simplificada de endereços.
    Apenas suporta endereços P2PKH.
    """
    
    version: int
    hash160: bytes
    
    @classmethod
    def from_public_key(cls, public_key: bytes, version: int = 0x00) -> 'Address':
        """
        Cria um endereço a partir de uma chave pública.
        
        Args:
            public_key: Chave pública em bytes
            version: Versão do endereço (0x00 para mainnet)
            
        Returns:
            Address: Novo endereço
        """
        # Calcula HASH160 (RIPEMD160(SHA256()))
        sha256 = hashlib.sha256(public_key).digest()
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256)
        hash160 = ripemd160.digest()
        
        return cls(version=version, hash160=hash160)
        
    def to_string(self) -> str:
        """
        Converte o endereço para string base58check.
        
        Returns:
            str: Endereço em formato base58check
        """
        # Concatena versão e hash160
        extended = bytes([self.version]) + self.hash160
        
        # Adiciona checksum
        checksum = hashlib.sha256(
            hashlib.sha256(extended).digest()
        ).digest()[:4]
        
        # Codifica em base58
        return base58.b58encode(extended + checksum).decode()
        
    @classmethod
    def from_string(cls, address: str) -> 'Address':
        """
        Cria um endereço a partir de uma string base58check.
        
        Args:
            address: Endereço em formato base58check
            
        Returns:
            Address: Novo endereço
            
        Raises:
            ValueError: Se endereço inválido
        """
        try:
            # Decodifica base58
            decoded = base58.b58decode(address)
            
            # Separa versão, hash160 e checksum
            version = decoded[0]
            hash160 = decoded[1:-4]
            checksum = decoded[-4:]
            
            # Verifica checksum
            extended = decoded[:-4]
            expected_checksum = hashlib.sha256(
                hashlib.sha256(extended).digest()
            ).digest()[:4]
            
            if checksum != expected_checksum:
                raise ValueError("Invalid checksum")
                
            return cls(version=version, hash160=hash160)
            
        except Exception as e:
            raise ValueError(f"Invalid address: {e}")
            
    def __str__(self) -> str:
        return self.to_string()
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Address):
            return False
        return (
            self.version == other.version and
            self.hash160 == other.hash160
        ) 