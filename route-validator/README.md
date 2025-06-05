# Route Validator

Sistema descentralizado de validação de rotas para entregadores, com integração blockchain.

## Características

- Coleta de GPS local (sem dependência de APIs externas)
- Validação por perímetro configurável
- Armazenamento local em SQLite
- Integração com blockchain para Proof of Delivery
- API REST para integração
- Suporte a múltiplos dispositivos (Android, iOS, Linux embarcado)

## Requisitos

- Rust 1.70+
- SQLite 3.x
- GPS local ou dispositivo compatível

## Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/route-validator

# Entre no diretório
cd route-validator

# Compile o projeto
cargo build --release
```

## Configuração

O sistema aceita as seguintes variáveis de ambiente:

- `VALIDATOR_PORT`: Porta da API REST (default: 8080)
- `VALIDATOR_DB`: Caminho do banco SQLite (default: routes.db)
- `VALIDATOR_GPS_DEVICE`: Dispositivo GPS (ex: /dev/ttyUSB0)
- `VALIDATOR_BLOCKCHAIN_URL`: URL do nó blockchain
- `VALIDATOR_CONTRACT`: Endereço do contrato na blockchain

## Uso

### 1. Iniciar o servidor

```bash
cargo run --release
```

### 2. API REST

#### Iniciar rota
```bash
curl -X POST http://localhost:8080/start \
  -H "Content-Type: application/json" \
  -d '{"contract_id": "123", "tolerance_radius": 50, "max_error": 100}'
```

#### Adicionar ponto
```bash
curl -X POST http://localhost:8080/point \
  -H "Content-Type: application/json" \
  -d '{"latitude": -23.550520, "longitude": -46.633308}'
```

#### Finalizar rota
```bash
curl -X POST http://localhost:8080/end
```

## Segurança

- Assinatura digital de pontos
- Validação de timestamp
- Proteção contra manipulação de coordenadas
- Proof of Delivery na blockchain

## Desenvolvimento

### Estrutura do Projeto

```
src/
├── main.rs           # Ponto de entrada
├── core/             # Lógica central
├── gps/              # Coleta de GPS
├── storage/          # Armazenamento local
├── blockchain/       # Integração blockchain
└── api/              # API REST
```

### Testes

```bash
cargo test
```

## Licença

MIT 