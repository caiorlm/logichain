from __future__ import annotations
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import logging
from decimal import Decimal
import time

from ..core.blockchain import Blockchain
from ..core.transaction import Transaction
from ..wallet.wallet import Wallet
from ..network.p2p import P2PNetwork
from ..integration.system_integrator import SystemIntegrator
from ..oracle.oracle_system import OracleData
from ..bridge.bridge_system import BridgeTransaction, ChainType
from ..scaling.layer2 import Layer2Transaction, Layer2Type

# API Models
class TransactionRequest(BaseModel):
    to_address: str
    amount: Decimal = Field(gt=0)
    gas_price: int = Field(gt=0)
    gas_limit: int = Field(gt=21000)
    data: Optional[Dict] = None
    chain_id: int = Field(gt=0)

class WalletRequest(BaseModel):
    password: str
    mnemonic: Optional[str] = None

class BlockResponse(BaseModel):
    hash: str
    previous_hash: str
    timestamp: int
    transactions: List[Dict[str, Any]]
    nonce: int
    difficulty: int
    merkle_root: str

class TransactionResponse(BaseModel):
    hash: str
    from_address: str
    to_address: str
    amount: int
    nonce: int
    gas_price: int
    gas_limit: int
    data: Optional[str]
    timestamp: int
    signature: Optional[str]

class Layer2TransactionRequest(BaseModel):
    to_address: str
    amount: Decimal
    l2_type: str = "optimistic_rollup"

class BridgeTransactionRequest(BaseModel):
    to_address: str
    amount: Decimal
    from_chain: str
    to_chain: str
    token_address: str
    chain_id: int = Field(gt=0)

class OracleDataRequest(BaseModel):
    value: Any
    source: str
    validator_signatures: List[str] = []

# API Setup
app = FastAPI(title="Blockchain API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get blockchain instance
def get_blockchain() -> Blockchain:
    return app.state.blockchain

def get_p2p() -> P2PNetwork:
    return app.state.p2p

def get_system() -> SystemIntegrator:
    return app.state.system

def get_wallet() -> Wallet:
    return app.state.wallet

@app.on_event("startup")
async def startup_event():
    """Initialize blockchain and P2P network on startup."""
    if not hasattr(app.state, "blockchain"):
        app.state.blockchain = Blockchain()
        app.state.wallet = Wallet()
        app.state.p2p = P2PNetwork(app.state.blockchain)
    logging.info("API started")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    if hasattr(app.state, "p2p"):
        await app.state.p2p.stop()
    logging.info("API stopped")

# Wallet Endpoints
@app.post("/wallet/create")
async def create_wallet(
    request: WalletRequest,
    wallet: Wallet = Depends(get_wallet)
) -> Dict[str, str]:
    """Creates a new wallet."""
    try:
        result = wallet.create_new(request.password)
        return {
            "status": "success",
            "address": result["address"],
            "mnemonic": result["mnemonic"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/wallet/load")
async def load_wallet(
    request: WalletRequest,
    wallet: Wallet = Depends(get_wallet)
) -> Dict[str, str]:
    """Loads a wallet from mnemonic."""
    try:
        if not request.mnemonic:
            raise ValueError("Mnemonic is required")
            
        address = wallet.load_from_mnemonic(request.mnemonic, request.password)
        return {
            "status": "success",
            "address": address
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/wallet/balance/{address}")
async def get_balance(
    address: str,
    blockchain: Blockchain = Depends(get_blockchain)
) -> Dict[str, int]:
    """Gets wallet balance."""
    try:
        balance = blockchain.get_balance(address)
        return {
            "address": address,
            "balance": balance
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Transaction Endpoints
@app.post("/transactions/create")
async def create_transaction(
    request: TransactionRequest,
    wallet: Wallet = Depends(get_wallet),
    blockchain: Blockchain = Depends(get_blockchain),
    p2p: P2PNetwork = Depends(get_p2p)
) -> Dict[str, str]:
    """Creates and broadcasts a new transaction."""
    try:
        # Create transaction
        nonce = blockchain.get_nonce(wallet.get_address())
        tx = Transaction(
            from_address=wallet.get_address(),
            to_address=request.to_address,
            amount=request.amount,
            nonce=nonce,
            chain_id=request.chain_id,
            gas_price=request.gas_price,
            gas_limit=request.gas_limit,
            data=request.data,
            fee=Decimal(str(request.gas_price * request.gas_limit)) / Decimal('1000000000')
        )
        
        # Sign transaction
        tx.sign(wallet.account.key.hex())
        
        # Add to blockchain
        if blockchain.add_transaction(tx):
            # Broadcast to network
            await p2p._broadcast_transaction(tx)
            
            return {
                "status": "success",
                "hash": tx.hash
            }
        else:
            raise ValueError("Transaction rejected")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/transactions/{tx_hash}")
async def get_transaction(
    tx_hash: str,
    blockchain: Blockchain = Depends(get_blockchain)
) -> TransactionResponse:
    """Gets transaction details."""
    # Search in pending transactions
    if tx_hash in blockchain.transaction_pool:
        tx = blockchain.transaction_pool[tx_hash]
        return TransactionResponse(**tx.to_dict())
        
    # Search in blocks
    for block in reversed(blockchain.chain):
        for tx_dict in block.transactions:
            tx = Transaction.from_dict(tx_dict)
            if tx.hash == tx_hash:
                return TransactionResponse(**tx.to_dict())
                
    raise HTTPException(status_code=404, detail="Transaction not found")

@app.get("/transactions/pending")
async def get_pending_transactions(
    blockchain: Blockchain = Depends(get_blockchain)
) -> List[TransactionResponse]:
    """Gets all pending transactions."""
    return [
        TransactionResponse(**tx.to_dict())
        for tx in blockchain.transaction_pool.values()
    ]

# Block Endpoints
@app.get("/blocks/latest")
async def get_latest_block(
    blockchain: Blockchain = Depends(get_blockchain)
) -> BlockResponse:
    """Gets the latest block."""
    if not blockchain.chain:
        raise HTTPException(status_code=404, detail="No blocks found")
        
    latest = blockchain.chain[-1]
    return BlockResponse(**latest.to_dict())

@app.get("/blocks/{block_hash}")
async def get_block(
    block_hash: str,
    blockchain: Blockchain = Depends(get_blockchain)
) -> BlockResponse:
    """Gets block by hash."""
    for block in blockchain.chain:
        if block.hash == block_hash:
            return BlockResponse(**block.to_dict())
            
    raise HTTPException(status_code=404, detail="Block not found")

@app.get("/blocks")
async def get_blocks(
    start: int = 0,
    limit: int = 10,
    blockchain: Blockchain = Depends(get_blockchain)
) -> List[BlockResponse]:
    """Gets a range of blocks."""
    end = min(start + limit, len(blockchain.chain))
    return [
        BlockResponse(**block.to_dict())
        for block in blockchain.chain[start:end]
    ]

# Mining Endpoints
@app.post("/mining/start")
async def start_mining(
    blockchain: Blockchain = Depends(get_blockchain),
    wallet: Wallet = Depends(get_wallet)
) -> Dict[str, str]:
    """Starts mining blocks."""
    try:
        if blockchain.start_mining(wallet.get_address()):
            return {"status": "Mining started"}
        else:
            raise ValueError("Mining already in progress")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/mining/stop")
async def stop_mining(
    blockchain: Blockchain = Depends(get_blockchain)
) -> Dict[str, str]:
    """Stops mining blocks."""
    blockchain.stop_mining()
    return {"status": "Mining stopped"}

# Network Endpoints
@app.get("/network/peers")
async def get_peers(
    p2p: P2PNetwork = Depends(get_p2p)
) -> Dict[str, List[str]]:
    """Gets list of connected peers."""
    return {
        "peers": list(p2p.peers)
    }

@app.post("/network/peers")
async def add_peer(
    address: str,
    p2p: P2PNetwork = Depends(get_p2p)
) -> Dict[str, str]:
    """Adds a new peer."""
    try:
        p2p.add_peer(address)
        return {"status": "Peer added"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Layer 2 endpoints
@app.post("/l2/transactions/create")
async def create_l2_transaction(
    request: Layer2TransactionRequest,
    wallet: Wallet = Depends(get_wallet),
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, str]:
    """Creates a Layer 2 transaction."""
    try:
        # Create L1 transaction with L2 metadata
        nonce = system.blockchain.get_nonce(wallet.get_address())
        tx = Transaction(
            from_address=wallet.get_address(),
            to_address=request.to_address,
            amount=request.amount,
            nonce=nonce,
            gas_price=1,  # L2 transactions have minimal gas
            gas_limit=21000,
            data={"layer": "l2", "l2_type": request.l2_type}
        )
        
        # Sign transaction
        tx.sign(wallet.account.key.hex())
        
        # Process through system integrator
        if await system.process_transaction(tx):
            return {
                "status": "success",
                "hash": tx.hash
            }
        else:
            raise ValueError("Transaction rejected")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/l2/status")
async def get_l2_status(
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, Any]:
    """Gets Layer 2 system status."""
    try:
        status = await system.get_system_status()
        return status["layer2"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Bridge endpoints
@app.post("/bridge/transactions/create")
async def create_bridge_transaction(
    request: BridgeTransactionRequest,
    wallet: Wallet = Depends(get_wallet),
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, str]:
    """Creates a cross-chain bridge transaction."""
    try:
        # Create transaction with bridge metadata
        nonce = system.blockchain.get_nonce(wallet.get_address())
        tx = Transaction(
            from_address=wallet.get_address(),
            to_address=request.to_address,
            amount=request.amount,
            nonce=nonce,
            chain_id=request.chain_id,
            gas_price=1,
            gas_limit=21000,
            fee=Decimal('0.000021'),
            data={
                "from_chain": request.from_chain,
                "to_chain": request.to_chain,
                "token_address": request.token_address
            }
        )
        
        # Sign transaction
        tx.sign(wallet.account.key.hex())
        
        # Process through system integrator
        if await system.process_transaction(tx):
            return {
                "status": "success",
                "hash": tx.hash
            }
        else:
            raise ValueError("Transaction rejected")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/bridge/status")
async def get_bridge_status(
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, Any]:
    """Gets bridge system status."""
    try:
        status = await system.get_system_status()
        return status["bridge"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Oracle endpoints
@app.post("/oracle/data/submit")
async def submit_oracle_data(
    request: OracleDataRequest,
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, str]:
    """Submits data to the oracle system."""
    try:
        oracle_data = OracleData(
            timestamp=int(time.time()),
            value=request.value,
            source=request.source,
            signature="",  # Will be filled by validators
            validator_signatures=request.validator_signatures
        )
        
        if await system.oracle_system.submit_data("price", oracle_data):
            return {
                "status": "success",
                "timestamp": oracle_data.timestamp
            }
        else:
            raise ValueError("Data rejected")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/oracle/data/{feed_type}")
async def get_oracle_data(
    feed_type: str,
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, Any]:
    """Gets latest oracle data for a feed type."""
    try:
        data = system.oracle_system.get_latest_data(feed_type)
        if data:
            return {
                "timestamp": data.timestamp,
                "value": data.value,
                "source": data.source,
                "validator_count": len(data.validator_signatures)
            }
        else:
            raise HTTPException(status_code=404, detail="No data found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/status")
async def get_system_status(
    system: SystemIntegrator = Depends(get_system)
) -> Dict[str, Any]:
    """Gets status of all systems."""
    try:
        return await system.get_system_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start_api(
    host: str = "0.0.0.0",
    port: int = 5000,
    blockchain: Optional[Blockchain] = None,
    system_integrator: Optional[SystemIntegrator] = None
):
    """Starts the REST API server."""
    if blockchain:
        app.state.blockchain = blockchain
    if system_integrator:
        app.state.system = system_integrator
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    ) 