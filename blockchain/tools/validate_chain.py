"""
LogiChain Validation Tool
Validates blockchain integrity and consistency
"""

import hashlib
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from ..core.blockchain import Blockchain
from ..storage.database import BlockchainDB
from ..crypto.signature import SignatureManager

@dataclass
class ValidationResult:
    """Results of chain validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False
        
    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)

class ChainValidator:
    """Validates blockchain consistency and integrity"""
    
    # Maximum supply of tokens
    MAX_SUPPLY = 21_000_000
    
    # Block reward halving interval (blocks)
    HALVING_INTERVAL = 210_000
    
    # Initial block reward
    INITIAL_REWARD = 50
    
    def __init__(
        self,
        blockchain: Blockchain,
        db: BlockchainDB
    ):
        self.blockchain = blockchain
        self.db = db
        
    def validate_chain(self) -> ValidationResult:
        """Perform complete chain validation"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        # Validate block chain
        self._validate_block_chain(result)
        
        # Validate total supply
        self._validate_total_supply(result)
        
        # Validate signatures
        self._validate_signatures(result)
        
        # Validate UTXO set
        self._validate_utxo_set(result)
        
        # Validate account balances
        self._validate_account_balances(result)
        
        # Validate stakes
        self._validate_stakes(result)
        
        # Validate reputation scores
        self._validate_reputation(result)
        
        return result
        
    def _validate_block_chain(
        self,
        result: ValidationResult
    ):
        """Validate block chain integrity"""
        # Get all blocks
        blocks = self.blockchain.get_all_blocks()
        
        # Check genesis block
        if not blocks:
            result.add_error("Empty blockchain")
            return
            
        # Validate block sequence
        prev_hash = blocks[0].hash
        for block in blocks[1:]:
            # Verify previous hash
            if block.previous_hash != prev_hash:
                result.add_error(
                    f"Invalid previous hash at height {block.height}"
                )
                
            # Verify block hash
            if not self._verify_block_hash(block):
                result.add_error(
                    f"Invalid block hash at height {block.height}"
                )
                
            # Update previous hash
            prev_hash = block.hash
            
    def _validate_total_supply(
        self,
        result: ValidationResult
    ):
        """Validate total token supply"""
        # Calculate total supply
        total_supply = self._calculate_total_supply()
        
        # Verify against max supply
        if total_supply > self.MAX_SUPPLY:
            result.add_error(
                f"Total supply {total_supply} exceeds "
                f"maximum {self.MAX_SUPPLY}"
            )
            
        # Verify mining rewards
        self._validate_mining_rewards(result)
        
    def _validate_signatures(
        self,
        result: ValidationResult
    ):
        """Validate transaction and block signatures"""
        # Get all blocks
        blocks = self.blockchain.get_all_blocks()
        
        for block in blocks:
            # Validate block signature
            if not self._verify_block_signature(block):
                result.add_error(
                    f"Invalid block signature at height {block.height}"
                )
                
            # Validate transaction signatures
            for tx in block.transactions:
                if not self._verify_transaction_signature(tx):
                    result.add_error(
                        f"Invalid transaction signature {tx.id} "
                        f"in block {block.height}"
                    )
                    
    def _validate_utxo_set(
        self,
        result: ValidationResult
    ):
        """Validate UTXO set consistency"""
        # Get current UTXO set
        utxo_set = self.db.get_utxo_set()
        
        # Calculate UTXO set from chain
        calculated_utxo = self._calculate_utxo_set()
        
        # Compare sets
        if utxo_set != calculated_utxo:
            result.add_error("UTXO set mismatch")
            
        # Verify no double spends
        spent_outputs: Set[Tuple[str, int]] = set()
        for block in self.blockchain.get_all_blocks():
            for tx in block.transactions:
                for input in tx.inputs:
                    output_ref = (input.txid, input.vout)
                    if output_ref in spent_outputs:
                        result.add_error(
                            f"Double spend detected: {input.txid}:{input.vout}"
                        )
                    spent_outputs.add(output_ref)
                    
    def _validate_account_balances(
        self,
        result: ValidationResult
    ):
        """Validate account balance consistency"""
        # Get current account balances
        accounts = self.db.get_accounts()
        
        # Calculate balances from chain
        calculated_balances = self._calculate_account_balances()
        
        # Compare balances
        for address, account in accounts.items():
            if address not in calculated_balances:
                result.add_error(f"Invalid account: {address}")
                continue
                
            if account["balance"] != calculated_balances[address]:
                result.add_error(
                    f"Balance mismatch for {address}: "
                    f"stored={account['balance']}, "
                    f"calculated={calculated_balances[address]}"
                )
                
    def _validate_stakes(
        self,
        result: ValidationResult
    ):
        """Validate staking consistency"""
        # Get current stakes
        stakes = self.db.get_stakes()
        
        # Verify stake amounts
        for stake_id, stake in stakes.items():
            # Verify stake amount
            if stake["amount"] <= 0:
                result.add_error(
                    f"Invalid stake amount for {stake_id}"
                )
                
            # Verify stake type
            if stake["type"] not in {"validator", "delegator"}:
                result.add_error(
                    f"Invalid stake type for {stake_id}"
                )
                
            # Verify stake balance
            address = stake.get("address")
            if not self._verify_stake_balance(
                address,
                stake["amount"]
            ):
                result.add_error(
                    f"Insufficient balance for stake {stake_id}"
                )
                
    def _validate_reputation(
        self,
        result: ValidationResult
    ):
        """Validate reputation score consistency"""
        # Get reputation scores
        scores = self.db.get_reputation_scores()
        
        # Verify score range
        for node_id, score in scores.items():
            if not (0 <= score <= 1):
                result.add_error(
                    f"Invalid reputation score for {node_id}: {score}"
                )
                
        # Verify validator scores
        validators = self.db.get_validators()
        for validator in validators.values():
            if validator["node_id"] not in scores:
                result.add_error(
                    f"Missing reputation score for validator "
                    f"{validator['node_id']}"
                )
                
    def _verify_block_hash(self, block) -> bool:
        """Verify block hash is valid"""
        calculated_hash = hashlib.sha256(
            str(block.get_hash_data()).encode()
        ).hexdigest()
        return calculated_hash == block.hash
        
    def _verify_block_signature(self, block) -> bool:
        """Verify block signature"""
        try:
            return SignatureManager.verify_block(
                block.validator_key,
                block.get_signing_data(),
                block.signature
            )
        except Exception:
            return False
            
    def _verify_transaction_signature(self, tx) -> bool:
        """Verify transaction signature"""
        try:
            return SignatureManager.verify_transaction(
                tx.sender_key,
                tx.get_signing_data(),
                tx.signature
            )
        except Exception:
            return False
            
    def _calculate_total_supply(self) -> int:
        """Calculate total token supply"""
        total = 0
        
        # Add account balances
        accounts = self.db.get_accounts()
        for account in accounts.values():
            total += account["balance"]
            
        # Add UTXO amounts
        utxo_set = self.db.get_utxo_set()
        for utxo in utxo_set.values():
            total += utxo["amount"]
            
        return total
        
    def _validate_mining_rewards(
        self,
        result: ValidationResult
    ):
        """Validate mining reward distribution"""
        current_reward = self.INITIAL_REWARD
        halvings = 0
        
        for block in self.blockchain.get_all_blocks():
            # Check reward amount
            if block.reward > current_reward:
                result.add_error(
                    f"Excessive block reward at height {block.height}"
                )
                
            # Check for halving
            if block.height > 0 and block.height % self.HALVING_INTERVAL == 0:
                halvings += 1
                current_reward = self.INITIAL_REWARD / (2 ** halvings)
                
    def _calculate_utxo_set(self) -> Dict:
        """Calculate UTXO set from chain"""
        utxo_set = {}
        spent_outputs = set()
        
        # Process all transactions
        for block in self.blockchain.get_all_blocks():
            for tx in block.transactions:
                # Remove spent outputs
                for input in tx.inputs:
                    spent_outputs.add((input.txid, input.vout))
                    
                # Add new outputs
                for i, output in enumerate(tx.outputs):
                    output_ref = (tx.id, i)
                    if output_ref not in spent_outputs:
                        utxo_set[f"{tx.id}:{i}"] = {
                            "txid": tx.id,
                            "vout": i,
                            "amount": output.amount,
                            "address": output.address
                        }
                        
        return utxo_set
        
    def _calculate_account_balances(self) -> Dict[str, int]:
        """Calculate account balances from chain"""
        balances = {}
        
        # Process all transactions
        for block in self.blockchain.get_all_blocks():
            for tx in block.transactions:
                # Deduct input amounts
                for input in tx.inputs:
                    from_addr = input.address
                    if from_addr not in balances:
                        balances[from_addr] = 0
                    balances[from_addr] -= input.amount
                    
                # Add output amounts
                for output in tx.outputs:
                    to_addr = output.address
                    if to_addr not in balances:
                        balances[to_addr] = 0
                    balances[to_addr] += output.amount
                    
            # Add block reward
            miner = block.miner_address
            if miner not in balances:
                balances[miner] = 0
            balances[miner] += block.reward
            
        return balances
        
    def _verify_stake_balance(
        self,
        address: str,
        amount: int
    ) -> bool:
        """Verify address has sufficient balance for stake"""
        accounts = self.db.get_accounts()
        if address not in accounts:
            return False
        return accounts[address]["balance"] >= amount 