"""
LogiChain Bridge API
REST endpoints for bridge operations
"""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..bridge.bridge_service import BridgeService, ChainType, BridgeTransaction
from ..bridge.custody_service import CustodyService

router = APIRouter(prefix="/bridge", tags=["bridge"])

class BridgeRequest(BaseModel):
    """Bridge transaction request"""
    from_chain: str
    to_chain: str
    from_address: str
    to_address: str
    amount: float

class BridgeResponse(BaseModel):
    """Bridge transaction response"""
    tx_hash: str
    from_chain: str
    to_chain: str
    from_address: str
    to_address: str
    amount: float
    fee: float
    status: str

@router.post("/transfer", response_model=BridgeResponse)
async def create_bridge_transfer(
    request: BridgeRequest,
    bridge_service: BridgeService = Depends(),
    custody_service: CustodyService = Depends()
) -> Dict:
    """Create new bridge transfer"""
    try:
        # Validate chains
        try:
            from_chain = ChainType(request.from_chain)
            to_chain = ChainType(request.to_chain)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid chain type"
            )
            
        # Create bridge transaction
        bridge_tx = bridge_service.create_bridge_transaction(
            from_chain=from_chain,
            to_chain=to_chain,
            from_address=request.from_address,
            to_address=request.to_address,
            amount=request.amount
        )
        
        return {
            "tx_hash": bridge_tx.tx_hash,
            "from_chain": bridge_tx.from_chain.value,
            "to_chain": bridge_tx.to_chain.value,
            "from_address": bridge_tx.from_address,
            "to_address": bridge_tx.to_address,
            "amount": bridge_tx.amount,
            "fee": bridge_tx.fee,
            "status": bridge_tx.status
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/transaction/{tx_hash}", response_model=BridgeResponse)
async def get_bridge_transaction(
    tx_hash: str,
    bridge_service: BridgeService = Depends()
) -> Dict:
    """Get bridge transaction status"""
    tx = bridge_service.get_transaction(tx_hash)
    if not tx:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )
        
    return {
        "tx_hash": tx.tx_hash,
        "from_chain": tx.from_chain.value,
        "to_chain": tx.to_chain.value,
        "from_address": tx.from_address,
        "to_address": tx.to_address,
        "amount": tx.amount,
        "fee": tx.fee,
        "status": tx.status
    }

@router.get("/rates/{chain}")
async def get_exchange_rate(
    chain: str,
    bridge_service: BridgeService = Depends()
) -> Dict:
    """Get current exchange rate"""
    try:
        chain_type = ChainType(chain)
        rate = bridge_service.get_exchange_rate(chain_type)
        
        return {
            "chain": chain,
            "rate": rate
        }
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid chain type"
        )

@router.get("/custody/status")
async def get_custody_status(
    custody_service: CustodyService = Depends()
) -> Dict:
    """Get custody service status"""
    return custody_service.get_status()

@router.get("/custody/balances")
async def get_custody_balances(
    custody_service: CustodyService = Depends()
) -> Dict:
    """Get custody wallet balances"""
    custody_service.update_balances()
    return custody_service.get_balances()

@router.get("/supported_chains")
async def get_supported_chains() -> Dict:
    """Get supported chains and info"""
    return {
        chain.value: {
            "name": chain.value.title(),
            "min_amount": min_amount,
            "confirmations": confirmations
        }
        for chain, (min_amount, confirmations) in {
            ChainType.ETHEREUM: (0.01, 12),
            ChainType.BINANCE: (0.1, 15),
            ChainType.POLYGON: (10, 128),
            ChainType.AVALANCHE: (1, 12)
        }.items()
    } 