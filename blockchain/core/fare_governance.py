"""
Sistema de governança para atualização de variáveis de frete via consenso.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import json
import logging
from .fare_calculator import FareVariables, FareConstants

@dataclass
class VoteProposal:
    """Proposta de alteração de variáveis de frete"""
    proposal_id: str
    proposed_variables: FareVariables
    proposer_wallet: str
    proposal_timestamp: datetime
    votes_pool: Dict[str, bool] = field(default_factory=dict)
    votes_drivers: Dict[str, bool] = field(default_factory=dict)
    status: str = "open"
    
    def calculate_consensus(self) -> Dict[str, float]:
        """Calcula percentual de consenso entre POOLs e motoristas"""
        if not self.votes_pool or not self.votes_drivers:
            return {"pools": 0.0, "drivers": 0.0}
            
        pool_approval = sum(1 for v in self.votes_pool.values() if v) / len(self.votes_pool)
        driver_approval = sum(1 for v in self.votes_drivers.values() if v) / len(self.votes_drivers)
        
        return {
            "pools": pool_approval,
            "drivers": driver_approval
        }
    
    def to_dict(self) -> Dict:
        """Converte proposta para dicionário"""
        return {
            "proposal_id": self.proposal_id,
            "proposed_variables": self.proposed_variables.to_dict(),
            "proposer_wallet": self.proposer_wallet,
            "proposal_timestamp": self.proposal_timestamp.isoformat(),
            "votes_pool": self.votes_pool,
            "votes_drivers": self.votes_drivers,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VoteProposal':
        """Cria proposta a partir de dicionário"""
        return cls(
            proposal_id=data["proposal_id"],
            proposed_variables=FareVariables.from_dict(data["proposed_variables"]),
            proposer_wallet=data["proposer_wallet"],
            proposal_timestamp=datetime.fromisoformat(data["proposal_timestamp"]),
            votes_pool=data["votes_pool"],
            votes_drivers=data["votes_drivers"],
            status=data["status"]
        )

class FareGovernance:
    """Sistema de governança para atualização de variáveis"""
    
    def __init__(self, blockchain=None):
        self.current_variables = FareVariables.from_genesis()
        self.active_proposals: Dict[str, VoteProposal] = {}
        self.failed_votes_by_pool: Dict[str, int] = {}
        self.blockchain = blockchain
        self.logger = logging.getLogger("FareGovernance")
    
    def create_proposal(
        self,
        proposed_variables: FareVariables,
        proposer_wallet: str
    ) -> str:
        """Cria nova proposta de alteração"""
        proposal_id = hashlib.sha256(
            f"{proposer_wallet}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        proposal = VoteProposal(
            proposal_id=proposal_id,
            proposed_variables=proposed_variables,
            proposer_wallet=proposer_wallet,
            proposal_timestamp=datetime.now()
        )
        
        self.active_proposals[proposal_id] = proposal
        self._register_on_chain("proposal_created", proposal.to_dict())
        
        self.logger.info(f"Nova proposta criada: {proposal_id}")
        return proposal_id
    
    def submit_vote(
        self,
        proposal_id: str,
        voter_wallet: str,
        is_pool: bool,
        approve: bool
    ) -> bool:
        """Registra voto em uma proposta"""
        if proposal_id not in self.active_proposals:
            self.logger.warning(f"Proposta não encontrada: {proposal_id}")
            return False
            
        proposal = self.active_proposals[proposal_id]
        
        # Verifica se já votou
        if is_pool and voter_wallet in proposal.votes_pool:
            self.logger.warning(f"POOL já votou: {voter_wallet}")
            return False
        if not is_pool and voter_wallet in proposal.votes_drivers:
            self.logger.warning(f"Motorista já votou: {voter_wallet}")
            return False
        
        # Registra voto
        if is_pool:
            proposal.votes_pool[voter_wallet] = approve
        else:
            proposal.votes_drivers[voter_wallet] = approve
            
        self._register_on_chain("vote_submitted", {
            "proposal_id": proposal_id,
            "voter": voter_wallet,
            "is_pool": is_pool,
            "approve": approve
        })
        
        # Verifica consenso
        consensus = proposal.calculate_consensus()
        self.logger.info(f"Consenso atual: {consensus}")
        
        if consensus["pools"] >= FareConstants.MIN_CONSENSUS_PERCENTAGE and \
           consensus["drivers"] >= FareConstants.MIN_CONSENSUS_PERCENTAGE:
            self._apply_proposal(proposal)
            return True
            
        # Verifica se proposta falhou
        if len(proposal.votes_pool) >= 10 and len(proposal.votes_drivers) >= 10:
            if consensus["pools"] < 0.3 or consensus["drivers"] < 0.3:
                self._fail_proposal(proposal)
                
        return False
    
    def _apply_proposal(self, proposal: VoteProposal):
        """Aplica proposta aprovada"""
        self.current_variables = proposal.proposed_variables
        proposal.status = "approved"
        
        self._register_on_chain("proposal_approved", {
            "proposal_id": proposal.proposal_id,
            "new_variables": proposal.proposed_variables.to_dict(),
            "consensus": proposal.calculate_consensus()
        })
        
        self.logger.info(f"Proposta aprovada: {proposal.proposal_id}")
    
    def _fail_proposal(self, proposal: VoteProposal):
        """Marca proposta como falha e atualiza contadores"""
        proposal.status = "failed"
        
        # Atualiza contadores de falha dos POOLs que votaram contra
        for pool, approved in proposal.votes_pool.items():
            if not approved:
                self.failed_votes_by_pool[pool] = self.failed_votes_by_pool.get(pool, 0) + 1
                
                # Verifica suspensão
                if self.failed_votes_by_pool[pool] >= FareConstants.MAX_FAILED_VOTES:
                    self._suspend_pool(pool)
        
        self._register_on_chain("proposal_failed", {
            "proposal_id": proposal.proposal_id,
            "consensus": proposal.calculate_consensus()
        })
        
        self.logger.info(f"Proposta falhou: {proposal.proposal_id}")
    
    def check_pool_status(self, pool_wallet: str) -> bool:
        """Verifica se POOL deve ser suspenso"""
        failed_votes = self.failed_votes_by_pool.get(pool_wallet, 0)
        return failed_votes < FareConstants.MAX_FAILED_VOTES
    
    def _suspend_pool(self, pool_wallet: str):
        """Suspende POOL por falta de consenso"""
        suspension_end = datetime.now() + timedelta(days=120)  # 4 meses
        
        self._register_on_chain("pool_suspended", {
            "pool_wallet": pool_wallet,
            "reason": "consensus_failure",
            "suspension_end": suspension_end.isoformat(),
            "failed_votes": self.failed_votes_by_pool[pool_wallet]
        })
        
        self.logger.warning(f"POOL suspenso: {pool_wallet}")
    
    def _register_on_chain(self, event_type: str, data: Dict):
        """Registra evento no blockchain"""
        if self.blockchain:
            self.blockchain.register_governance_event(event_type, data)
        
        self.logger.debug(f"Evento registrado: {event_type}")
    
    def get_proposal(self, proposal_id: str) -> Optional[VoteProposal]:
        """Retorna proposta por ID"""
        return self.active_proposals.get(proposal_id)
    
    def list_active_proposals(self) -> List[VoteProposal]:
        """Lista propostas ativas"""
        return [p for p in self.active_proposals.values() if p.status == "open"]
    
    def get_current_variables(self) -> FareVariables:
        """Retorna variáveis atuais"""
        return self.current_variables 