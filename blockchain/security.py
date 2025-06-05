"""
Módulo de segurança e validação da blockchain
"""

import hashlib
import hmac
import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from .block import Block
from .wallet import Wallet
from .contract import DeliveryContract, TokenConversionContract
from .genesis import GENESIS_HASH, verify_genesis_block

@dataclass
class SecurityConfig:
    """Configurações de segurança"""
    
    # Tamanho máximo de bloco
    max_block_size: int = 2_000_000  # 2MB
    
    # Intervalo entre blocos
    block_time_window: int = 300  # 5 minutos
    
    # Dificuldade inicial
    initial_difficulty: int = 4
    
    # Ajuste de dificuldade
    difficulty_adjustment_blocks: int = 2016
    
    # Tamanho máximo de transação
    max_tx_size: int = 100_000  # 100KB
    
    # Número máximo de transações por bloco
    max_txs_per_block: int = 10_000
    
    # Tamanho mínimo de chave
    min_key_size: int = 2048
    
    # Número máximo de tentativas de mineração
    max_mining_attempts: int = 1_000_000
    
    # Tempo máximo de mineração
    max_mining_time: int = 3600  # 1 hora
    
    # Configurações de rede
    max_peers: int = 50
    max_connections_per_ip: int = 10
    connection_timeout: int = 30
    sync_timeout: int = 300
    
    # Configurações de carteira
    wallet_path: Optional[str] = None
    keystore_path: Optional[str] = None

class ChainValidator:
    """
    Validador da blockchain
    Garante integridade, imutabilidade e segurança
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.used_nonces: Set[str] = set()  # Para proteção anti-replay
        self.block_timestamps: List[int] = []  # Para validação de timestamp
        self.total_supply: Decimal = Decimal('0')
        
    def validate_block(
        self,
        block: Block,
        previous_block: Optional[Block] = None
    ) -> bool:
        """
        Valida bloco completo
        Todas as regras devem passar
        """
        try:
            # Se é bloco gênesis
            if not previous_block:
                if not verify_genesis_block(block):
                    return False
                return True
                
            # Validações básicas
            if not self._validate_block_basics(block, previous_block):
                return False
                
            # Validações de timestamp
            if not self._validate_block_timestamp(block, previous_block):
                return False
                
            # Validações de tamanho
            if not self._validate_block_size(block):
                return False
                
            # Validações de transações
            if not self._validate_block_transactions(block):
                return False
                
            # Validações de supply e reward
            if not self._validate_block_supply(block):
                return False
                
            # Validações específicas de rewards
            if not self._validate_block_rewards(block):
                return False
                
            # Validações de hash e proof-of-work
            if not self._validate_block_hash(block, previous_block):
                return False
                
            return True
            
        except Exception as e:
            # Qualquer erro não previsto invalida o bloco
            return False
            
    def _validate_block_basics(
        self,
        block: Block,
        previous_block: Block
    ) -> bool:
        """Validações básicas do bloco"""
        
        # Verifica previous_hash
        if block.previous_hash != previous_block.hash:
            return False
            
        # Verifica campos obrigatórios
        required = {
            'timestamp', 'start_coords', 'end_coords',
            'delivery_hash', 'previous_hash', 'contract_id', 'hash'
        }
        if not all(hasattr(block, field) for field in required):
            return False
            
        # Verifica tipos de dados
        if not isinstance(block.timestamp, (int, float)):
            return False
            
        if not isinstance(block.start_coords, tuple) or len(block.start_coords) != 2:
            return False
            
        if not isinstance(block.end_coords, tuple) or len(block.end_coords) != 2:
            return False
            
        return True
        
    def _validate_block_timestamp(
        self,
        block: Block,
        previous_block: Block
    ) -> bool:
        """Validações de timestamp"""
        
        current_time = int(time.time())
        
        # Não pode ser do futuro
        if block.timestamp > current_time + self.config.max_mining_time:
            return False
            
        # Não pode ser anterior ao bloco anterior
        if block.timestamp <= previous_block.timestamp:
            return False
            
        # Média móvel de timestamps para evitar manipulação
        self.block_timestamps.append(block.timestamp)
        if len(self.block_timestamps) > 11:
            self.block_timestamps.pop(0)
            
        if len(self.block_timestamps) >= 11:
            median_time = sorted(self.block_timestamps)[5]  # Mediana
            if block.timestamp <= median_time:
                return False
                
        return True
        
    def _validate_block_size(self, block: Block) -> bool:
        """Validações de tamanho do bloco"""
        
        # Tamanho total do bloco
        block_size = len(str(block.to_dict()).encode())
        if block_size > self.config.max_block_size:
            return False
            
        # Número de transações
        if hasattr(block, 'transactions'):
            if len(block.transactions) > self.config.max_txs_per_block:
                return False
                
        return True
        
    def _validate_block_transactions(self, block: Block) -> bool:
        """Validações das transações do bloco"""
        
        if not hasattr(block, 'transactions'):
            return True  # Bloco sem transações é válido
            
        used_nonces_in_block = set()
        
        for tx in block.transactions:
            # Valida assinatura
            if not self._validate_transaction_signature(tx):
                return False
                
            # Valida nonce (anti-replay)
            if not self._validate_transaction_nonce(tx, used_nonces_in_block):
                return False
                
            # Valida saldos
            if not self._validate_transaction_balance(tx):
                return False
                
        return True
        
    def _validate_transaction_signature(self, transaction: Dict) -> bool:
        """Valida assinatura de transação"""
        
        try:
            # Remove signature para verificar
            signature = bytes.fromhex(transaction['signature'])
            tx_data = {k:v for k,v in transaction.items() if k != 'signature'}
            tx_string = json.dumps(tx_data, sort_keys=True)
            
            # Recupera chave pública
            from_address = transaction['from_address']
            wallet = Wallet.get_wallet_by_address(from_address)
            if not wallet:
                return False
                
            # Verifica assinatura
            return wallet.verify_signature(signature, tx_string.encode())
            
        except:
            return False
            
    def _validate_transaction_nonce(
        self,
        transaction: Dict,
        used_nonces_in_block: Set[str]
    ) -> bool:
        """Valida nonce da transação (anti-replay)"""
        
        nonce = transaction.get('nonce')
        if not nonce:
            return False
            
        # Nonce já usado no bloco
        if nonce in used_nonces_in_block:
            return False
            
        # Nonce já usado globalmente
        if nonce in self.used_nonces:
            return False
            
        # Nonce fora da janela
        current_window = int(time.time() / self.config.max_connections_per_ip)
        tx_window = int(transaction['timestamp'] / self.config.max_connections_per_ip)
        if abs(current_window - tx_window) > 1:
            return False
            
        used_nonces_in_block.add(nonce)
        self.used_nonces.add(nonce)
        
        # Limpa nonces antigos
        self._clean_old_nonces()
        
        return True
        
    def _validate_transaction_balance(self, transaction: Dict) -> bool:
        """Valida saldos da transação"""
        
        try:
            from_address = transaction['from_address']
            amount = Decimal(str(transaction['amount']))
            token_type = transaction['token_type']
            region_hash = transaction.get('region_hash')
            
            # Recupera carteira
            wallet = Wallet.get_wallet_by_address(from_address)
            if not wallet:
                return False
                
            # Verifica saldo
            balance = wallet.get_balance(token_type, region_hash)
            if amount > balance:
                return False
                
            # Verifica overflow
            if amount + self.total_supply > self.config.max_supply:
                return False
                
            return True
            
        except:
            return False
            
    def _validate_block_supply(self, block: Block) -> bool:
        """Validações de supply e reward"""
        
        try:
            if not (hasattr(block, 'consensus_reward') or hasattr(block, 'activity_reward')):
                return True  # Bloco sem rewards é válido
                
            total_reward = Decimal('0')
            
            # Soma rewards
            if block.consensus_reward:
                total_reward += block.consensus_reward
            if block.activity_reward:
                total_reward += block.activity_reward
                
            # Verifica overflow
            if total_reward + self.total_supply > self.config.max_supply:
                return False
                
            # Atualiza supply total
            self.total_supply += total_reward
            
            return True
            
        except:
            return False

    def _validate_block_rewards(self, block: Block) -> bool:
        """Validações específicas de rewards"""
        
        try:
            # Valida reward de consenso
            if block.consensus_reward and block.consensus_reward > 0:
                # Deve ter validadores
                if not block.validator_addresses:
                    return False
                    
                # Valida distribuição
                if not hasattr(block, 'consensus_distribution'):
                    return False
                    
                # Soma deve bater
                total = sum(Decimal(str(v)) for v in block.consensus_distribution.values())
                if total != block.consensus_reward:
                    return False
                    
            # Valida reward de atividade
            if block.activity_reward and block.activity_reward > 0:
                # Deve ter entregador
                if not block.driver_address:
                    return False
                    
                # Valida distribuição
                if not hasattr(block, 'activity_distribution'):
                    return False
                    
                # Soma deve bater
                total = sum(Decimal(str(v)) for v in block.activity_distribution.values())
                if total != block.activity_reward:
                    return False
                    
            return True
            
        except:
            return False
            
    def _validate_block_hash(self, block: Block, previous_block: Block) -> bool:
        """Validações de hash e proof-of-work"""
        
        # Verifica se hash calculado bate com hash armazenado
        calculated_hash = block.calculate_hash()
        if calculated_hash != block.hash:
            return False
            
        # Verifica dificuldade mínima (zeros no início)
        if not block.hash.startswith('0' * self.config.initial_difficulty):
            return False
            
        return True
        
    def _clean_old_nonces(self):
        """Limpa nonces fora da janela de tempo"""
        current_window = int(time.time() / self.config.max_connections_per_ip)
        self.used_nonces = {
            nonce for nonce in self.used_nonces
            if int(nonce.split(':')[0]) >= current_window - 1
        }

class TransactionValidator:
    """
    Validador de transações
    Garante segurança e integridade das transações
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        
    def validate_delivery_contract(
        self,
        contract: DeliveryContract,
        executor_wallet: Wallet,
        establishment_wallet: Wallet
    ) -> bool:
        """Valida contrato de entrega"""
        
        try:
            # Valida assinaturas
            if not contract.verify_signatures():
                return False
                
            # Valida endereços
            if (contract.executor_address != executor_wallet.address or
                contract.establishment_address != establishment_wallet.address):
                return False
                
            # Valida valor
            if contract.value <= 0:
                return False
                
            # Valida coordenadas
            if not self._validate_coordinates(
                contract.start_coords,
                contract.end_coords
            ):
                return False
                
            return True
            
        except:
            return False
            
    def validate_conversion_contract(
        self,
        contract: TokenConversionContract,
        from_wallet: Wallet,
        to_wallet: Wallet,
        region_manager: 'RegionManager'
    ) -> bool:
        """Valida contrato de conversão"""
        
        try:
            # Valida assinatura
            if not contract.verify():
                return False
                
            # Valida endereços
            if (contract.from_address != from_wallet.address or
                contract.to_address != to_wallet.address):
                return False
                
            # Valida valor
            if contract.amount <= 0:
                return False
                
            # Valida saldo
            balance = from_wallet.get_balance(
                contract.from_token_type,
                contract.from_region_hash
            )
            if contract.amount > balance:
                return False
                
            # Valida taxa de conversão
            if contract.from_token_type == 'lateral' and contract.to_token_type == 'central':
                from_region = region_manager.get_region(region_hash=contract.from_region_hash)
                if not from_region:
                    return False
                    
                expected_rate = region_manager.calculate_conversion_rate(from_region)
                if abs(contract.conversion_rate - expected_rate) > Decimal('0.000001'):
                    return False
                    
            return True
            
        except:
            return False
            
    def _validate_coordinates(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float]
    ) -> bool:
        """Valida coordenadas geográficas"""
        
        try:
            # Valida formato
            if (len(start_coords) != 2 or len(end_coords) != 2):
                return False
                
            # Valida ranges
            if not all(-90 <= x <= 90 for x in (start_coords[0], end_coords[0])):
                return False
                
            if not all(-180 <= x <= 180 for x in (start_coords[1], end_coords[1])):
                return False
                
            return True
            
        except:
            return False 