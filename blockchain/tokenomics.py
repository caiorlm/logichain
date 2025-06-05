"""
Tokenomics da LOGI - Nossa própria criptomoeda
"""

from decimal import Decimal
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class TokenConfig:
    """Configuração de tokenomics"""
    INITIAL_SUPPLY: int = 100_000_000
    MAX_SUPPLY: int = 1_000_000_000
    BLOCK_REWARD: int = 50
    HALVING_BLOCKS: int = 210_000
    INITIAL_DISTRIBUTION: Dict[str, float] = field(default_factory=lambda: {
        'team': 0.15,
        'advisors': 0.05,
        'foundation': 0.10,
        'ecosystem': 0.20,
        'public_sale': 0.50
    })
    
    # Taxa mínima de transação
    MIN_TX_FEE: Decimal = Decimal("0.0001")  # 0.0001 LOGI
    
    # Taxa máxima de transação
    MAX_TX_FEE: Decimal = Decimal("1.0")  # 1 LOGI
    
    # Decimais
    DECIMALS: int = 8
    
    def get_block_reward(self, block_height: int) -> Decimal:
        """Calcula recompensa do bloco baseado na altura"""
        halvings = block_height // self.HALVING_BLOCKS
        if halvings >= 64:  # Previne underflow
            return Decimal("0")
            
        reward = self.BLOCK_REWARD
        reward = reward / (2 ** halvings)
        
        if reward < Decimal("0.00000001"):
            reward = Decimal("0")
            
        return reward
        
    def validate_fee(self, fee: Decimal) -> bool:
        """Valida se taxa está dentro dos limites"""
        if fee < self.MIN_TX_FEE or fee > self.MAX_TX_FEE:
            return False
            
        decimal_places = abs(fee.as_tuple().exponent)
        return decimal_places <= self.DECIMALS
        
    def format_amount(self, amount: Decimal) -> str:
        """Formata valor com número correto de decimais"""
        return f"{amount:.{self.DECIMALS}f}" 