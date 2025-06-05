from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Any
import json

from ..core.blockchain import Blockchain
from ..core.key_manager import KeyManager
from ..core.transaction import Transaction

app = FastAPI()
blockchain = Blockchain()
key_manager = KeyManager()

@app.post("/keys/generate")
async def generate_keys() -> Dict[str, str]:
    """
    Generates a new key pair and returns the address.
    """
    try:
        private_key, public_key = key_manager.generate_key_pair()
        
        # Generate address from public key
        address = blockchain.generate_address(public_key)
        
        # Save keys
        key_manager.save_keys(address, private_key, public_key)
        
        return {
            "address": address,
            "public_key": public_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/keys/{address}/public")
async def get_public_key(address: str) -> Dict[str, str]:
    """
    Returns the public key for an address.
    """
    keys = key_manager.load_keys(address)
    if not keys:
        raise HTTPException(status_code=404, detail="Address not found")
        
    return {
        "address": address,
        "public_key": keys[1]
    }

@app.post("/sign")
async def sign_payload(
    address: str = Body(...),
    payload: Dict[str, Any] = Body(...)
) -> Dict[str, str]:
    """
    Signs any payload with the private key of an address.
    """
    keys = key_manager.load_keys(address)
    if not keys:
        raise HTTPException(status_code=404, detail="Address not found")
        
    message = json.dumps(payload, sort_keys=True)
    signature = key_manager.sign_message(keys[0], message)
    
    if not signature:
        raise HTTPException(status_code=500, detail="Failed to sign message")
        
    return {
        "address": address,
        "signature": signature,
        "payload": payload
    }

@app.post("/verify")
async def verify_signature(
    address: str = Body(...),
    payload: Dict[str, Any] = Body(...),
    signature: str = Body(...)
) -> Dict[str, bool]:
    """
    Verifies a signature against a payload.
    """
    keys = key_manager.load_keys(address)
    if not keys:
        raise HTTPException(status_code=404, detail="Address not found")
        
    message = json.dumps(payload, sort_keys=True)
    is_valid = key_manager.verify_signature(keys[1], message, signature)
    
    return {
        "address": address,
        "is_valid": is_valid
    }

@app.get("/balance/{address}")
async def get_balance(address: str) -> Dict[str, float]:
    """
    Returns the current balance of an address.
    """
    balance = blockchain.get_balance(address)
    pending_balance = blockchain.get_pending_balance(address)
    
    return {
        "address": address,
        "confirmed_balance": balance,
        "pending_balance": pending_balance,
        "total_balance": balance + pending_balance
    }

@app.post("/transactions/create")
async def create_transaction(
    from_address: str = Body(...),
    to_address: str = Body(...),
    amount: float = Body(...),
    data: Dict[str, Any] = Body(None)
) -> Dict[str, Any]:
    """
    Creates and signs a new transaction.
    """
    # Load sender's keys
    keys = key_manager.load_keys(from_address)
    if not keys:
        raise HTTPException(status_code=404, detail="Sender address not found")
        
    # Check balance
    balance = blockchain.get_balance(from_address)
    if balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
        
    # Create transaction
    tx = Transaction(
        from_address=from_address,
        to_address=to_address,
        amount=amount,
        nonce=blockchain.get_nonce(from_address),
        data=data
    )
    
    # Sign transaction
    tx_dict = tx.to_dict()
    signature = key_manager.sign_transaction(keys[0], tx_dict)
    tx.signature = signature
    
    # Add to pool
    if not blockchain.add_transaction_to_pool(tx):
        raise HTTPException(
            status_code=400,
            detail="Failed to add transaction to pool"
        )
        
    return tx.to_dict()

@app.get("/chain/status")
async def get_chain_status() -> Dict[str, Any]:
    """
    Returns current blockchain status.
    """
    latest_block = blockchain.chain[-1]
    
    return {
        "height": len(blockchain.chain),
        "latest_block_hash": latest_block.hash,
        "latest_block_time": latest_block.timestamp.isoformat(),
        "difficulty": blockchain.difficulty,
        "pending_transactions": len(blockchain.transaction_pool.transactions),
        "total_supply": blockchain.current_supply
    }

@app.post("/mining/start")
async def start_mining(address: str = Body(...)) -> Dict[str, Any]:
    """
    Starts mining blocks with rewards going to address.
    """
    if not key_manager.load_keys(address):
        raise HTTPException(status_code=404, detail="Address not found")
        
    if blockchain.start_mining(address):
        return {
            "status": "started",
            "miner_address": address
        }
    else:
        raise HTTPException(status_code=400, detail="Failed to start mining")

@app.post("/mining/stop")
async def stop_mining() -> Dict[str, str]:
    """
    Stops mining blocks.
    """
    blockchain.stop_mining()
    return {"status": "stopped"} 