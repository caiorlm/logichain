"""
Wallet CLI interface
"""

import cmd
import sys
import logging
from typing import Optional
from mnemonic import Mnemonic
from ..core.wallet import Wallet
from .. import LogiChain

logger = logging.getLogger(__name__)

class WalletCLI(cmd.Cmd):
    """Wallet CLI interface"""
    
    intro = 'Welcome to the LogiChain wallet CLI. Type help or ? to list commands.\n'
    prompt = '(wallet) '
    
    def __init__(self):
        super().__init__()
        self.wallet = None
        self.mnemo = Mnemonic("english")
        try:
            # Connect to blockchain
            self.blockchain = LogiChain()
            print("Connected to LogiChain network")
        except Exception as e:
            print(f"Warning: Could not connect to blockchain: {e}")
            self.blockchain = None
        
    def do_create(self, arg):
        """Create a new wallet: create [password]"""
        try:
            password = arg.strip() if arg else None
            self.wallet = Wallet.create(password)
            print("Created new wallet")
            print(f"Address: {self.wallet.address}")
            print("\nIMPORTANT: Save your mnemonic phrase securely:")
            print(self.wallet.mnemonic)
            
            if self.blockchain:
                print("\nBlockchain connection status: LIVE")
            else:
                print("\nBlockchain connection status: OFFLINE")
                
        except Exception as e:
            print(f"Error creating wallet: {e}")
            
    def do_load(self, arg):
        """Load existing wallet from mnemonic: load <mnemonic> [password]"""
        try:
            args = arg.split()
            if not args:
                print("Error: Mnemonic phrase required")
                return
                
            mnemonic = args[0]
            password = args[1] if len(args) > 1 else None
            
            self.wallet = Wallet.from_mnemonic(mnemonic, password)
            print(f"Loaded wallet with address: {self.wallet.address}")
            
            if self.blockchain:
                print("Blockchain connection status: LIVE")
            else:
                print("Blockchain connection status: OFFLINE")
                
        except Exception as e:
            print(f"Error loading wallet: {e}")
            
    def do_status(self, arg):
        """Show blockchain connection status"""
        if self.blockchain:
            print("Blockchain connection status: LIVE")
            print("Network is operational")
        else:
            print("Blockchain connection status: OFFLINE")
            print("Not connected to the network")
            
    def do_info(self, arg):
        """Show wallet information"""
        if not self.wallet:
            print("No wallet loaded. Use 'create' or 'load' first.")
            return
            
        try:
            print("\nWallet Information:")
            print(f"Address: {self.wallet.address}")
            print(f"Public Key: {self.wallet.get_public_key()}")
            print(f"\nBlockchain connection: {'LIVE' if self.blockchain else 'OFFLINE'}")
        except Exception as e:
            print(f"Error getting wallet info: {e}")
            
    def do_exit(self, arg):
        """Exit the wallet CLI"""
        print("Goodbye!")
        return True
        
    def do_quit(self, arg):
        """Exit the wallet CLI"""
        return self.do_exit(arg)

def main():
    """Main entry point"""
    try:
        WalletCLI().cmdloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 