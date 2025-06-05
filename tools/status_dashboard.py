"""
Dashboard de status da blockchain
"""

import os
import sys
import sqlite3
from pathlib import Path
import logging
import time
from datetime import datetime
import curses
import threading

# Adiciona o diretório raiz ao path para importar módulos
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from blockchain.database.db_manager import get_db_connection
from blockchain.wallet.key_manager import KeyManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='blockchain_status.log'
)

class BlockchainStatus:
    def __init__(self):
        self.key_manager = KeyManager()
        self.active_wallet = None
        self.update_interval = 2  # segundos
        self.should_run = True
        
    def get_blockchain_stats(self):
        """Obtém estatísticas da blockchain"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total de blocos
        cursor.execute("SELECT COUNT(*), MAX(block_index), MAX(timestamp) FROM blocks")
        total_blocks, last_block_index, last_block_time = cursor.fetchone()
        
        # Hash do último bloco
        cursor.execute("SELECT hash FROM blocks ORDER BY block_index DESC LIMIT 1")
        last_block_hash = cursor.fetchone()[0] if total_blocks > 0 else None
        
        # Total de transações na mempool
        cursor.execute("SELECT COUNT(*) FROM mempool WHERE status = 'pending'")
        mempool_count = cursor.fetchone()[0]
        
        # Carteira ativa e saldo
        active_wallet = self.key_manager.get_active_wallet()
        balance = 0.0
        if active_wallet:
            cursor.execute("SELECT balance FROM wallets WHERE address = ?", 
                         (active_wallet['address'],))
            result = cursor.fetchone()
            if result:
                balance = result[0]
        
        conn.close()
        
        return {
            'total_blocks': total_blocks,
            'last_block_index': last_block_index,
            'last_block_hash': last_block_hash,
            'last_block_time': datetime.fromtimestamp(last_block_time).strftime('%Y-%m-%d %H:%M:%S') if last_block_time else None,
            'mempool_count': mempool_count,
            'active_wallet': active_wallet['address'] if active_wallet else None,
            'balance': balance
        }
    
    def check_component_status(self):
        """Verifica status dos componentes"""
        status = {
            'database': True,
            'key_manager': True,
            'wallet': bool(self.key_manager.get_active_wallet()),
            'mempool': True
        }
        
        try:
            conn = get_db_connection()
            conn.execute("SELECT 1")
            conn.close()
        except:
            status['database'] = False
        
        try:
            self.key_manager.is_initialized()
        except:
            status['key_manager'] = False
            
        try:
            conn = get_db_connection()
            conn.execute("SELECT 1 FROM mempool LIMIT 1")
            conn.close()
        except:
            status['mempool'] = False
            
        return status
    
    def render_dashboard(self, stdscr):
        """Renderiza dashboard usando curses"""
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        
        while self.should_run:
            try:
                stats = self.get_blockchain_stats()
                status = self.check_component_status()
                
                stdscr.clear()
                
                # Título
                stdscr.addstr(0, 0, "🔗 BLOCKCHAIN STATUS DASHBOARD", curses.A_BOLD)
                stdscr.addstr(1, 0, "=" * 50)
                
                # Estatísticas da blockchain
                stdscr.addstr(3, 0, f"✔ Blocos carregados: {stats['total_blocks']}")
                if stats['last_block_hash']:
                    stdscr.addstr(4, 0, f"✔ Último bloco: {stats['last_block_hash'][:8]}...")
                    stdscr.addstr(5, 0, f"✔ Índice: {stats['last_block_index']}")
                    stdscr.addstr(6, 0, f"✔ Timestamp: {stats['last_block_time']}")
                
                # Informações da carteira
                if stats['active_wallet']:
                    stdscr.addstr(8, 0, f"✔ Carteira ativa: {stats['active_wallet'][:8]}...")
                    stdscr.addstr(9, 0, f"✔ Saldo atual: {stats['balance']:.2f} LOGI")
                else:
                    stdscr.addstr(8, 0, "⚠️  Nenhuma carteira ativa", curses.color_pair(3))
                
                # Mempool
                stdscr.addstr(11, 0, f"✔ Mempool: {stats['mempool_count']} transações")
                
                # Status dos componentes
                stdscr.addstr(13, 0, "STATUS DOS COMPONENTES")
                stdscr.addstr(14, 0, "-" * 30)
                
                for i, (component, is_ok) in enumerate(status.items()):
                    color = curses.color_pair(1) if is_ok else curses.color_pair(2)
                    status_text = "✅ OK" if is_ok else "❌ ERROR"
                    stdscr.addstr(15 + i, 0, f"{component.title():<15} {status_text}", color)
                
                # Rodapé
                stdscr.addstr(20, 0, "Pressione 'q' para sair | Atualização a cada 2s")
                stdscr.addstr(21, 0, f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")
                
                stdscr.refresh()
                time.sleep(self.update_interval)
                
            except KeyboardInterrupt:
                break
            except curses.error:
                continue
    
    def start(self):
        """Inicia o dashboard"""
        try:
            curses.wrapper(self.render_dashboard)
        except KeyboardInterrupt:
            self.should_run = False
        except Exception as e:
            logging.error(f"Erro no dashboard: {str(e)}")
            self.should_run = False

def main():
    """Função principal"""
    try:
        dashboard = BlockchainStatus()
        dashboard.start()
    except Exception as e:
        logging.error(f"Erro ao iniciar dashboard: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 