# Documentação da API LogiChain

## Core do Sistema

### main.py
Ponto de entrada principal do sistema que inicializa todos os componentes:
- Blockchain
- Rede P2P
- Sistema Oracle
- Sistema Bridge
- Configurações globais

### network.py
Implementação base da rede P2P:
- Gerenciamento de conexões entre nós
- Descoberta de peers
- Sincronização de estado
- Propagação de mensagens

### config.py
Configurações globais do sistema:
- Portas de rede
- Diretórios de dados
- Dificuldade de mineração
- Parâmetros de consenso

## Nós da Rede

### driver_node.py
Nó específico para motoristas:
- Gerenciamento de contratos de entrega
- Validação de rotas
- Provas de entrega
- Reputação do motorista

### establishment_node.py
Nó para estabelecimentos:
- Criação de contratos
- Validação de entregas
- Gestão de pagamentos
- Reputação do estabelecimento

### executor_node.py
Nó validador:
- Confirmação de blocos
- Execução de contratos
- Validação de transações
- Consenso da rede

## Genesis e Inicialização

### genesis_block.py
Define o bloco genesis:
```json
{
    "timestamp": 0,
    "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "transactions": [],
    "nonce": 0,
    "difficulty": 4
}
```

### GENESIS_BLOCK_OFFICIAL.json
Bloco genesis oficial serializado e imutável.

### GENESIS_BLOCK_OFFICIAL.sha256
Hash de verificação do bloco genesis para garantir integridade.

### genesis_reference.json
Referência para validação do genesis com parâmetros iniciais.

### initialize_blockchain.py
Script de inicialização da blockchain:
- Criação do bloco genesis
- Configuração inicial
- Setup do banco de dados
- Inicialização dos índices

### verify_genesis.py
Verifica a integridade do bloco genesis:
- Validação do hash
- Verificação da estrutura
- Confirmação dos parâmetros

## Servidores e APIs

### api_server.py
Servidor API principal:
- Rotas REST
- Gerenciamento de carteiras
- Transações
- Mineração
- Provas de entrega
- Estatísticas

### web_server.py
Servidor web para interface com usuário:
- Interface web
- API para carteiras
- Visualização de blocos
- Estatísticas em tempo real

### integrated_server.py
Servidor integrado:
- Interface web com blockchain
- Streaming de mineração
- API REST completa
- Sistema de provas de entrega

### gunicorn_config.py
Configuração do Gunicorn:
- Workers e threads
- Timeouts
- SSL/TLS
- Logging

## Segurança e Produção

### firewall_rules.py
Configuração de regras de firewall:
- Portas permitidas
- IPs autorizados
- Rate limiting
- Proteção DDoS

### generate_production_keys.py
Geração de chaves criptográficas:
- Chaves SSL
- Chaves de nós
- Chaves de API
- Tokens de segurança

### generate_ssl_certs.py
Geração de certificados SSL:
- Certificados auto-assinados
- CSRs
- Renovação automática
- Validação

### launch_production.py
Script de produção:
- Inicialização de serviços
- Verificações de segurança
- Monitoramento
- Backup automático

## Scripts de Execução

### run_node.py
Execução de nó individual:
```bash
python run_node.py --type driver --port 8000 --peers "node1:8001,node2:8002"
```

### start_mainnet.py
Inicialização da rede principal:
```bash
python start_mainnet.py --nodes 3 --genesis-file genesis.json
```

### clean_structure.ps1
Script PowerShell para organização:
```powershell
./clean_structure.ps1 -Target "production" -Backup $true
```

## Documentação

### README.md
Documentação principal com:
- Visão geral
- Instalação
- Configuração
- Exemplos

### LICENSE
Licença MIT do projeto.

### requirements.txt
Dependências Python:
```txt
cryptography>=41.0.0
fastapi==0.68.1
uvicorn==0.15.0
pydantic==1.8.2
aiohttp==3.8.1
websockets==12.0
``` 