"""
Blockchain System Bootstrap
Initializes system with mandatory trust core and quorum approval
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Optional

from security.critical_integrity_adapter import CriticalIntegrityAdapter
from security.trust_core import TrustCore, TrustState
from core.genesis_rules import GenesisRules

def load_genesis_block():
    """Load or create genesis block"""
    try:
        # Create default genesis rules
        rules = GenesisRules()
        
        # Generate genesis block
        return rules.to_genesis_block()
        
    except Exception as e:
        print(f"Failed to load genesis block: {e}")
        sys.exit(1)

def load_trusted_nodes() -> List[str]:
    """Load trusted node IDs"""
    try:
        base_dir = Path(__file__).parent
        nodes_file = base_dir / "security" / "trusted_nodes.json"
        
        with open(nodes_file) as f:
            nodes_data = json.load(f)
            return nodes_data["nodes"]
            
    except Exception as e:
        print(f"Failed to load trusted nodes: {e}")
        sys.exit(1)

def wait_for_quorum(trust_core: TrustCore, timeout: int = 300) -> bool:
    """Wait for quorum approval with timeout"""
    start_time = time.time()
    print("\nWaiting for quorum approval...")
    
    while time.time() - start_time < timeout:
        if trust_core.state == TrustState.ACTIVE:
            return True
        elif trust_core.state == TrustState.FAILED:
            return False
            
        # Check every 5 seconds
        time.sleep(5)
        print(".", end="", flush=True)
        
    print("\nQuorum approval timeout!")
    return False

def initialize_system():
    """Initialize blockchain system with trust core"""
    try:
        print("Initializing blockchain system...")
        
        # Get base paths
        base_dir = Path(__file__).parent
        manifest_path = base_dir / "security" / "manifest.json"
        
        # Load genesis block
        genesis_block = load_genesis_block()
        
        # Load trusted nodes
        trusted_nodes = load_trusted_nodes()
        
        # Initialize trust core
        print("\nInitializing trust core...")
        trust_core = TrustCore()
        if not trust_core.initialize(trusted_nodes):
            print("FATAL: Failed to initialize trust core")
            sys.exit(1)
            
        # Wait for quorum approval
        if not wait_for_quorum(trust_core):
            print("FATAL: Failed to get quorum approval")
            sys.exit(1)
            
        # Enforce trust rules
        print("\nEnforcing trust rules...")
        if not trust_core.enforce_rules():
            print("FATAL: Trust rule enforcement failed")
            sys.exit(1)
            
        # Initialize integrity adapter
        print("\nInitializing integrity checks...")
        adapter = CriticalIntegrityAdapter()
        adapter.initialize(manifest_path, genesis_block)
        
        # Enforce integrity
        print("Enforcing system integrity...")
        if not adapter.enforce_integrity():
            print("FATAL: System integrity check failed")
            sys.exit(1)
            
        # Show integrity status
        status = adapter.get_integrity_status()
        print("\nLayer Integrity Status:")
        for layer, info in status.items():
            print(f"- {layer}: {info['state']}")
            
        print("\nSystem initialized successfully!")
        return True
        
    except Exception as e:
        print(f"FATAL: Failed to initialize system: {e}")
        sys.exit(1)

if __name__ == "__main__":
    initialize_system() 