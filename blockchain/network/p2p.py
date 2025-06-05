import threading
import socket
import json
import requests
from time import sleep

class P2PNetwork:
    def __init__(self, port, genesis_nodes=None):
        self.port = port
        self.peers = set(genesis_nodes) if genesis_nodes else set()
        self.running = False
        
    def start(self):
        """Inicia o servidor P2P em uma thread separada"""
        self.running = True
        threading.Thread(target=self._run_server).start()
        threading.Thread(target=self._discover_peers).start()
        
    def _run_server(self):
        """Executa o servidor P2P"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', self.port))
        server.listen(5)
        
        while self.running:
            try:
                client, address = server.accept()
                threading.Thread(target=self._handle_peer, args=(client,)).start()
            except:
                continue
                
    def _handle_peer(self, client):
        """Processa mensagens de outros nós"""
        try:
            data = client.recv(4096)
            if not data:
                return
            
            try:
                message = json.loads(data.decode())
                if message.get('type') == 'genesis':
                    # Atualiza o bloco genesis local
                    self._update_genesis(message.get('data'))
            except json.JSONDecodeError:
                print("Erro ao decodificar mensagem JSON")
        finally:
            client.close()
            
    def _discover_peers(self):
        """Descobre e conecta a novos peers"""
        while self.running:
            for peer in list(self.peers):
                try:
                    # Tenta conectar ao peer
                    response = requests.get(f'http://{peer}/api/network/stats')
                    if response.status_code == 200:
                        # Adiciona novos peers encontrados
                        new_peers = response.json().get('peers', [])
                        self.peers.update(new_peers)
                except:
                    self.peers.remove(peer)
            sleep(60)  # Espera 1 minuto antes de tentar novamente
            
    def broadcast_genesis(self, genesis_data):
        """Envia atualização do bloco genesis para todos os peers"""
        message = {
            'type': 'genesis',
            'data': genesis_data
        }
        
        for peer in self.peers:
            try:
                requests.post(
                    f'http://{peer}/api/p2p/sync',
                    json={'genesis_block': genesis_data}
                )
            except:
                continue
                
    def _update_genesis(self, genesis_data):
        """Atualiza o bloco genesis local"""
        try:
            requests.post(
                'http://localhost:5000/api/p2p/sync',
                json={'genesis_block': genesis_data}
            )
        except:
            pass 