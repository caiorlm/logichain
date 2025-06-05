import sqlite3
from colorama import init, Fore, Style

# Initialize colorama
init()

def check_wallets():
    try:
        conn = sqlite3.connect('data/blockchain/chain.db')
        cursor = conn.cursor()

        # Get unique addresses from transactions (both senders and receivers)
        cursor.execute('''
            SELECT COUNT(DISTINCT address) as total_wallets
            FROM (
                SELECT from_address as address FROM transactions 
                WHERE from_address != '0000000000000000000000000000000000000000000000000000000000000000'
                UNION
                SELECT to_address as address FROM transactions
                WHERE to_address != '0000000000000000000000000000000000000000000000000000000000000000'
            )
        ''')
        total = cursor.fetchone()[0]
        print(f'\n{Fore.GREEN}Total unique wallets: {total}{Style.RESET_ALL}')

        # Show wallet details
        cursor.execute('''
            SELECT 
                address,
                COUNT(*) as total_transactions,
                (SELECT COUNT(*) FROM blocks WHERE miner_address = address) as blocks_mined,
                (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE to_address = address
                ) as total_received,
                (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE from_address = address
                    AND from_address != '0000000000000000000000000000000000000000000000000000000000000000'
                ) as total_sent
            FROM (
                SELECT from_address as address FROM transactions 
                WHERE from_address != '0000000000000000000000000000000000000000000000000000000000000000'
                UNION ALL
                SELECT to_address as address FROM transactions
                WHERE to_address != '0000000000000000000000000000000000000000000000000000000000000000'
            )
            GROUP BY address
            ORDER BY total_transactions DESC
            LIMIT 5
        ''')

        print(f'\n{Fore.YELLOW}Top 5 most active wallets:{Style.RESET_ALL}')
        print(f'{Fore.CYAN}{"Address":<64} | {"Transactions":^12} | {"Blocks Mined":^12} | {"Received LOGI":^12} | {"Sent LOGI":^12}{Style.RESET_ALL}')
        print('-' * 120)
        
        for row in cursor.fetchall():
            address, tx_count, blocks_mined, received, sent = row
            print(f'{address} | {tx_count:^12} | {blocks_mined:^12} | {received:^12.2f} | {sent:^12.2f}')

        # Get mining statistics
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT miner_address) as total_miners,
                COUNT(*) as total_blocks,
                AVG(mining_reward) as avg_reward
            FROM blocks
            WHERE miner_address != '0000000000000000000000000000000000000000000000000000000000000000'
        ''')
        
        miners_stats = cursor.fetchone()
        print(f'\n{Fore.YELLOW}Mining Statistics:{Style.RESET_ALL}')
        print(f'Total Miners: {miners_stats[0]}')
        print(f'Total Blocks: {miners_stats[1]}')
        print(f'Average Reward: {miners_stats[2]:.2f} LOGI')

    except Exception as e:
        print(f'{Fore.RED}Error checking wallets: {e}{Style.RESET_ALL}')
    finally:
        conn.close()

if __name__ == "__main__":
    check_wallets() 