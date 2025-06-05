from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from decimal import Decimal
import time
import json
import os
import threading
import hashlib
import secrets
from mnemonic import Mnemonic
import binascii
import ecdsa
import sys

# Import correto do blockchain principal da raiz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main_blockchain as blockchain_module

# Configurações locais para substituir imports quebrados
class ChainValidator:
    """Validador de chain simplificado"""
    def validate_chain(self, chain_data):
        return True
        
class AuditLog:
    """Log de auditoria simplificado"""
    def log_event(self, event, data):
        print(f"AUDIT: {event} - {data}")

class P2PNetwork:
    """Rede P2P simplificada"""
    def __init__(self, port, genesis_nodes):
        self.port = port
        self.genesis_nodes = genesis_nodes
        self.peers = []
        
    def broadcast_genesis(self, genesis_data):
        print(f"Broadcasting genesis: {genesis_data}")
        
    def broadcast_block(self, block_data):
        print(f"Broadcasting block: {block_data}")

class Wallet:
    """Carteira simplificada"""
    def __init__(self, passphrase=None):
        self.address = hashlib.sha256(
            (passphrase or secrets.token_hex(16)).encode()
        ).hexdigest()[:40]
        self.balance = TokenBalance()
        self.created_at = int(time.time())
        self.status = 'active'
        self.mnemonic = None
        if passphrase:
            self._generate_mnemonic()
            
    def _generate_mnemonic(self):
        """Gera mnemônico"""
        mnemo = Mnemonic("english")
        self.mnemonic = mnemo.generate(strength=128)
        
    def create_with_password(self, password):
        """Cria carteira com senha"""
        self.address = hashlib.sha256(password.encode()).hexdigest()[:40]
        self._generate_mnemonic()
        
    def export_mnemonic(self):
        """Exporta mnemônico"""
        return self.mnemonic
        
    def export_public_key(self):
        """Exporta chave pública"""
        return f"public_key_{self.address}"
        
    def set_balance(self, token_type, amount):
        """Define saldo"""
        if token_type == 'central':
            self.balance.central = amount
        else:
            self.balance.lateral[token_type] = amount
            
    def verify_transaction(self, transaction):
        """Verifica transação"""
        return True
        
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'address': self.address,
            'balance': {
                'central': str(self.balance.central),
                'lateral': self.balance.lateral
            },
            'status': self.status,
            'created_at': self.created_at
        }
        
    @classmethod
    def from_mnemonic(cls, mnemonic, passphrase):
        """Cria carteira de mnemônico"""
        wallet = cls()
        wallet.mnemonic = mnemonic
        wallet.address = hashlib.sha256(mnemonic.encode()).hexdigest()[:40]
        return wallet
        
    @classmethod  
    def from_dict(cls, data):
        """Cria carteira de dicionário"""
        wallet = cls()
        wallet.address = data['address']
        wallet.status = data.get('status', 'active')
        wallet.created_at = data.get('created_at', int(time.time()))
        wallet.balance.central = Decimal(data['balance']['central'])
        wallet.balance.lateral = data['balance'].get('lateral', {})
        return wallet

class TokenBalance:
    """Saldo de tokens"""
    def __init__(self):
        self.central = Decimal('0')
        self.lateral = {}

class Transaction:
    """Transação simplificada"""
    def __init__(self, from_addr, to_addr, amount):
        self.from_address = from_addr
        self.to_address = to_addr
        self.amount = amount
        self.timestamp = time.time()
        self.hash = self.calculate_hash()
        
    def calculate_hash(self):
        return hashlib.sha256(
            f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}".encode()
        ).hexdigest()

class Block:
    """Bloco para compatibilidade"""
    def __init__(self, timestamp, start_coords, end_coords, delivery_hash, 
                 previous_hash, contract_id, transactions):
        self.timestamp = timestamp
        self.start_coords = start_coords
        self.end_coords = end_coords
        self.delivery_hash = delivery_hash
        self.previous_hash = previous_hash
        self.contract_id = contract_id
        self.transactions = transactions
        self.hash = self.calculate_hash()
        
    def calculate_hash(self):
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()
        ).hexdigest()
        
    def to_dict(self):
        return {
            'timestamp': self.timestamp,
            'start_coords': self.start_coords.to_dict() if hasattr(self.start_coords, 'to_dict') else str(self.start_coords),
            'end_coords': self.end_coords.to_dict() if hasattr(self.end_coords, 'to_dict') else str(self.end_coords),
            'delivery_hash': self.delivery_hash,
            'previous_hash': self.previous_hash,
            'contract_id': self.contract_id,
            'transactions': self.transactions,
            'hash': self.hash
        }
        
    @classmethod
    def from_dict(cls, data):
        block = cls(
            timestamp=data['timestamp'],
            start_coords=data['start_coords'],
            end_coords=data['end_coords'], 
            delivery_hash=data['delivery_hash'],
            previous_hash=data['previous_hash'],
            contract_id=data['contract_id'],
            transactions=data['transactions']
        )
        block.hash = data.get('hash', block.calculate_hash())
        return block

class Coordinates:
    """Coordenadas simples"""
    def __init__(self, lat, lng):
        self.lat = lat
        self.lng = lng
        
    def to_dict(self):
        return {'lat': self.lat, 'lng': self.lng}

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"]
    }
})

# Configuração de mineração
MINING_DIFFICULTY = 4  # Número de zeros iniciais requeridos
BLOCK_REWARD = Decimal('50')  # Recompensa por bloco
BLOCK_TIME = 60  # Tempo alvo em segundos

# Instancia componentes principais
tokenomics_config = blockchain_module.TokenConfig()
tokenomics = blockchain_module.TokenomicsManager(tokenomics_config)
validator = ChainValidator()
audit_log = AuditLog()

# Configuração P2P
P2P_PORT = 6000
GENESIS_NODES = ['127.0.0.1:6000']  # Lista de nós iniciais
p2p_network = P2PNetwork(P2P_PORT, GENESIS_NODES)

# Arquivo do bloco genesis
GENESIS_FILE = 'genesis_block.json'

class BlockchainState:
    def __init__(self):
        self.wallets = {}  # Armazena apenas dados públicos das carteiras
        self.transactions = []  # Armazena transações pendentes
        self.blocks = []  # Armazena blocos validados
        self.miners = {}  # Armazena mineradores ativos
        self.mining_stats = {}  # Estatísticas de mineração
        self.current_block = None  # Bloco sendo minerado
        self.difficulty = MINING_DIFFICULTY
        self.genesis_block = None
        self.load_or_create_genesis()
        
        # Inicia thread de ajuste de dificuldade
        self.difficulty_thread = threading.Thread(target=self._adjust_difficulty)
        self.difficulty_thread.daemon = True
        self.difficulty_thread.start()
        
    def load_or_create_genesis(self):
        """Carrega ou cria o bloco genesis"""
        if os.path.exists(GENESIS_FILE):
            try:
                with open(GENESIS_FILE, 'r') as f:
                    genesis_data = json.load(f)
                    self.genesis_block = Block.from_dict(genesis_data)
                    # Carrega carteiras das transações do bloco genesis
                    for tx in self.genesis_block.transactions:
                        if tx.get('type') == 'wallet':
                            wallet = Wallet.from_dict(tx['wallet_data'])
                            self.wallets[wallet.address] = wallet
            except Exception as e:
                print(f"Erro ao carregar bloco genesis: {e}")
                self._create_new_genesis()
        else:
            self._create_new_genesis()
            
    def _create_new_genesis(self):
        """Cria um novo bloco genesis"""
        genesis_transaction = {
            "type": "genesis",
            "timestamp": time.time(),
            "data": "Genesis Block of Logistics Blockchain Protocol"
        }
        
        self.genesis_block = Block(
            timestamp=time.time(),
            start_coords=Coordinates(0, 0),
            end_coords=Coordinates(0, 0),
            delivery_hash="genesis",
            previous_hash="0" * 64,
            contract_id="genesis",
            transactions=[genesis_transaction]
        )
        
        # Adiciona carteira de teste
        test_wallet = Wallet()
        test_wallet.create_with_password('asd123')  # Cria com senha padrão
        test_wallet.address = '393b7421e4377c12c4dde45f5a85ca8b94e757b4'
        test_wallet.set_balance('central', Decimal('1000'))  # Saldo inicial para teste
        self.add_wallet(test_wallet)
            
    def add_wallet(self, wallet):
        """Adiciona uma nova carteira ao estado"""
        self.wallets[wallet.address] = wallet
        self.update_genesis_block()
        
    def update_genesis_block(self):
        """Atualiza o bloco genesis com o estado atual"""
        # Mantém a transação genesis original
        genesis_tx = next(tx for tx in self.genesis_block.transactions if tx['type'] == 'genesis')
        
        # Cria transações para cada carteira
        wallet_transactions = [{
            'type': 'wallet',
            'timestamp': time.time(),
            'wallet_data': wallet.to_dict()
        } for wallet in self.wallets.values()]
        
        # Atualiza transações do bloco
        transactions = [genesis_tx] + wallet_transactions
        
        # Cria novo bloco com as transações atualizadas
        self.genesis_block = Block(
            timestamp=self.genesis_block.timestamp,
            start_coords=self.genesis_block.start_coords,
            end_coords=self.genesis_block.end_coords,
            delivery_hash=self.genesis_block.delivery_hash,
            previous_hash=self.genesis_block.previous_hash,
            contract_id=self.genesis_block.contract_id,
            transactions=transactions
        )
        
        # Salva no arquivo
        with open(GENESIS_FILE, 'w') as f:
            json.dump(self.genesis_block.to_dict(), f, indent=2)
            
        # Propaga para outros nós
        p2p_network.broadcast_genesis(self.genesis_block.to_dict())

    def add_transaction(self, transaction: dict) -> bool:
        """Adiciona transação pendente"""
        # Valida transação
        try:
            from_address = transaction['from_address']
            wallet_data = self.wallets.get(from_address)
            if not wallet_data:
                return False
                
            # Cria carteira somente-leitura para verificar
            wallet = Wallet.from_dict(wallet_data)
            if wallet.verify_transaction(transaction):
                self.transactions.append(transaction)
                return True
        except Exception as e:
            print(f"Erro ao validar transação: {e}")
        return False
        
    def get_wallet_balance(self, address: str) -> dict:
        """Retorna saldo da carteira"""
        wallet_data = self.wallets.get(address)
        if not wallet_data:
            return {'central': '0', 'lateral': {}}
        return wallet_data['balance']

    def start_mining(self, address: str) -> bool:
        """Inicia mineração para endereço"""
        if not self.wallets.get(address):
            return False
            
        self.miners[address] = {
            'active': True,
            'started_at': time.time(),
            'blocks_mined': 0,
            'total_reward': Decimal('0'),
            'last_hash': None
        }
        
        # Cria novo bloco se necessário
        if not self.current_block:
            self._create_new_block()
            
        return True
        
    def stop_mining(self, address: str) -> bool:
        """Para mineração para endereço"""
        if address in self.miners:
            self.miners[address]['active'] = False
            return True
        return False
        
    def submit_block(self, address: str, block_data: dict) -> bool:
        """
        Submete bloco minerado para validação
        Retorna True se bloco foi aceito
        """
        try:
            # Verifica se minerador está ativo
            miner = self.miners.get(address)
            if not miner or not miner['active']:
                return False
                
            # Verifica hash
            block_hash = block_data['hash']
            if not block_hash.startswith('0' * self.difficulty):
                return False
                
            # Verifica se bloco é válido
            if not self._verify_block(block_data):
                return False
                
            # Adiciona bloco à chain
            self.blocks.append(block_data)
            
            # Atualiza estatísticas do minerador
            miner['blocks_mined'] += 1
            miner['total_reward'] += BLOCK_REWARD
            miner['last_hash'] = block_hash
            
            # Remove transações do pool
            self._remove_confirmed_transactions(block_data['transactions'])
            
            # Cria novo bloco
            self._create_new_block()
            
            # Propaga bloco
            p2p_network.broadcast_block(block_data)
            
            return True
            
        except Exception as e:
            print(f"Erro ao submeter bloco: {e}")
            return False
            
    def get_mining_stats(self, address: str = None) -> dict:
        """Retorna estatísticas de mineração"""
        if address:
            stats = self.miners.get(address, {
                'active': False,
                'blocks_mined': 0,
                'total_reward': Decimal('0')
            })
        else:
            stats = {
                'total_miners': len(self.miners),
                'active_miners': len([m for m in self.miners.values() if m['active']]),
                'network_hashrate': self._calculate_network_hashrate(),
                'difficulty': self.difficulty,
                'block_time': BLOCK_TIME,
                'current_block': self._get_current_block_template()
            }
            
        return stats
        
    def _create_new_block(self):
        """Cria novo bloco para mineração"""
        prev_hash = self.blocks[-1]['hash'] if self.blocks else '0' * 64
        
        self.current_block = {
            'number': len(self.blocks) + 1,
            'timestamp': int(time.time()),
            'transactions': self.transactions[:],
            'prev_hash': prev_hash,
            'difficulty': self.difficulty,
            'reward': float(BLOCK_REWARD)
        }
        
    def _verify_block(self, block_data: dict) -> bool:
        """Verifica se bloco é válido"""
        try:
            # Verifica número do bloco
            if block_data['number'] != len(self.blocks) + 1:
                return False
                
            # Verifica hash anterior
            prev_hash = self.blocks[-1]['hash'] if self.blocks else '0' * 64
            if block_data['prev_hash'] != prev_hash:
                return False
                
            # Verifica transações
            for tx in block_data['transactions']:
                if not self._verify_transaction(tx):
                    return False
                    
            return True
            
        except Exception as e:
            print(f"Erro ao verificar bloco: {e}")
            return False
            
    def _verify_transaction(self, transaction: dict) -> bool:
        """Verifica se transação é válida"""
        try:
            from_address = transaction['from_address']
            wallet_data = self.wallets.get(from_address)
            if not wallet_data:
                return False
                
            wallet = Wallet.from_dict(wallet_data)
            return wallet.verify_transaction(transaction)
            
        except Exception as e:
            print(f"Erro ao verificar transação: {e}")
            return False
            
    def _remove_confirmed_transactions(self, transactions: list):
        """Remove transações confirmadas do pool"""
        tx_hashes = {tx['hash'] for tx in transactions}
        self.transactions = [tx for tx in self.transactions if tx['hash'] not in tx_hashes]
        
    def _calculate_network_hashrate(self) -> float:
        """Calcula hashrate total da rede"""
        total_blocks = len(self.blocks)
        if total_blocks < 2:
            return 0
            
        # Calcula média de tempo entre blocos
        timestamps = [b['timestamp'] for b in self.blocks[-10:]]
        if len(timestamps) < 2:
            return 0
            
        avg_time = (timestamps[-1] - timestamps[0]) / (len(timestamps) - 1)
        if avg_time <= 0:
            return 0
            
        # Estima hashrate baseado na dificuldade
        difficulty_multiplier = 16 ** self.difficulty  # Aproximação
        return difficulty_multiplier / avg_time
        
    def _get_current_block_template(self) -> dict:
        """Retorna template do bloco atual"""
        if not self.current_block:
            self._create_new_block()
            
        return {
            'number': self.current_block['number'],
            'timestamp': self.current_block['timestamp'],
            'transactions': len(self.current_block['transactions']),
            'prev_hash': self.current_block['prev_hash'],
            'difficulty': self.current_block['difficulty']
        }
        
    def _adjust_difficulty(self):
        """Ajusta dificuldade baseado no tempo médio dos blocos"""
        while True:
            time.sleep(60)  # Verifica a cada minuto
            
            if len(self.blocks) < 10:
                continue
                
            # Calcula tempo médio dos últimos 10 blocos
            timestamps = [b['timestamp'] for b in self.blocks[-10:]]
            avg_time = (timestamps[-1] - timestamps[0]) / (len(timestamps) - 1)
            
            # Ajusta dificuldade
            if avg_time < BLOCK_TIME * 0.8:
                self.difficulty += 1
            elif avg_time > BLOCK_TIME * 1.2:
                self.difficulty = max(1, self.difficulty - 1)

# Inicializa estado da blockchain
blockchain_state = BlockchainState()

# Adiciona carteira de teste se não existir
test_wallet_address = 'a0cab7c16f7815c1c87d4d036ee5ceae0c68ecdb'
if test_wallet_address not in blockchain_state.wallets:
    test_wallet = Wallet()
    test_wallet.address = test_wallet_address
    test_wallet.balance.central = Decimal('1000')
    blockchain_state.wallets[test_wallet_address] = test_wallet

@app.route('/')
def index():
    """Página principal"""
    return render_template('transactions.html')

@app.route('/wallet')
def wallet():
    """Página da carteira"""
    return render_template('wallet.html')

@app.route('/mining')
def mining():
    """Página de mineração"""
    return render_template('mining.html')

@app.route('/static/<path:path>')
def send_static(path):
    """Serve arquivos estáticos"""
    return send_from_directory('static', path)

@app.route('/api/network/stats', methods=['GET'])
def get_network_stats():
    """Status da rede blockchain"""
    return jsonify({
        'totalBlocks': len(blockchain_state.blocks),
        'activeNodes': len(p2p_network.peers),
        'totalWallets': len(blockchain_state.wallets),
        'pendingTransactions': len(blockchain_state.transactions)
    })

@app.route('/api/tokenomics', methods=['GET'])
def get_tokenomics():
    """Informações de tokenomics"""
    block_rewards = tokenomics.get_block_rewards(tokenomics.current_block)
    return jsonify({
        'circulatingSupply': float(tokenomics.get_circulating_supply()),
        'price': 1.0,  # Example price
        'consensusReward': float(block_rewards['consensus']),
        'activityReward': float(block_rewards['activity'])
    })

@app.route('/api/wallet/create', methods=['POST'])
def create_wallet():
    """
    Gera nova carteira HD
    Retorna dados públicos e mnemônico
    """
    try:
        print("DEBUG API: Iniciando criação de carteira")
        data = request.get_json()
        print("DEBUG API: Dados recebidos:", data)
        
        if not data or not isinstance(data, dict):
            print("DEBUG API: Dados inválidos recebidos")
            return jsonify({'error': 'Invalid request data'}), 400
            
        password = data.get('password')
        if not password or not isinstance(password, str):
            print("DEBUG API: Senha inválida ou não fornecida")
            return jsonify({'error': 'Password must be a non-empty string'}), 400
            
        # Gera nova carteira
        wallet = Wallet(passphrase=password)
        print(f"DEBUG API: Nova carteira criada com endereço: {wallet.address}")
        
        # Obtém o mnemônico antes de qualquer outra operação
        mnemonic = wallet.export_mnemonic()
        print(f"DEBUG API: Mnemônico gerado: {mnemonic}")
        
        if not mnemonic:
            print("DEBUG API: Erro - Mnemônico não gerado!")
            return jsonify({'error': 'Failed to generate mnemonic'}), 500
            
        # Prepara resposta com dados públicos e mnemônico
        response_data = {
            'address': wallet.address,
            'public_key': wallet.export_public_key(),
            'balance': {
                'central': '0',
                'lateral': {}
            },
            'mnemonic': mnemonic,  # Inclui o mnemônico explicitamente
            'status': 'active'
        }
        print(f"DEBUG API: Dados de resposta preparados: {json.dumps(response_data, indent=2)}")
        
        # Salva apenas dados públicos no estado
        wallet_data = wallet.to_dict()
        blockchain_state.wallets[wallet.address] = wallet_data
        
        return jsonify(response_data)
    except Exception as e:
        print(f"DEBUG API: Erro criando carteira: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@app.route('/api/wallet/recover', methods=['POST'])
def recover_wallet():
    """
    Recupera carteira de mnemônico
    """
    data = request.get_json()
    mnemonic = data.get('mnemonic')
    passphrase = data.get('passphrase')
    
    try:
        wallet = Wallet.from_mnemonic(mnemonic, passphrase)
        blockchain_state.wallets[wallet.address] = wallet.to_dict()
        return jsonify(wallet.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/wallets', methods=['GET'])
def list_wallets():
    """Lista carteiras (apenas dados públicos)"""
    try:
        wallets_list = []
        for address, wallet_data in blockchain_state.wallets.items():
            # Handle different types of wallet data
            if isinstance(wallet_data, dict):
                balance = wallet_data.get('balance', {}).get('central', '0')
            else:
                # If it's a Wallet object
                balance_obj = getattr(wallet_data, 'balance', None)
                if balance_obj is None:
                    balance = '0'
                elif isinstance(balance_obj, dict):
                    balance = balance_obj.get('central', '0')
                else:
                    # If it's a TokenBalance object
                    balance = str(getattr(balance_obj, 'central', '0'))
            
            wallet_info = {
                'address': address,
                'balance': balance,
                'status': 'active'
            }
            wallets_list.append(wallet_info)
        
        print("DEBUG: Wallets list:", wallets_list)  # Debug print
        return jsonify({'wallets': wallets_list})
    except Exception as e:
        print(f"Erro ao listar carteiras: {str(e)}")
        import traceback
        traceback.print_exc()  # Print full error trace
        return jsonify({'error': str(e)}), 400

@app.route('/api/wallet/<address>/balance', methods=['GET'])
def get_wallet_balance(address):
    """Retorna saldo da carteira"""
    try:
        wallet_data = blockchain_state.wallets.get(address)
        if not wallet_data:
            return jsonify({'central': '0', 'lateral': {}})
            
        # Handle different types of wallet data
        if isinstance(wallet_data, dict):
            balance = wallet_data.get('balance', {}).get('central', '0')
        else:
            # If it's a Wallet object
            balance_obj = getattr(wallet_data, 'balance', None)
            if balance_obj is None:
                balance = '0'
            elif isinstance(balance_obj, dict):
                balance = balance_obj.get('central', '0')
            else:
                # If it's a TokenBalance object
                balance = str(getattr(balance_obj, 'central', '0'))
            
        return jsonify({'central': balance})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/transactions', methods=['POST'])
def submit_transaction():
    """
    Submete transação assinada para a rede
    A transação deve ser assinada offline
    """
    transaction = request.get_json()
    
    if blockchain_state.add_transaction(transaction):
        # Propaga para rede P2P
        p2p_network.broadcast_transaction(transaction)
        return jsonify({'success': True, 'transaction': transaction})
    
    return jsonify({'error': 'Invalid transaction'}), 400

@app.route('/api/transactions/pending', methods=['GET'])
def get_pending_transactions():
    """Lista transações pendentes"""
    return jsonify(blockchain_state.transactions)

@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """Lista blocos validados"""
    return jsonify(blockchain_state.blocks)

@app.route('/api/user/<address>/stats', methods=['GET'])
def get_user_stats(address):
    """Estatísticas do usuário"""
    wallet = blockchain_state.wallets.get(address)
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
        
    # Example stats
    return jsonify({
        'balance': float(wallet.get_balance('central')),
        'totalDeliveries': 0,  # Would come from delivery system
        'totalRewards': float(wallet.get_balance('central'))  # Simplified
    })

@app.route('/api/deliveries/active/<address>', methods=['GET'])
def get_active_deliveries(address):
    """Entregas ativas do usuário"""
    wallet = Wallet(address)
    deliveries = wallet.get_active_deliveries()
    return jsonify([{
        'id': d.id,
        'status': d.status,
        'timestamp': d.timestamp,
        'reward': d.reward,
        'distance': d.distance
    } for d in deliveries])

@app.route('/api/deliveries', methods=['POST'])
def create_delivery():
    """Criar nova entrega"""
    data = request.json
    delivery = Transaction.create_delivery(
        from_address=data['from'],
        to_address=data['to'],
        amount=data['amount'],
        coordinates=data['coordinates']
    )
    return jsonify(delivery.to_dict())

@app.route('/api/mining/start', methods=['POST'])
def start_mining():
    """Inicia mineração"""
    data = request.get_json()
    address = data.get('address')
    
    if not address:
        return jsonify({'error': 'Address required'}), 400
        
    if blockchain_state.start_mining(address):
        return jsonify({
            'success': True,
            'block_template': blockchain_state._get_current_block_template(),
            'difficulty': blockchain_state.difficulty
        })
    
    return jsonify({'error': 'Failed to start mining'}), 400

@app.route('/api/mining/stop', methods=['POST'])
def stop_mining():
    """Para mineração"""
    data = request.get_json()
    address = data.get('address')
    
    if not address:
        return jsonify({'error': 'Address required'}), 400
        
    if blockchain_state.stop_mining(address):
        return jsonify({'success': True})
    
    return jsonify({'error': 'Miner not found'}), 404

@app.route('/api/mining/submit', methods=['POST'])
def submit_mined_block():
    """Submete bloco minerado"""
    data = request.get_json()
    address = data.get('address')
    block = data.get('block')
    
    if not address or not block:
        return jsonify({'error': 'Address and block required'}), 400
        
    if blockchain_state.submit_block(address, block):
        return jsonify({
            'success': True,
            'new_template': blockchain_state._get_current_block_template()
        })
    
    return jsonify({'error': 'Invalid block'}), 400

@app.route('/api/mining/stats', methods=['GET'])
def get_mining_stats():
    """Estatísticas de mineração"""
    address = request.args.get('address')
    return jsonify(blockchain_state.get_mining_stats(address))

@app.route('/api/contracts/<address>', methods=['GET'])
def get_contracts(address):
    """Contratos do usuário"""
    wallet = Wallet(address)
    contracts = wallet.get_contracts()
    return jsonify([{
        'id': c.id,
        'type': c.type,
        'value': c.value,
        'status': c.status
    } for c in contracts])

@app.route('/api/contracts', methods=['POST'])
def create_contract():
    """Criar novo contrato"""
    data = request.json
    contract = Transaction.create_contract(
        contract_type=data['type'],
        value=data['value'],
        owner=data['address']
    )
    return jsonify(contract.to_dict())

@app.route('/api/transactions/<address>', methods=['GET'])
def get_transactions(address):
    """Transações do usuário"""
    wallet = Wallet(address)
    transactions = wallet.get_transactions()
    return jsonify([{
        'type': tx.type,
        'amount': tx.amount,
        'timestamp': tx.timestamp,
        'status': tx.status
    } for tx in transactions])

@app.route('/api/search', methods=['GET'])
def search_blockchain():
    """Buscar na blockchain"""
    query = request.args.get('q')
    
    if query == 'latest_blocks':
        blocks = validator.get_latest_blocks(10)
        return jsonify([{
            'number': b.number,
            'timestamp': b.timestamp,
            'transactions': len(b.transactions),
            'miner': b.miner,
            'size': b.size
        } for b in blocks])
    
    elif query == 'latest_transactions':
        txs = validator.get_latest_transactions(10)
        return jsonify([{
            'hash': tx.hash,
            'from': tx.from_address,
            'to': tx.to_address,
            'value': tx.amount
        } for tx in txs])
    
    else:
        results = validator.search(query)
        return jsonify(results)

@app.route('/api/wallet/update-password', methods=['POST'])
def update_wallet_password():
    """Atualiza a senha da wallet"""
    data = request.get_json()
    address = data.get('address')
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    wallet = blockchain_state.wallets.get(address)
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
        
    try:
        # Verify current password by attempting to export private key
        wallet.export_private_key(current_password)
        
        # Update password
        wallet.password = new_password
        blockchain_state.update_genesis_block()  # Salva após atualizar senha
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': 'Invalid current password'}), 400

@app.route('/api/wallet/verify', methods=['POST'])
def verify_wallet():
    """Verifica se uma carteira existe e está ativa"""
    try:
        data = request.get_json()
        if not data or 'address' not in data:
            return jsonify({'error': 'Endereço da carteira é obrigatório'}), 400

        address = data['address']
        wallet_data = blockchain_state.wallets.get(address)
        
        if not wallet_data:
            return jsonify({'error': 'Carteira não encontrada'}), 404

        # Se chegou aqui, a carteira existe
        return jsonify({
            'valid': True,
            'address': address,
            'status': 'active'
        })

    except Exception as e:
        print(f"Erro ao verificar carteira: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/wallet/login', methods=['POST'])
def login_wallet():
    """Login na wallet com verificação de senha"""
    data = request.get_json()
    address = data.get('address')
    password = data.get('password')
    
    if not address or not password:
        return jsonify({'error': 'Endereço e senha são obrigatórios'}), 400
        
    wallet = blockchain_state.wallets.get(address)
    if not wallet:
        return jsonify({'error': 'Wallet não encontrada'}), 404
        
    try:
        # Verifica a senha
        if not wallet.verify_password(password):  # Método que vamos adicionar à classe Wallet
            return jsonify({'error': 'Senha incorreta'}), 401
            
        return jsonify({
            'address': wallet.address,
            'balance': float(wallet.get_balance('central')),
            'status': 'active'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 401

@app.route('/api/p2p/sync', methods=['POST'])
def sync_blockchain():
    """Sincroniza o estado com outros nós"""
    data = request.get_json()
    if data and 'genesis_block' in data:
        new_genesis = Block.from_dict(data['genesis_block'])
        if new_genesis.index > blockchain_state.genesis_block.index:
            blockchain_state.genesis_block = new_genesis
            blockchain_state.load_or_create_genesis()
            return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/explorer')
def explorer():
    """Página do explorador da blockchain"""
    return render_template('explorer.html')

@app.route('/api/chain', methods=['GET'])
def get_chain():
    """Retorna toda a blockchain"""
    start = request.args.get('start', type=int, default=0)
    limit = request.args.get('limit', type=int, default=50)
    
    # Inclui bloco genesis
    blocks = [blockchain_state.genesis_block.to_dict()]
    
    # Adiciona blocos validados
    blocks.extend(blockchain_state.blocks[start:start+limit])
    
    return jsonify({
        'blocks': blocks,
        'total': len(blockchain_state.blocks) + 1,  # +1 para o genesis
        'has_more': (start + limit) < len(blockchain_state.blocks)
    })

@app.route('/api/block/<block_hash>', methods=['GET'])
def get_block(block_hash):
    """Retorna detalhes de um bloco específico"""
    # Verifica bloco genesis
    if blockchain_state.genesis_block.hash == block_hash:
        return jsonify(blockchain_state.genesis_block.to_dict())
        
    # Busca nos blocos validados
    for block in blockchain_state.blocks:
        if block['hash'] == block_hash:
            return jsonify(block)
            
    return jsonify({'error': 'Block not found'}), 404

@app.route('/api/transaction/<tx_hash>', methods=['GET'])
def get_transaction(tx_hash):
    """Retorna detalhes de uma transação específica"""
    # Busca em todos os blocos
    blocks = [blockchain_state.genesis_block] + blockchain_state.blocks
    
    for block in blocks:
        for tx in block.transactions:
            if tx.get('hash') == tx_hash:
                return jsonify({
                    'transaction': tx,
                    'block': block.to_dict(),
                    'confirmations': len(blockchain_state.blocks) - block.number + 1
                })
                
    # Busca em transações pendentes
    for tx in blockchain_state.transactions:
        if tx.get('hash') == tx_hash:
            return jsonify({
                'transaction': tx,
                'pending': True,
                'confirmations': 0
            })
            
    return jsonify({'error': 'Transaction not found'}), 404

@app.route('/api/address/<address>', methods=['GET'])
def get_address_info(address):
    """Retorna informações de um endereço"""
    wallet = blockchain_state.wallets.get(address)
    if not wallet:
        return jsonify({'error': 'Address not found'}), 404
        
    # Busca transações do endereço
    transactions = []
    blocks = [blockchain_state.genesis_block] + blockchain_state.blocks
    
    for block in blocks:
        for tx in block.transactions:
            if tx.get('from_address') == address or tx.get('to_address') == address:
                transactions.append({
                    'transaction': tx,
                    'block': block.number,
                    'confirmations': len(blockchain_state.blocks) - block.number + 1
                })
                
    # Adiciona transações pendentes
    for tx in blockchain_state.transactions:
        if tx.get('from_address') == address or tx.get('to_address') == address:
            transactions.append({
                'transaction': tx,
                'pending': True,
                'confirmations': 0
            })
            
    return jsonify({
        'address': address,
        'balance': wallet.get('balance', {'central': '0', 'lateral': {}}),
        'transactions': transactions,
        'total_transactions': len(transactions)
    })

@app.route('/api/search', methods=['GET'])
def search():
    """Busca por bloco, transação ou endereço"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query required'}), 400
        
    # Tenta encontrar bloco
    if len(query) == 64:  # Tamanho do hash
        if blockchain_state.genesis_block.hash == query:
            return jsonify({
                'type': 'block',
                'data': blockchain_state.genesis_block.to_dict()
            })
            
        for block in blockchain_state.blocks:
            if block['hash'] == query:
                return jsonify({
                    'type': 'block',
                    'data': block
                })
                
    # Tenta encontrar transação
    blocks = [blockchain_state.genesis_block] + blockchain_state.blocks
    for block in blocks:
        for tx in block.transactions:
            if tx.get('hash') == query:
                return jsonify({
                    'type': 'transaction',
                    'data': {
                        'transaction': tx,
                        'block': block.to_dict(),
                        'confirmations': len(blockchain_state.blocks) - block.number + 1
                    }
                })
                
    # Tenta encontrar endereço
    if query in blockchain_state.wallets:
        wallet = blockchain_state.wallets[query]
        return jsonify({
            'type': 'address',
            'data': {
                'address': query,
                'balance': wallet.get('balance', {'central': '0', 'lateral': {}})
            }
        })
        
    return jsonify({'error': 'Not found'}), 404

# Inicia servidor P2P em uma thread separada
if __name__ == '__main__':
    # Inicializa sistema de auditoria
    audit_log.start()
    
    # Inicia rede P2P
    p2p_network.start()
    
    # Configurações SSL
    ssl_context = None
    if os.path.exists('ssl/certificate.crt') and os.path.exists('ssl/private.key'):
        import ssl
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain('ssl/certificate.crt', 'ssl/private.key')
        print("SSL/TLS configurado com sucesso!")
    else:
        print("AVISO: Certificados SSL não encontrados. Servidor rodando sem SSL!")
    
    # Carrega variáveis de ambiente de produção
    if os.path.exists('production/keys.env'):
        from dotenv import load_dotenv
        load_dotenv('production/keys.env')
        print("Chaves de produção carregadas!")
    
    # Inicia servidor HTTP com SSL se disponível
    if ssl_context:
        app.run(host='0.0.0.0', port=5000, ssl_context=ssl_context)
    else:
        app.run(host='0.0.0.0', port=5000) 