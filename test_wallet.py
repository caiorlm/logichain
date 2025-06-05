"""
Test script for wallet functionality
"""

import os
import time
import json
import hashlib
import sqlite3
from wallet_manager import WalletManager
from simple_miner import SimpleMiner
from colorama import init, Fore, Style

# Initialize colorama
init()

def test_wallet_creation():
    print(f"\n{Fore.BLUE}Testing wallet creation...{Style.RESET_ALL}")
    wm = WalletManager()
    
    # Create new wallet
    wallet = wm.create_wallet()
    print(f"Created wallet with address: {wallet['address']}")
    print(f"Mnemonic phrase: {wallet['mnemonic']}")
    
    # List wallets
    wallets = wm.list_wallets()
    print(f"\nTotal wallets: {len(wallets)}")
    return wallet

def test_wallet_recovery(original_wallet):
    print(f"\n{Fore.BLUE}Testing wallet recovery...{Style.RESET_ALL}")
    wm = WalletManager()
    
    # Recover wallet from mnemonic
    recovered = wm.recover_wallet(original_wallet["mnemonic"])
    if recovered:
        print(f"Recovered wallet address: {recovered['address']}")
        if recovered["address"] == original_wallet["address"]:
            print(f"{Fore.GREEN}✓ Recovery successful - addresses match{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Recovery failed - addresses don't match{Style.RESET_ALL}")
            print(f"Original address: {original_wallet['address']}")
            print(f"Recovered address: {recovered['address']}")
    return recovered

def test_wallet_import_export(wallet):
    print(f"\n{Fore.BLUE}Testing wallet import/export...{Style.RESET_ALL}")
    wm = WalletManager()
    
    # Export wallet
    export_path = "data/wallets/test_export.json"
    wm.export_wallet(wallet["address"], export_path)
    print(f"Exported wallet to: {export_path}")
    
    # Import wallet to new database
    new_db_path = "data/blockchain/test_chain.db"
    if os.path.exists(new_db_path):
        os.remove(new_db_path)
    
    wm_new = WalletManager(new_db_path)
    imported = wm_new.import_wallet(export_path)
    
    if imported:
        print(f"Imported wallet address: {imported['address']}")
        if imported["address"] == wallet["address"]:
            print(f"{Fore.GREEN}✓ Import successful - addresses match{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Import failed - addresses don't match{Style.RESET_ALL}")
    
    # Clean up
    os.remove(export_path)
    os.remove(new_db_path)
    return imported

def mine_blocks(miner_address, num_blocks=1):
    """Mine blocks properly using the mining process"""
    print(f"\n{Fore.BLUE}Mining {num_blocks} blocks...{Style.RESET_ALL}")
    miner = SimpleMiner()
    
    for i in range(num_blocks):
        # Create mining reward transaction
        reward_tx = {
            'from_address': '0' * 64,  # System reward
            'to_address': miner_address,
            'amount': 50.0,  # Standard block reward
            'timestamp': time.time(),
            'nonce': 0
        }
        
        # Mine block
        block = miner.mine_block([reward_tx])
        if block:
            print(f"Mined block with hash: {block['hash'][:8]}...")
        else:
            print(f"{Fore.RED}Failed to mine block{Style.RESET_ALL}")
            return False
            
    return True

def test_transactions():
    print(f"\n{Fore.BLUE}Testing transactions...{Style.RESET_ALL}")
    wm = WalletManager()
    
    # Create two wallets
    wallet1 = wm.create_wallet()
    wallet2 = wm.create_wallet()
    print(f"Created wallet1: {wallet1['address']}")
    print(f"Created wallet2: {wallet2['address']}")
    
    # Mine some blocks to get rewards
    if not mine_blocks(wallet1["address"], 2):
        raise Exception("Failed to mine blocks")
    
    # Check balance
    balance = wm.get_balance(wallet1["address"])
    print(f"\nWallet1 balance after mining: {balance} LOGI")
    
    # Load wallet1
    wm.load_wallet(wallet1["address"])
    
    # Create transaction
    amount = 10.0
    tx = wm.create_transaction(wallet2["address"], amount)
    print(f"\nCreated transaction:")
    print(f"From: {tx['from_address']}")
    print(f"To: {tx['to_address']}")
    print(f"Amount: {tx['amount']} LOGI")
    print(f"Nonce: {tx['nonce']}")
    
    # Verify transaction
    is_valid = wm.verify_transaction(tx)
    print(f"\nTransaction verification: {'✓' if is_valid else '✗'}")
    
    # Test invalid signature
    tx_invalid = tx.copy()
    tx_invalid["signature"] = "invalid"
    is_valid = wm.verify_transaction(tx_invalid)
    print(f"Invalid signature verification: {'✗' if not is_valid else '✓'}")
    
    return tx

def main():
    try:
        # Test wallet creation
        wallet = test_wallet_creation()
        
        # Test wallet recovery
        recovered = test_wallet_recovery(wallet)
        
        # Test import/export
        imported = test_wallet_import_export(wallet)
        
        # Test transactions
        tx = test_transactions()
        
    except Exception as e:
        print(f"\n{Fore.RED}Error during testing: {e}{Style.RESET_ALL}")
        raise

if __name__ == "__main__":
    main() 