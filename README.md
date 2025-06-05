# LogiChain - Sistema de Blockchain

Sistema completo de blockchain com gerenciamento de carteiras, mineração e transações.

## Estrutura do Sistema

O sistema é composto pelos seguintes módulos:

- `wallet_manager.py`: Gerenciamento de carteiras e saldos
- `mining_manager.py`: Controle de mineração e recompensas
- `transaction_manager.py`: Gerenciamento de transações e mempool
- `blockchain_monitor.py`: Monitoramento e validação contínua
- `init_and_validate.py`: Inicialização e validação do sistema

## Requisitos

- Python 3.7+
- SQLite3
- Dependências listadas em `requirements.txt`

## Instalação

1. Clone o repositório
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Inicialização

Para inicializar o sistema pela primeira vez:

```bash
python init_and_validate.py
```

Este script irá:
1. Criar as estruturas de diretórios necessárias
2. Inicializar o banco de dados
3. Criar o bloco gênesis (se necessário)
4. Validar a integridade da blockchain
5. Verificar todas as transações
6. Recalcular os saldos das carteiras
7. Gerar relatórios iniciais

## Monitoramento

Para iniciar o monitoramento contínuo:

```bash
python blockchain_monitor.py
```

O monitor irá:
- Verificar a integridade da blockchain a cada 10 minutos
- Gerar relatórios diários
- Alertar sobre problemas encontrados

## Estrutura de Diretórios

```
data/
  blockchain/     # Banco de dados da blockchain
  reports/        # Relatórios gerados
  logs/          # Logs do sistema
```

## Funcionalidades

### Carteiras

- Criação e gerenciamento de carteiras
- Rastreamento de saldos
- Proteção contra saldo negativo
- Histórico de transações

### Mineração

- Proof of Work com dificuldade ajustável
- Recompensas de mineração
- Validação de blocos
- Processamento de transações pendentes

### Transações

- Validação de transações
- Mempool com prioridade por taxa
- Proteção contra duplo gasto
- Rastreamento de status

### Monitoramento

- Verificação de integridade da cadeia
- Validação de transações
- Recálculo de saldos
- Geração de relatórios

## Relatórios

O sistema gera três tipos de relatórios:

1. Relatório de Carteiras (`wallets_*.csv/json`)
   - Endereço
   - Saldo
   - Total recebido/enviado
   - Recompensas de mineração
   - Blocos minerados

2. Relatório de Mineração (`mining_*.csv/json`)
   - Endereço do minerador
   - Blocos minerados
   - Recompensas totais
   - Primeiro/último bloco

3. Relatório de Transações (`transactions_*.csv/json`)
   - Hash da transação
   - Tipo
   - Origem/destino
   - Valor
   - Status

## Segurança

O sistema implementa várias medidas de segurança:

- Validação de saldo antes de transações
- Proteção contra duplo gasto
- Verificação de encadeamento de blocos
- Validação de Proof of Work
- Monitoramento contínuo

## Contribuindo

1. Fork o repositório
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Crie um Pull Request

## Licença

Este projeto está licenciado sob a MIT License.

## Support

For support, please open an issue in the GitHub repository or contact the development team.

## Acknowledgments

- LoRa Technology by Semtech
- Cryptographic libraries contributors
- Open source blockchain community

# Blockchain Storage Migration

## Overview
This repository contains a blockchain implementation that has been updated to use a Bitcoin Core-like storage system. The new storage system replaces the previous SQLite database with a more efficient and scalable file-based solution.

## Storage System
The new storage system follows Bitcoin Core's approach:

```
/blocks/
    - blk00000.dat  # Block data files
    - blk00001.dat
    - ...
/chainstate/
    - CURRENT       # Current active database version
    - MANIFEST     # List of database files
    - LOG         # Database log
    /blocks/      # Block index
    /coins/      # UTXO set
    /wallets/    # Wallet data
```

## Migration Process
To migrate your existing SQLite database to the new storage system, follow these steps:

1. **Backup**
   The migration process will automatically create a backup of your SQLite database at `data/blockchain/chain.db.backup`.

2. **Migration**
   Run the migration script:
   ```bash
   python migrate_all.py
   ```

   This script will:
   - Migrate all data to the new storage system
   - Verify the migration
   - Clean up the old SQLite database (after confirmation)

3. **Verification**
   You can verify the new storage system separately:
   ```bash
   python verify_chaindb.py
   ```

4. **Cleanup**
   To clean up the old SQLite database after a successful migration:
   ```bash
   python cleanup_sqlite.py
   ```

## Individual Scripts
- `migrate_to_chaindb.py`: Performs the actual migration
- `verify_chaindb.py`: Verifies the new storage system
- `cleanup_sqlite.py`: Cleans up the old SQLite database
- `migrate_all.py`: Runs the complete migration process

## Recovery
If something goes wrong during migration:
1. The original SQLite database is preserved at `data/blockchain/chain.db.backup`
2. You can restore it by copying it back to `data/blockchain/chain.db`

## New Features
The new storage system provides:
- Better scalability for large blockchains
- Improved performance for block and transaction queries
- Bitcoin Core-like storage format
- Better data integrity with separate block files
- Efficient UTXO set management

## Requirements
- Python 3.7+
- No additional dependencies required

## Notes
- The migration process is non-destructive
- Your original data is backed up automatically
- The process can be resumed if interrupted
- All wallet balances and transaction history are preserved 