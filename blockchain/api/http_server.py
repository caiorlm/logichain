"""
Simple HTTP server for LogiChain API
Uses only standard Python libraries
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
from typing import Dict, Any
from urllib.parse import parse_qs, urlparse
from ..bridge.bridge_service import BridgeService, ChainType
from ..bridge.custody_service import CustodyService

class LogiChainRequestHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler"""
    
    def __init__(self, *args, **kwargs):
        self.bridge_service = kwargs.pop('bridge_service', None)
        self.custody_service = kwargs.pop('custody_service', None)
        super().__init__(*args, **kwargs)
        
    def _send_response(self, data: Dict[str, Any], status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
        
    def _send_error(self, message: str, status: int = 400):
        """Send error response"""
        self._send_response({
            'error': message
        }, status)
        
    def _get_json_body(self) -> Dict[str, Any]:
        """Get JSON request body"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        return json.loads(body.decode())
        
    def do_POST(self):
        """Handle POST requests"""
        try:
            if self.path == '/bridge/transfer':
                # Create bridge transfer
                body = self._get_json_body()
                
                try:
                    from_chain = ChainType(body['from_chain'])
                    to_chain = ChainType(body['to_chain'])
                except ValueError:
                    self._send_error('Invalid chain type')
                    return
                    
                bridge_tx = self.bridge_service.create_bridge_transaction(
                    from_chain=from_chain,
                    to_chain=to_chain,
                    from_address=body['from_address'],
                    to_address=body['to_address'],
                    amount=float(body['amount'])
                )
                
                self._send_response({
                    'tx_hash': bridge_tx.tx_hash,
                    'from_chain': bridge_tx.from_chain.value,
                    'to_chain': bridge_tx.to_chain.value,
                    'from_address': bridge_tx.from_address,
                    'to_address': bridge_tx.to_address,
                    'amount': bridge_tx.amount,
                    'fee': bridge_tx.fee,
                    'status': bridge_tx.status
                })
                
            else:
                self._send_error('Not found', 404)
                
        except Exception as e:
            logging.error(f'Error handling request: {e}')
            self._send_error('Internal server error', 500)
            
    def do_GET(self):
        """Handle GET requests"""
        try:
            url = urlparse(self.path)
            
            if url.path == '/bridge/transaction':
                # Get bridge transaction
                params = parse_qs(url.query)
                tx_hash = params.get('tx_hash', [''])[0]
                
                if not tx_hash:
                    self._send_error('Missing tx_hash parameter')
                    return
                    
                tx = self.bridge_service.get_transaction(tx_hash)
                if not tx:
                    self._send_error('Transaction not found', 404)
                    return
                    
                self._send_response({
                    'tx_hash': tx.tx_hash,
                    'from_chain': tx.from_chain.value,
                    'to_chain': tx.to_chain.value,
                    'from_address': tx.from_address,
                    'to_address': tx.to_address,
                    'amount': tx.amount,
                    'fee': tx.fee,
                    'status': tx.status
                })
                
            elif url.path == '/bridge/rates':
                # Get exchange rates
                params = parse_qs(url.query)
                chain = params.get('chain', [''])[0]
                
                try:
                    chain_type = ChainType(chain)
                except ValueError:
                    self._send_error('Invalid chain type')
                    return
                    
                rate = self.bridge_service.get_exchange_rate(chain_type)
                self._send_response({
                    'chain': chain,
                    'rate': rate
                })
                
            elif url.path == '/bridge/custody/status':
                # Get custody status
                self._send_response(
                    self.custody_service.get_status()
                )
                
            elif url.path == '/bridge/custody/balances':
                # Get custody balances
                self.custody_service.update_balances()
                self._send_response(
                    self.custody_service.get_balances()
                )
                
            elif url.path == '/bridge/supported_chains':
                # Get supported chains
                self._send_response({
                    chain.value: {
                        'name': chain.value.title(),
                        'min_amount': min_amount,
                        'confirmations': confirmations
                    }
                    for chain, (min_amount, confirmations) in {
                        ChainType.ETHEREUM: (0.01, 12),
                        ChainType.BINANCE: (0.1, 15),
                        ChainType.POLYGON: (10, 128),
                        ChainType.AVALANCHE: (1, 12)
                    }.items()
                })
                
            else:
                self._send_error('Not found', 404)
                
        except Exception as e:
            logging.error(f'Error handling request: {e}')
            self._send_error('Internal server error', 500)
            
    def do_OPTIONS(self):
        """Handle OPTIONS requests (CORS)"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def run_server(
    host: str,
    port: int,
    bridge_service: BridgeService,
    custody_service: CustodyService
):
    """Run HTTP server"""
    
    def handler(*args):
        """Create handler with services"""
        return LogiChainRequestHandler(
            *args,
            bridge_service=bridge_service,
            custody_service=custody_service
        )
        
    server = HTTPServer((host, port), handler)
    logging.info(f'Starting server on {host}:{port}')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info('Shutting down server')
        server.server_close() 