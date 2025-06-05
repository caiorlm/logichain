from flask import Flask, render_template, jsonify, request
import json
import os
import sqlite3
from datetime import datetime
import hashlib
import secrets
from mnemonic import Mnemonic
from hdwallet.hdwallet import HDWallet
from hdwallet.symbols import ETH as SYMBOL
from hdwallet.cryptocurrencies import get_cryptocurrency
from typing import Optional
import sys

# Import correto do blockchain principal da raiz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main_blockchain as blockchain_module

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configuração do modo real
ONLINE_MODE = True
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blockchain/mainnet.db")
MINING_DIFFICULTY = 18  # Dificuldade real de mineração
BLOCK_REWARD = 50  # Recompensa inicial por bloco em LGC
HALVING_BLOCKS = 210000  # Número de blocos para halving
MNEMONIC_STRENGTH = 256  # 24 palavras para maior segurança

def init_database():
    """Inicializa o banco de dados com as tabelas necessárias"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Tabela de blocos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                hash TEXT PRIMARY KEY,
                timestamp REAL,
                transactions TEXT,
                previous_hash TEXT,
                nonce INTEGER,
                height INTEGER,
                pod_proof TEXT
            )
        ''')
        
        # Tabela de carteiras
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                balance REAL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        ''')
        
        # Tabela de transações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                hash TEXT PRIMARY KEY,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                confirmed INTEGER DEFAULT 0
            )
        ''')
        
        # Tabela de provas de entrega
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delivery_proofs (
                proof_hash TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                delivery_id TEXT NOT NULL,
                driver_address TEXT NOT NULL,
                receiver_address TEXT NOT NULL,
                pickup_coords TEXT NOT NULL,
                delivery_coords TEXT NOT NULL,
                pickup_time INTEGER NOT NULL,
                delivery_time INTEGER NOT NULL,
                distance_km REAL NOT NULL,
                photos TEXT NOT NULL,
                driver_signature TEXT,
                receiver_signature TEXT,
                reward REAL,
                block_hash TEXT,
                FOREIGN KEY (block_hash) REFERENCES blocks(hash)
            )
        ''')
        
        conn.commit()

def get_blockchain():
    return blockchain_module.Blockchain(DB_PATH)

def get_current_timestamp():
    return int(datetime.now().timestamp())

def format_timestamp(timestamp):
    # Converter string para timestamp se necessário
    if isinstance(timestamp, str):
        try:
            # Tentar converter string ISO para timestamp
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp = int(dt.timestamp())
        except ValueError:
            try:
                # Tentar converter timestamp em string
                timestamp = int(timestamp)
            except ValueError:
                return 'Data inválida'
    
    # Verificar se o timestamp está em segundos (10 dígitos) ou milissegundos (13 dígitos)
    if isinstance(timestamp, int) and len(str(timestamp)) >= 13:
        timestamp = timestamp // 1000
    
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OSError):
        return 'Data inválida'

def generate_wallet() -> dict:
    """Gera uma nova wallet usando BIP39/BIP44"""
    # Gerar mnemônico (12 palavras em inglês)
    mnemonic = Mnemonic("english").generate(strength=MNEMONIC_STRENGTH)
    
    # Criar HD wallet
    wallet = HDWallet(symbol=SYMBOL)
    wallet.from_mnemonic(
        mnemonic=mnemonic,
        language="english"  # Usar inglês como padrão
    )
    
    # Derivar primeira conta
    # m/44'/60'/0'/0/0 path para Ethereum
    wallet.from_path("m/44'/60'/0'/0/0")
    
    # Gerar endereço
    wallet_address = wallet.dumps()['addresses']['p2pkh']  # Usar endereço P2PKH
    private_key = wallet.dumps()['private_key']
    
    return {
        'address': f"LGC{wallet_address[2:]}",  # Remover '0x' e adicionar prefixo LGC
        'private_key': private_key,
        'mnemonic': mnemonic,
        'path': "m/44'/60'/0'/0/0"
    }

def recover_wallet_from_mnemonic(mnemonic: str) -> Optional[dict]:
    """Recupera uma wallet a partir da frase mnemônica"""
    try:
        wallet = HDWallet(symbol=SYMBOL)
        wallet.from_mnemonic(
            mnemonic=mnemonic,
            language="english"  # Usar inglês como padrão
        )
        
        # Derivar primeira conta
        wallet.from_path("m/44'/60'/0'/0/0")
        
        # Gerar endereço
        wallet_address = wallet.dumps()['addresses']['p2pkh']  # Usar endereço P2PKH
        private_key = wallet.dumps()['private_key']
        
        return {
            'address': f"LGC{wallet_address[2:]}",
            'private_key': private_key,
            'mnemonic': mnemonic,
            'path': "m/44'/60'/0'/0/0"
        }
    except Exception as e:
        print(f"Erro ao recuperar wallet: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html', online_mode=ONLINE_MODE)

@app.route('/api/mode')
def get_mode():
    return jsonify({'online': ONLINE_MODE})

@app.route('/api/blocks')
def get_blocks():
    blockchain = get_blockchain()
    blocks = []
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT hash, timestamp, transactions, previous_hash, nonce, height, pod_proof
            FROM blocks 
            ORDER BY height DESC 
            LIMIT 50
        ''')
        
        for row in cursor.fetchall():
            blocks.append({
                'hash': row[0],
                'timestamp': row[1],
                'transactions': row[2],
                'previous_hash': row[3],
                'nonce': row[4],
                'height': row[5],
                'pod_proof': row[6],
                'validation_status': 'Validado' if row[6] else 'Pendente'
            })
    return jsonify(blocks)

@app.route('/api/stats')
def get_stats():
    blockchain = get_blockchain()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM blocks')
        total_blocks = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT contract_id) FROM blocks WHERE contract_id != "genesis"')
        total_contracts = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance) FROM wallets')
        total_supply = cursor.fetchone()[0] or 0
        
        # Pegar último bloco para timestamp
        cursor.execute('SELECT timestamp FROM blocks ORDER BY timestamp DESC LIMIT 1')
        last_block = cursor.fetchone()
        last_update = format_timestamp(last_block[0]) if last_block else 'Nunca'
        
        return jsonify({
            'total_blocks': total_blocks,
            'total_contracts': total_contracts,
            'total_supply': total_supply,
            'online_mode': ONLINE_MODE,
            'last_update': last_update
        })

@app.route('/api/contracts/pending')
def get_pending_contracts():
    blockchain = get_blockchain()
    contracts = blockchain.get_pending_contracts_in_region(-90, 90, -180, 180)
    return jsonify(contracts)

# Endpoints de Wallet
@app.route('/api/wallet/create', methods=['POST'])
def create_wallet():
    try:
        wallet_data = generate_wallet()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO wallets (address, public_key, balance, created_at)
                VALUES (?, ?, 0, ?)
            ''', (
                wallet_data['address'],
                hashlib.sha256(wallet_data['private_key'].encode()).hexdigest(),  # Hash da chave privada
                get_current_timestamp()
            ))
            conn.commit()
            
        return jsonify({
            'success': True,
            'address': wallet_data['address'],
            'privateKey': wallet_data['private_key'],
            'mnemonic': wallet_data['mnemonic']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/<address>/balance')
def get_wallet_balance(address):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM wallets WHERE address = ?', (address,))
            result = cursor.fetchone()
            
            if result:
                return jsonify({
                    'success': True,
                    'balance': result[0]
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Wallet não encontrada'
                }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/<address>/transactions')
def get_wallet_transactions(address):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE from_address = ? OR to_address = ?
                ORDER BY timestamp DESC LIMIT 50
            ''', (address, address))
            
            transactions = []
            for row in cursor.fetchall():
                transactions.append({
                    'hash': row[0],
                    'from': row[1],
                    'to': row[2],
                    'amount': row[3],
                    'timestamp': row[4],
                    'confirmed': row[5]
                })
                
            return jsonify({
                'success': True,
                'transactions': transactions
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Endpoints de Mineração
@app.route('/api/mining/config')
def get_mining_config():
    blockchain = get_blockchain()
    last_block = blockchain.get_last_block()
    
    template = {
        'previous_hash': last_block['hash'] if last_block else None,
        'height': blockchain.get_height(),
        'difficulty': MINING_DIFFICULTY,
        'timestamp': get_current_timestamp()
    }
    
    return jsonify({
        'success': True,
        'difficulty': MINING_DIFFICULTY,
        'blockTemplate': template
    })

@app.route('/api/mining/submit', methods=['POST'])
def submit_block():
    data = request.json
    if not data or not all(k in data for k in ('address', 'nonce', 'hash', 'timestamp')):
        return jsonify({
            'success': False,
            'error': 'Dados incompletos'
        }), 400
        
    # Verificar solução
    if not data['hash'].startswith('0' * MINING_DIFFICULTY):
        return jsonify({
            'success': False,
            'error': 'Solução inválida'
        }), 400
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Adicionar recompensa à wallet do minerador
            cursor.execute('''
                UPDATE wallets 
                SET balance = balance + ?
                WHERE address = ?
            ''', (BLOCK_REWARD, data['address']))
            
            # Registrar transação de recompensa
            reward_tx_hash = hashlib.sha256(f"reward-{data['hash']}".encode()).hexdigest()
            cursor.execute('''
                INSERT INTO transactions (hash, from_address, to_address, amount, timestamp, confirmed)
                VALUES (?, 'SYSTEM', ?, ?, ?, 1)
            ''', (reward_tx_hash, data['address'], BLOCK_REWARD, data['timestamp']))
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'reward': BLOCK_REWARD
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Endpoints de Transações
@app.route('/api/transactions/send', methods=['POST'])
def send_transaction():
    data = request.json
    if not data or not all(k in data for k in ('from', 'to', 'amount', 'privateKey')):
        return jsonify({
            'success': False,
            'error': 'Dados incompletos'
        }), 400
        
    # Verificar chave privada
    public_key = hashlib.sha256(data['privateKey'].encode()).hexdigest()
    address = 'LGC' + public_key[:40]
    if address != data['from']:
        return jsonify({
            'success': False,
            'error': 'Chave privada inválida'
        }), 401
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Verificar saldo
            cursor.execute('SELECT balance FROM wallets WHERE address = ?', (data['from'],))
            result = cursor.fetchone()
            if not result or result[0] < data['amount']:
                return jsonify({
                    'success': False,
                    'error': 'Saldo insuficiente'
                }), 400
            
            # Criar hash da transação
            tx_data = f"{data['from']}{data['to']}{data['amount']}{get_current_timestamp()}"
            tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()
            
            # Registrar transação
            cursor.execute('''
                INSERT INTO transactions (hash, from_address, to_address, amount, timestamp, confirmed)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (tx_hash, data['from'], data['to'], data['amount'], get_current_timestamp()))
            
            # Atualizar saldos
            cursor.execute('''
                UPDATE wallets 
                SET balance = balance - ?
                WHERE address = ?
            ''', (data['amount'], data['from']))
            
            cursor.execute('''
                UPDATE wallets 
                SET balance = balance + ?
                WHERE address = ?
            ''', (data['amount'], data['to']))
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'hash': tx_hash
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Rotas da API de entrega
@app.route('/api/delivery/submit', methods=['POST'])
def submit_delivery():
    """Submete nova prova de entrega"""
    try:
        data = request.get_json()
        
        # Validar dados obrigatórios
        required = [
            'contract_id', 'delivery_id', 'driver_address',
            'receiver_address', 'pickup_coords', 'delivery_coords',
            'pickup_time', 'delivery_time', 'distance_km',
            'photos', 'driver_key', 'receiver_key'
        ]
        
        if not all(key in data for key in required):
            return jsonify({
                'success': False,
                'error': 'Dados incompletos'
            }), 400
        
        # Adicionar prova
        blockchain = get_blockchain()
        proof_hash = blockchain.add_delivery_proof(
            contract_id=data['contract_id'],
            delivery_id=data['delivery_id'],
            driver_address=data['driver_address'],
            receiver_address=data['receiver_address'],
            pickup_coords=tuple(data['pickup_coords']),
            delivery_coords=tuple(data['delivery_coords']),
            pickup_time=data['pickup_time'],
            delivery_time=data['delivery_time'],
            distance_km=data['distance_km'],
            photos=data['photos'],
            driver_key=data['driver_key'],
            receiver_key=data['receiver_key']
        )
        
        if not proof_hash:
            return jsonify({
                'success': False,
                'error': 'Erro ao adicionar prova'
            }), 500
        
        return jsonify({
            'success': True,
            'proof_hash': proof_hash
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/delivery/history/<address>')
def get_delivery_history(address):
    """Retorna histórico de entregas"""
    try:
        blockchain = get_blockchain()
        proofs = blockchain.get_delivery_proofs(address=address)
        
        return jsonify({
            'success': True,
            'proofs': proofs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/delivery/contract/<contract_id>')
def get_contract_deliveries(contract_id):
    """Retorna entregas de um contrato"""
    try:
        blockchain = get_blockchain()
        proofs = blockchain.get_delivery_proofs(contract_id=contract_id)
        
        return jsonify({
            'success': True,
            'proofs': proofs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/wallet/login', methods=['POST'])
def login_wallet():
    """Login usando frase mnemônica"""
    mnemonic = request.json.get('mnemonic')
    if not mnemonic:
        return jsonify({
            'success': False,
            'error': 'Frase mnemônica não fornecida'
        }), 400
        
    try:
        wallet_data = recover_wallet_from_mnemonic(mnemonic)
        if not wallet_data:
            return jsonify({
                'success': False,
                'error': 'Frase mnemônica inválida'
            }), 400

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Verificar se a wallet já existe
            cursor.execute('SELECT balance FROM wallets WHERE address = ?', (wallet_data['address'],))
            result = cursor.fetchone()
            
            if not result:
                # Se não existir, criar nova wallet
                cursor.execute('''
                    INSERT INTO wallets (address, public_key, balance, created_at)
                    VALUES (?, ?, 0, ?)
                ''', (
                    wallet_data['address'],
                    hashlib.sha256(wallet_data['private_key'].encode()).hexdigest(),
                    get_current_timestamp()
                ))
                conn.commit()
                balance = 0
            else:
                balance = result[0]

        return jsonify({
            'success': True,
            'address': wallet_data['address'],
            'privateKey': wallet_data['private_key'],
            'balance': balance
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Inicializar banco de dados
    init_database()
    
    # Iniciar servidor
    app.run(host='0.0.0.0', port=5000, debug=True) 