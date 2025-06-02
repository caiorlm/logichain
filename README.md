# LogiChain

A decentralized, coordinate-based blockchain for real-world logistics and delivery tracking.

LogiChain is an innovative blockchain system designed for logistics, built in Python. It verifies Proof of Delivery (PoD) through secure geolocated checkpoints, tracks regional reputation, and fairly distributes rewards using smart contracts based on real-world coordinates.

---

## Key Features

* Decentralized smart contracts with real-world geocoordinates
* Proof of Delivery (PoD) verification via cryptographic checkpoints
* Fair reward system based on region and delivery reputation
* Modular blockchain with hybrid consensus (PoW + PoD + BFT)
* Encrypted logs and tamper-resistant data
* Simulation tools and REST API included

---

## System Architecture

```
logichain/
├── core/
│   ├── blockchain.py         # Blockchain coordination & block creation
│   ├── coordinate_grid.py    # Global coordinate grid (65,341 zones)
│   ├── contract.py           # Smart contract engine
│   └── block.py              # Block structure & validation
├── consensus/
│   ├── bft_consensus.py      # Byzantine Fault Tolerant logic
│   └── hybrid_consensus.py   # Hybrid PoW/PoD consensus mechanism
├── security/
│   ├── security_manager.py   # Replay protection, anomaly detection
│   └── contracts/pod_contract.py # Proof of Delivery contracts
├── network/
│   ├── p2p_network.py        # Peer-to-peer communication
│   └── node.py               # Node logic & message relay
├── tokenomics/
│   ├── tokenomics.py         # Token distribution & halving
│   └── wallet.py             # Wallets & user balances
├── api/
│   └── rest_api.py           # FastAPI backend interface
├── simulator/
│   └── delivery_simulator.py # Delivery scenario testing
├── storage/
│   └── persistence.py        # Data persistence & recovery
└── tests/
    ├── test_integration.py   # System-wide integration tests
    └── test_stress.py        # Load and stress testing
```

---

## Security Architecture

* Replay protection: Nonce cache validation
* Integrity: Hash-chained logs
* Checkpoint control: Geofencing + timestamp proof
* Anomaly detection: Contract frequency and misuse alerts
* Contract expiration: Automatic time-based lockout
* Rate limiting: Max transactions per coordinate region
* Configurable thresholds:

  * MAX\_OPERATIONS\_PER\_MINUTE = 60
  * MAX\_COORDINATE\_OPS = 100
  * TIMESTAMP\_TOLERANCE = 300
  * BACKUP\_INTERVAL = 3600

---

## Coordinate Grid

* 181 × 361 coordinate grid (lat: -90~~90, lng: -180~~180)
* 65,341 zones tracked
* Stats per coordinate:

  * Total contracts
  * Success rate
  * Avg. delivery time
  * Last activity timestamp

---

## Wallet Metrics

```python
class WalletMetrics:
    total_deliveries: int
    total_revenue: float
    completed_contracts: int
    avg_rating: float
    reputation_score: float
```

---

## Contract Lifecycle

* ContractState handles state transitions
* Checkpoints include:

  * Timestamp
  * GPS coordinates
  * Temperature / Humidity
  * Shock detection
* Timestamps validated against tolerance

---

## Simulated Deliveries

```python
def generate_contract_data():
    return {
        'cargo_type': ['Electronics', 'Food', 'Clothing', 'Materials'],
        'weight': random.uniform(1, 1000),
        'volume': random.uniform(1, 100),
        'priority': ['Low', 'Medium', 'High', 'Urgent'],
        'estimated_value': random.uniform(100, 10000)
    }
```

---

## Network Configuration

* P2P default port: 30303
* API default port: 8545
* Max peers: 50
* Mandatory: SSL/TLS encryption

---

## Tokenomics

```python
@dataclass
class TokenDistribution:
    genesis_wallets: int = 1000
    initial_balance: int = 1000
    total_initial_supply: int = genesis_wallets * initial_balance
    max_supply: int = 100_000_000
```

* Halving every 4 years
* Mining rewards split between:

  * Delivery drivers
  * Validator pools

---

## Testing Framework

* Integration Tests
* Stress Tests:

  * 1000 contracts
  * 5 checkpoints each
  * Multi-threaded
  * Batches of 50 ops

---

## Frontend (React)

* InteractiveMap: Geocoordinate visualization
* GlobalStats: Realtime metrics dashboard
* ContractList: Browse/filter contracts
* SecurityLog: View security alerts
* DeliverySimulator: Simulate full cycle

---

## Logging & Monitoring

Tracks:

* Wallet creation
* Contract events
* PoD checkpoints
* Security incidents
* State changes

---

## License

MIT License — see `LICENSE` file.

---

## Contact

Developed by Caio RLM — Contributions welcome!
