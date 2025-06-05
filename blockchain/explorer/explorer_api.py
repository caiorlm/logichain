"""
Blockchain explorer API.
Provides endpoints for querying blockchain data and statistics.
"""

from typing import Dict, List, Optional, Union, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time
from datetime import datetime, timedelta
from ..core.blockchain import Blockchain
from ..storage.database import BlockchainDB
from ..staking.staking_system import StakingSystem
from ..governance.dao import LogiChainDAO

app = FastAPI(title="LogiChain Explorer")

class ExplorerAPI:
    def __init__(
        self,
        blockchain: Blockchain,
        db: BlockchainDB,
        staking: StakingSystem,
        dao: LogiChainDAO
    ):
        self.blockchain = blockchain
        self.db = db
        self.staking = staking
        self.dao = dao
        
    async def get_blockchain_stats(self) -> Dict:
        """Get blockchain statistics"""
        try:
            latest_block = self.blockchain.get_latest_block()
            
            return {
                "height": len(self.blockchain.chain),
                "total_transactions": sum(
                    len(block.transactions) for block in self.blockchain.chain
                ),
                "latest_block": {
                    "hash": latest_block.hash,
                    "timestamp": latest_block.timestamp,
                    "transactions": len(latest_block.transactions)
                },
                "average_block_time": self._calculate_average_block_time(),
                "current_difficulty": self.blockchain.difficulty,
                "total_supply": self.blockchain.current_supply,
                "active_nodes": len(self.blockchain.peers)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_block(self, block_hash: str) -> Dict:
        """Get block details"""
        try:
            block = self.blockchain.get_block_by_hash(block_hash)
            if not block:
                raise HTTPException(status_code=404, detail="Block not found")
                
            return {
                "hash": block.hash,
                "height": block.index,
                "timestamp": block.timestamp,
                "previous_hash": block.previous_hash,
                "transactions": [
                    self._format_transaction(tx) for tx in block.transactions
                ],
                "miner": block.miner_address,
                "difficulty": block.difficulty,
                "size": len(str(block.transactions))
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_transaction(self, tx_hash: str) -> Dict:
        """Get transaction details"""
        try:
            tx = self.blockchain.get_transaction(tx_hash)
            if not tx:
                raise HTTPException(status_code=404, detail="Transaction not found")
                
            return self._format_transaction(tx)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_address(self, address: str) -> Dict:
        """Get address details and history"""
        try:
            # Get basic info
            balance = self.blockchain.get_balance(address)
            transactions = self.blockchain.get_address_transactions(address)
            
            # Get stake info if exists
            stake = self.staking.get_stake_info(address)
            
            # Get governance info
            governance = {
                "voting_power": self.dao.get_voter_power(address),
                "proposals_created": self._count_proposals_by_address(address),
                "votes_cast": self._count_votes_by_address(address)
            }
            
            return {
                "address": address,
                "balance": balance,
                "transaction_count": len(transactions),
                "transactions": [
                    self._format_transaction(tx) for tx in transactions[:100]  # Last 100
                ],
                "stake": stake,
                "governance": governance
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_staking_stats(self) -> Dict:
        """Get staking statistics"""
        try:
            return {
                "total_staked": self.staking.get_total_staked(),
                "active_stakes": len(self.staking.stakes),
                "total_rewards_distributed": self._calculate_total_rewards(),
                "average_apy": self._calculate_average_apy()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_governance_stats(self) -> Dict:
        """Get governance statistics"""
        try:
            active_proposals = [
                p for p in self.dao.proposals.values()
                if p["status"] == "active"
            ]
            
            return {
                "total_proposals": len(self.dao.proposals),
                "active_proposals": len(active_proposals),
                "total_voters": len(self.dao.stake_data),
                "total_votes_cast": sum(
                    len(votes) for votes in self.dao.votes.values()
                )
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def _format_transaction(self, tx: Any) -> Dict:
        """Format transaction for API response"""
        return {
            "hash": tx.hash,
            "from": tx.from_address,
            "to": tx.to_address,
            "amount": tx.amount,
            "timestamp": tx.timestamp,
            "block_height": tx.block_height,
            "confirmations": len(self.blockchain.chain) - tx.block_height,
            "fee": tx.fee,
            "data": tx.data
        }
        
    def _calculate_average_block_time(self) -> float:
        """Calculate average block time over last 100 blocks"""
        if len(self.blockchain.chain) < 2:
            return 0
            
        recent_blocks = self.blockchain.chain[-100:]
        times = [
            b2.timestamp - b1.timestamp
            for b1, b2 in zip(recent_blocks[:-1], recent_blocks[1:])
        ]
        
        return sum(times) / len(times) if times else 0
        
    def _calculate_total_rewards(self) -> float:
        """Calculate total staking rewards distributed"""
        return sum(
            stake.rewards_claimed
            for stake in self.staking.stakes.values()
        )
        
    def _calculate_average_apy(self) -> float:
        """Calculate average APY across all stakes"""
        if not self.staking.stakes:
            return 0
            
        apys = []
        for stake in self.staking.stakes.values():
            if stake.status == "active" and stake.start_time < time.time() - 86400:
                days = (time.time() - stake.start_time) / 86400
                apy = (stake.rewards_claimed / stake.amount) * (365 / days)
                apys.append(apy)
                
        return sum(apys) / len(apys) if apys else 0
        
    def _count_proposals_by_address(self, address: str) -> int:
        """Count proposals created by address"""
        return sum(
            1 for p in self.dao.proposals.values()
            if p["proposer"] == address
        )
        
    def _count_votes_by_address(self, address: str) -> int:
        """Count votes cast by address"""
        return sum(
            1 for votes in self.dao.votes.values()
            for vote in votes
            if vote.voter == address
        )

# API Routes
@app.get("/stats")
async def get_stats(explorer: ExplorerAPI):
    return await explorer.get_blockchain_stats()

@app.get("/blocks/{block_hash}")
async def get_block(block_hash: str, explorer: ExplorerAPI):
    return await explorer.get_block(block_hash)

@app.get("/transactions/{tx_hash}")
async def get_transaction(tx_hash: str, explorer: ExplorerAPI):
    return await explorer.get_transaction(tx_hash)

@app.get("/address/{address}")
async def get_address(address: str, explorer: ExplorerAPI):
    return await explorer.get_address(address)

@app.get("/staking")
async def get_staking_stats(explorer: ExplorerAPI):
    return await explorer.get_staking_stats()

@app.get("/governance")
async def get_governance_stats(explorer: ExplorerAPI):
    return await explorer.get_governance_stats() 