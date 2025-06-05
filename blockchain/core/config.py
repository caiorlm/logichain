"""
Configurações globais do sistema LogiChain
"""

import os
from dotenv import load_dotenv
from typing import Dict, Any

# Carrega variáveis de ambiente
load_dotenv()

class GovernanceConstants:
    """Constantes de governança"""
    CONSENSUS_THRESHOLD = int(os.getenv("CONSENSUS_THRESHOLD", "66"))
    VOTING_PERIOD_BLOCKS = int(os.getenv("VOTING_PERIOD_BLOCKS", "100"))
    MIN_STAKE = int(os.getenv("MIN_STAKE", "1000"))

class GenesisVariables:
    """Variáveis do bloco gênesis"""
    CHAIN_ID = int(os.getenv("CHAIN_ID", "1"))
    NETWORK = os.getenv("NETWORK", "testnet")

class PoDConfig:
    """Configurações do Proof of Delivery"""
    MIN_ACCURACY = float(os.getenv("MIN_ACCURACY", "10.0"))
    MAX_TIME_DRIFT = int(os.getenv("MAX_TIME_DRIFT", "300"))
    CHECKPOINT_INTERVAL = int(os.getenv("CHECKPOINT_INTERVAL", "15"))

def get_all_config() -> Dict[str, Any]:
    """Retorna todas as configurações em um dicionário"""
    return {
        "governance": {k: v for k, v in vars(GovernanceConstants).items() if not k.startswith("_")},
        "genesis": {k: v for k, v in vars(GenesisVariables).items() if not k.startswith("_")},
        "pod": {k: v for k, v in vars(PoDConfig).items() if not k.startswith("_")}
    } 