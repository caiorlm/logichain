"""
API Server para conectar interface web com a blockchain
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Optional
import uvicorn
import logging
from decimal import Decimal
from datetime import datetime

from .. import blockchain
from ..core.transaction import Transaction

app = FastAPI(title="LogiChain API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
app.mount("/dashboard", StaticFiles(directory="../blockchain-wallet-html", html=True))

@app.get("/api/blockchain/stats")
async def get_blockchain_stats():
    """Retorna estatísticas da blockchain"""
    try:
        stats = {
            "token": {
                "symbol": "LOGI",
                "decimals": blockchain.token_config.DECIMALS,
                "max_supply": str(blockchain.token_config.MAX_SUPPLY),
                "current_supply": str(blockchain.consensus.get_current_supply()),
                "block_reward": str(blockchain.token_config.INITIAL_BLOCK_REWARD)
            },
            "blockchain": {
                "height": len(blockchain.consensus.chain) - 1,
                "difficulty": blockchain.consensus.current_difficulty,
                "last_block_time": blockchain.consensus.chain[-1].timestamp if blockchain.consensus.chain else 0,
                "target_block_time": blockchain.consensus.target_block_time,
                "pending_transactions": len(blockchain.tx_pool.transactions)
            },
            "network": {
                "connected_peers": len(blockchain.network.peers),
                "sync_status": blockchain.network.get_sync_status(),
                "node_version": "1.0.0"
            }
        }
        return {"success": True, "data": stats}
    except Exception as e:
        logging.error(f"Error getting blockchain stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/wallet/create")
async def create_wallet():
    """Cria nova carteira"""
    try:
        wallet = blockchain.Wallet(blockchain.security)
        wallet_info = wallet.create()
        return {"success": True, "data": wallet_info}
    except Exception as e:
        logging.error(f"Error creating wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/wallet/import")
async def import_wallet(mnemonic: str):
    """Importa carteira existente"""
    try:
        wallet = blockchain.Wallet(blockchain.security)
        wallet_info = wallet.import_from_mnemonic(mnemonic)
        return {"success": True, "data": wallet_info}
    except Exception as e:
        logging.error(f"Error importing wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/wallet/{address}/balance")
async def get_wallet_balance(address: str):
    """Retorna saldo da carteira"""
    try:
        wallet = blockchain.Wallet(blockchain.security)
        if not wallet.load(address):
            raise HTTPException(status_code=404, detail="Wallet not found")
            
        balance = wallet.get_balance()
        return {
            "success": True,
            "data": {
                "balance": str(balance),
                "address": address,
                "token": "LOGI"
            }
        }
    except Exception as e:
        logging.error(f"Error getting wallet balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transaction/send")
async def send_transaction(
    from_address: str,
    to_address: str,
    amount: str,
    private_key: str
):
    """Envia nova transação"""
    try:
        # Validar endereços
        if not blockchain.security.validate_address(from_address) or not blockchain.security.validate_address(to_address):
            raise HTTPException(status_code=400, detail="Invalid address format")
            
        # Converter amount para Decimal
        try:
            amount_decimal = Decimal(amount)
        except:
            raise HTTPException(status_code=400, detail="Invalid amount format")
            
        # Criar e assinar transação
        wallet = blockchain.Wallet(blockchain.security)
        if not wallet.load(from_address):
            raise HTTPException(status_code=404, detail="Wallet not found")
            
        tx = wallet.create_transaction(
            to_address=to_address,
            amount=amount_decimal,
            fee=blockchain.token_config.MIN_TX_FEE
        )
        
        if not tx:
            raise HTTPException(status_code=400, detail="Failed to create transaction")
            
        # Assinar transação
        tx.sign(private_key)
        
        # Validar e adicionar ao pool
        if not tx.verify():
            raise HTTPException(status_code=400, detail="Invalid transaction signature")
            
        if not blockchain.tx_pool.add_transaction(tx):
            raise HTTPException(status_code=400, detail="Failed to add transaction to pool")
            
        # Propagar para rede
        await blockchain.network.broadcast_transaction(tx)
        
        return {
            "success": True,
            "data": {
                "tx_hash": tx.tx_hash,
                "from": from_address,
                "to": to_address,
                "amount": str(amount_decimal),
                "fee": str(blockchain.token_config.MIN_TX_FEE),
                "timestamp": datetime.now().timestamp()
            }
        }
    except Exception as e:
        logging.error(f"Error sending transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transaction/{tx_hash}")
async def get_transaction(tx_hash: str):
    """Retorna detalhes de uma transação"""
    try:
        # Procurar no pool primeiro
        tx = blockchain.tx_pool.get_transaction(tx_hash)
        if tx:
            return {
                "success": True,
                "data": {
                    "status": "pending",
                    "transaction": tx.to_dict()
                }
            }
            
        # Procurar na blockchain
        tx = blockchain.consensus.get_transaction(tx_hash)
        if tx:
            return {
                "success": True,
                "data": {
                    "status": "confirmed",
                    "transaction": tx.to_dict(),
                    "confirmations": blockchain.consensus.get_confirmations(tx_hash)
                }
            }
        
        raise HTTPException(status_code=404, detail="Transaction not found")
    except Exception as e:
        logging.error(f"Error getting transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/blocks/latest")
async def get_latest_blocks(limit: int = 10):
    """Retorna últimos blocos"""
    try:
        blocks = []
        for block in reversed(blockchain.consensus.chain[-limit:]):
            blocks.append({
                "index": block.index,
                "hash": block.hash,
                "previous_hash": block.previous_hash,
                "timestamp": block.timestamp,
                "transactions": len(block.transactions),
                "miner": block.miner_address,
                "reward": str(block.consensus_reward)
            })
            
        return {"success": True, "data": blocks}
    except Exception as e:
        logging.error(f"Error getting latest blocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mining/status")
async def get_mining_status():
    """Retorna status da mineração"""
    try:
        stats = blockchain.consensus.get_mining_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logging.error(f"Error getting mining status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def start_server():
    """Inicia o servidor API"""
    # Inicializar blockchain
    blockchain.start()
    
    # Iniciar servidor
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    start_server() 