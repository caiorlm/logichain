"""
Implementação de state channels para escalabilidade off-chain
"""

from typing import Dict, List, Optional, Any
import time
import json
import hashlib
import threading
import logging
from dataclasses import dataclass
from enum import Enum

from ..core.transaction import Transaction
from ..security import SecurityManager

class ChannelState(Enum):
    """Estado do canal"""
    OPENING = "opening"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    DISPUTED = "disputed"

@dataclass
class ChannelUpdate:
    """Atualização do estado do canal"""
    nonce: int
    state: Dict[str, Any]
    signatures: Dict[str, str]
    timestamp: float

class StateChannel:
    """
    Canal de estado para transações off-chain
    
    Permite que participantes realizem transações
    sem precisar publicá-las na blockchain
    """
    
    def __init__(
        self,
        channel_id: str,
        participants: List[str],
        initial_state: Dict[str, Any],
        lock_time: int = 24 * 3600,  # 24 horas
        security_manager: Optional[SecurityManager] = None
    ):
        self.channel_id = channel_id
        self.participants = set(participants)
        self.lock_time = lock_time
        
        # Estado
        self.state = ChannelState.OPENING
        self.current_state = initial_state
        self.nonce = 0
        self.updates: List[ChannelUpdate] = []
        self.dispute_timer: Optional[float] = None
        
        # Segurança
        self.security = security_manager or SecurityManager()
        
        # Threading
        self.lock = threading.RLock()
        
        logging.info(f"StateChannel initialized: {channel_id}")
        
    def open(self) -> bool:
        """Abre o canal"""
        with self.lock:
            if self.state != ChannelState.OPENING:
                return False
                
            self.state = ChannelState.ACTIVE
            self._add_update(self.current_state, {})
            return True
            
    def update_state(
        self,
        new_state: Dict[str, Any],
        signature: str,
        participant: str
    ) -> bool:
        """
        Atualiza estado do canal
        
        Args:
            new_state: Novo estado
            signature: Assinatura do estado
            participant: Participante que assinou
            
        Returns:
            bool: True se atualização foi aceita
        """
        with self.lock:
            # Validações
            if self.state != ChannelState.ACTIVE:
                return False
                
            if participant not in self.participants:
                return False
                
            if not self._verify_signature(new_state, signature, participant):
                return False
                
            # Atualiza estado
            self.current_state = new_state
            self.nonce += 1
            
            # Registra update
            signatures = {participant: signature}
            self._add_update(new_state, signatures)
            
            return True
            
    def add_signature(
        self,
        state_hash: str,
        signature: str,
        participant: str
    ) -> bool:
        """
        Adiciona assinatura a um estado
        
        Args:
            state_hash: Hash do estado
            signature: Assinatura
            participant: Participante
            
        Returns:
            bool: True se assinatura foi aceita
        """
        with self.lock:
            if participant not in self.participants:
                return False
                
            # Encontra update
            update = self._find_update_by_hash(state_hash)
            if not update:
                return False
                
            # Verifica assinatura
            if not self._verify_signature(
                update.state,
                signature,
                participant
            ):
                return False
                
            # Adiciona assinatura
            update.signatures[participant] = signature
            
            return True
            
    def close(
        self,
        final_state: Dict[str, Any],
        signatures: Dict[str, str]
    ) -> bool:
        """
        Inicia fechamento do canal
        
        Args:
            final_state: Estado final
            signatures: Assinaturas dos participantes
            
        Returns:
            bool: True se fechamento foi iniciado
        """
        with self.lock:
            if self.state != ChannelState.ACTIVE:
                return False
                
            # Verifica assinaturas
            if not self._verify_all_signatures(final_state, signatures):
                return False
                
            # Inicia fechamento
            self.state = ChannelState.CLOSING
            self.current_state = final_state
            self.dispute_timer = time.time() + self.lock_time
            
            # Registra update final
            self._add_update(final_state, signatures)
            
            return True
            
    def dispute(
        self,
        state: Dict[str, Any],
        signatures: Dict[str, str],
        participant: str
    ) -> bool:
        """
        Inicia disputa do canal
        
        Args:
            state: Estado disputado
            signatures: Assinaturas do estado
            participant: Participante que iniciou disputa
            
        Returns:
            bool: True se disputa foi aceita
        """
        with self.lock:
            if self.state not in (ChannelState.CLOSING, ChannelState.ACTIVE):
                return False
                
            if participant not in self.participants:
                return False
                
            # Verifica assinaturas
            if not self._verify_all_signatures(state, signatures):
                return False
                
            # Encontra nonce do estado
            update = self._find_update_by_state(state)
            if not update or update.nonce <= self.nonce:
                return False
                
            # Aceita disputa
            self.state = ChannelState.DISPUTED
            self.current_state = state
            self.nonce = update.nonce
            self.dispute_timer = time.time() + self.lock_time
            
            return True
            
    def resolve_dispute(
        self,
        state: Dict[str, Any],
        signatures: Dict[str, str]
    ) -> bool:
        """
        Resolve disputa com novo estado
        
        Args:
            state: Novo estado
            signatures: Assinaturas
            
        Returns:
            bool: True se disputa foi resolvida
        """
        with self.lock:
            if self.state != ChannelState.DISPUTED:
                return False
                
            # Verifica assinaturas
            if not self._verify_all_signatures(state, signatures):
                return False
                
            # Encontra nonce do estado
            update = self._find_update_by_state(state)
            if not update or update.nonce <= self.nonce:
                return False
                
            # Resolve disputa
            self.state = ChannelState.CLOSING
            self.current_state = state
            self.nonce = update.nonce
            self.dispute_timer = time.time() + self.lock_time
            
            return True
            
    def finalize(self) -> bool:
        """Finaliza canal após período de disputa"""
        with self.lock:
            if self.state not in (ChannelState.CLOSING, ChannelState.DISPUTED):
                return False
                
            if not self.dispute_timer or time.time() < self.dispute_timer:
                return False
                
            self.state = ChannelState.CLOSED
            return True
            
    def get_state(self) -> Dict[str, Any]:
        """Retorna estado atual"""
        return self.current_state.copy()
        
    def get_latest_update(self) -> Optional[ChannelUpdate]:
        """Retorna última atualização"""
        return self.updates[-1] if self.updates else None
        
    def _add_update(
        self,
        state: Dict[str, Any],
        signatures: Dict[str, str]
    ):
        """Adiciona nova atualização"""
        update = ChannelUpdate(
            nonce=self.nonce,
            state=state,
            signatures=signatures,
            timestamp=time.time()
        )
        self.updates.append(update)
        
    def _find_update_by_hash(
        self,
        state_hash: str
    ) -> Optional[ChannelUpdate]:
        """Encontra update pelo hash do estado"""
        for update in reversed(self.updates):
            if self._hash_state(update.state) == state_hash:
                return update
        return None
        
    def _find_update_by_state(
        self,
        state: Dict[str, Any]
    ) -> Optional[ChannelUpdate]:
        """Encontra update pelo estado"""
        state_hash = self._hash_state(state)
        return self._find_update_by_hash(state_hash)
        
    def _verify_signature(
        self,
        state: Dict[str, Any],
        signature: str,
        participant: str
    ) -> bool:
        """Verifica assinatura de um participante"""
        state_hash = self._hash_state(state)
        return self.security.verify_signature(
            state_hash,
            signature,
            participant
        )
        
    def _verify_all_signatures(
        self,
        state: Dict[str, Any],
        signatures: Dict[str, str]
    ) -> bool:
        """Verifica todas as assinaturas"""
        if set(signatures.keys()) != self.participants:
            return False
            
        return all(
            self._verify_signature(state, sig, participant)
            for participant, sig in signatures.items()
        )
        
    @staticmethod
    def _hash_state(state: Dict[str, Any]) -> str:
        """Gera hash do estado"""
        state_json = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()
        
    @staticmethod
    def generate_channel_id(
        participants: List[str],
        nonce: int
    ) -> str:
        """Gera ID único para o canal"""
        data = f"{sorted(participants)}{nonce}{time.time()}".encode()
        return hashlib.sha256(data).hexdigest() 