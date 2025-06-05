"""
API REST para interação com o sistema LogiChain.
Implementa endpoints seguros com autenticação JWT.
"""

from typing import List, Optional, Annotated
from decimal import Decimal
import jwt
import time
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..core.config import SecurityConstants, NetworkConfig
from ..core.smart_contract import SmartContractManager, ContractStatus
from ..core.pod import GeoPoint, ProofOfDelivery
from ..core.fare_calculator import FareCalculator
from ..core.fare_governance import FareGovernance
from ..security.crypto import CryptoManager

# Inicializa API
app = FastAPI(
    title="LogiChain API",
    description="API para sistema de logística em blockchain",
    version="1.0.0"
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Segurança
security = HTTPBearer()
crypto = CryptoManager()

# Gerenciadores
contract_manager = SmartContractManager()
pod_manager = ProofOfDelivery()
fare_calculator = FareCalculator()
governance = FareGovernance()

# Models Pydantic
class GeoPointModel(BaseModel):
    latitude: Decimal = Field(description="Latitude do ponto")
    longitude: Decimal = Field(description="Longitude do ponto")
    timestamp: int = Field(description="Timestamp Unix do ponto")
    accuracy: Optional[float] = Field(None, description="Precisão do GPS em metros")

class CreateContractRequest(BaseModel):
    pickup_point: GeoPointModel = Field(description="Ponto de coleta")
    delivery_point: GeoPointModel = Field(description="Ponto de entrega")
    energy_type: str = Field(default="diesel", description="Tipo de energia")

class AcceptContractRequest(BaseModel):
    contract_id: str = Field(description="ID do contrato")
    driver_wallet: str = Field(description="Carteira do motorista")

class CheckpointRequest(BaseModel):
    contract_id: str = Field(description="ID do contrato")
    point: GeoPointModel = Field(description="Ponto do checkpoint")
    driver_wallet: str = Field(description="Carteira do motorista")

class CompleteContractRequest(BaseModel):
    contract_id: str = Field(description="ID do contrato")
    driver_wallet: str = Field(description="Carteira do motorista")
    signature: str = Field(description="Assinatura digital")

class ProposalRequest(BaseModel):
    diesel_barrel_price_gbp: Optional[Decimal] = Field(None, description="Preço do barril de diesel em GBP")
    minimum_wage_hour_gbp: Optional[Decimal] = Field(None, description="Salário mínimo por hora em GBP")
    country_tax_rate: Optional[Decimal] = Field(None, description="Taxa de imposto do país")
    driver_fixed_profit_gbp: Optional[Decimal] = Field(None, description="Lucro fixo do motorista em GBP")

class VoteRequest(BaseModel):
    proposal_id: str = Field(description="ID da proposta")
    approve: bool = Field(description="Voto de aprovação")

# Funções auxiliares
async def verify_token(credentials: Annotated[HTTPAuthorizationCredentials, Security(security)]) -> str:
    """Verifica token JWT e retorna wallet"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            "secret",  # Usar variável de ambiente em produção
            algorithms=["HS256"]
        )
        
        if payload["exp"] < time.time():
            raise HTTPException(
                status_code=401,
                detail="Token expirado"
            )
        
        return payload["wallet"]
        
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

# Rotas da API
@app.post("/contracts/create")
async def create_contract(
    request: CreateContractRequest,
    wallet: str = Depends(verify_token)
) -> dict:
    """Cria novo contrato de entrega"""
    try:
        pickup = GeoPoint(
            latitude=request.pickup_point.latitude,
            longitude=request.pickup_point.longitude,
            timestamp=request.pickup_point.timestamp,
            accuracy=request.pickup_point.accuracy
        )
        
        delivery = GeoPoint(
            latitude=request.delivery_point.latitude,
            longitude=request.delivery_point.longitude,
            timestamp=request.delivery_point.timestamp,
            accuracy=request.delivery_point.accuracy
        )
        
        contract_id = contract_manager.create_contract(
            client_wallet=wallet,
            pickup_point=pickup,
            delivery_point=delivery,
            energy_type=request.energy_type
        )
        
        return {"contract_id": contract_id}
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/contracts/accept")
async def accept_contract(
    request: AcceptContractRequest,
    wallet: str = Depends(verify_token)
) -> dict:
    """Aceita contrato de entrega"""
    if wallet != request.driver_wallet:
        raise HTTPException(
            status_code=403,
            detail="Wallet não autorizada"
        )
    
    success = contract_manager.accept_contract(
        contract_id=request.contract_id,
        driver_wallet=wallet
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Falha ao aceitar contrato"
        )
    
    return {"success": True}

@app.post("/contracts/checkpoint")
async def add_checkpoint(
    request: CheckpointRequest,
    wallet: str = Depends(verify_token)
) -> dict:
    """Adiciona checkpoint ao contrato"""
    if wallet != request.driver_wallet:
        raise HTTPException(
            status_code=403,
            detail="Wallet não autorizada"
        )
    
    point = GeoPoint(
        latitude=request.point.latitude,
        longitude=request.point.longitude,
        timestamp=request.point.timestamp,
        accuracy=request.point.accuracy
    )
    
    success = contract_manager.add_checkpoint(
        contract_id=request.contract_id,
        point=point,
        driver_wallet=wallet
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Falha ao adicionar checkpoint"
        )
    
    return {"success": True}

@app.post("/contracts/complete")
async def complete_contract(
    request: CompleteContractRequest,
    wallet: str = Depends(verify_token)
) -> dict:
    """Completa contrato com prova de entrega"""
    if wallet != request.driver_wallet:
        raise HTTPException(
            status_code=403,
            detail="Wallet não autorizada"
        )
    
    success = contract_manager.complete_contract(
        contract_id=request.contract_id,
        driver_wallet=wallet,
        signature=request.signature
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Falha ao completar contrato"
        )
    
    return {"success": True}

@app.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: str,
    wallet: str = Depends(verify_token)
) -> dict:
    """Retorna dados do contrato"""
    contract = contract_manager.get_contract(contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=404,
            detail="Contrato não encontrado"
        )
    
    if (contract["client_wallet"] != wallet and
        contract["driver_wallet"] != wallet):
        raise HTTPException(
            status_code=403,
            detail="Acesso não autorizado"
        )
    
    return contract

@app.get("/contracts")
async def list_contracts(
    status: Optional[str] = None,
    wallet: str = Depends(verify_token)
) -> List[dict]:
    """Lista contratos filtrados"""
    contract_status = (
        ContractStatus(status.lower())
        if status else None
    )
    
    return contract_manager.list_contracts(
        status=contract_status,
        wallet=wallet
    )

@app.post("/governance/propose")
async def create_proposal(
    request: ProposalRequest,
    wallet: str = Depends(verify_token)
) -> dict:
    """Cria proposta de alteração de variáveis"""
    if not governance.check_pool_status(wallet):
        raise HTTPException(
            status_code=403,
            detail="POOL suspenso"
        )
    
    current = governance.get_current_variables()
    
    # Atualiza apenas campos fornecidos
    if request.diesel_barrel_price_gbp is not None:
        current.diesel_barrel_price_gbp = request.diesel_barrel_price_gbp
    if request.minimum_wage_hour_gbp is not None:
        current.minimum_wage_hour_gbp = request.minimum_wage_hour_gbp
    if request.country_tax_rate is not None:
        current.country_tax_rate = request.country_tax_rate
    if request.driver_fixed_profit_gbp is not None:
        current.driver_fixed_profit_gbp = request.driver_fixed_profit_gbp
    
    proposal_id = governance.create_proposal(
        proposed_variables=current,
        proposer_wallet=wallet
    )
    
    return {"proposal_id": proposal_id}

@app.post("/governance/vote")
async def submit_vote(
    request: VoteRequest,
    wallet: str = Depends(verify_token)
) -> dict:
    """Submete voto em proposta"""
    # Determina se é POOL ou motorista
    is_pool = wallet.startswith("0xPOOL")
    
    if is_pool and not governance.check_pool_status(wallet):
        raise HTTPException(
            status_code=403,
            detail="POOL suspenso"
        )
    
    success = governance.submit_vote(
        proposal_id=request.proposal_id,
        voter_wallet=wallet,
        is_pool=is_pool,
        approve=request.approve
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Falha ao registrar voto"
        )
    
    return {"success": True}

@app.get("/governance/proposals")
async def list_proposals(
    wallet: str = Depends(verify_token)
) -> List[dict]:
    """Lista propostas ativas"""
    proposals = []
    
    for proposal in governance.list_active_proposals():
        proposals.append({
            "id": proposal.proposal_id,
            "proposer": proposal.proposer_wallet,
            "timestamp": proposal.proposal_timestamp.isoformat(),
            "consensus": proposal.calculate_consensus(),
            "variables": proposal.proposed_variables.to_dict()
        })
    
    return proposals

@app.get("/governance/variables")
async def get_current_variables(
    wallet: str = Depends(verify_token)
) -> dict:
    """Retorna variáveis atuais"""
    return governance.get_current_variables().to_dict() 