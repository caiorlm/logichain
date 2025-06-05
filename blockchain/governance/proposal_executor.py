"""
LogiChain Proposal Executor
Enforces immutable tokenomics parameters in governance
"""

from typing import Dict, Any, Optional
from ..config import GOVERNANCE, validate_governance_param

class ProposalExecutor:
    """Executes and validates governance proposals"""
    
    def __init__(self):
        self.allowed_types = GOVERNANCE["ALLOWED_PROPOSAL_TYPES"]
        
    def validate_proposal(
        self,
        proposal_type: str,
        changes: Dict[str, Any]
    ) -> bool:
        """Validate if proposal can be executed"""
        # Check proposal type
        if proposal_type not in self.allowed_types:
            raise ValueError(f"Invalid proposal type: {proposal_type}")
            
        # Check for immutable parameters
        for param in changes.keys():
            if not validate_governance_param(param):
                raise ValueError(
                    f"Parameter '{param}' cannot be modified via governance"
                )
                
        return True
        
    def execute_proposal(
        self,
        proposal_type: str,
        changes: Dict[str, Any],
        config: Any
    ) -> bool:
        """Execute approved proposal"""
        try:
            # Validate first
            self.validate_proposal(proposal_type, changes)
            
            # Apply changes based on proposal type
            if proposal_type == "protocol_upgrade":
                return self._execute_protocol_upgrade(changes, config)
                
            elif proposal_type == "parameter_change":
                return self._execute_parameter_change(changes, config)
                
            elif proposal_type == "feature_activation":
                return self._execute_feature_activation(changes, config)
                
            return False
            
        except Exception as e:
            raise Exception(f"Failed to execute proposal: {str(e)}")
            
    def _execute_protocol_upgrade(
        self,
        changes: Dict[str, Any],
        config: Any
    ) -> bool:
        """Execute protocol upgrade proposal"""
        try:
            # Protocol upgrades should be implemented by specific handlers
            upgrade_handler = changes.get("upgrade_handler")
            if not upgrade_handler:
                raise ValueError("No upgrade handler specified")
                
            # Execute upgrade
            success = upgrade_handler(config)
            
            return success
        except Exception as e:
            raise Exception(f"Protocol upgrade failed: {str(e)}")
            
    def _execute_parameter_change(
        self,
        changes: Dict[str, Any],
        config: Any
    ) -> bool:
        """Execute parameter change proposal"""
        try:
            # Apply each parameter change
            for param, value in changes.items():
                if hasattr(config, param):
                    setattr(config, param, value)
                else:
                    raise ValueError(f"Invalid parameter: {param}")
                    
            return True
        except Exception as e:
            raise Exception(f"Parameter change failed: {str(e)}")
            
    def _execute_feature_activation(
        self,
        changes: Dict[str, Any],
        config: Any
    ) -> bool:
        """Execute feature activation proposal"""
        try:
            # Feature activation should be implemented by specific handlers
            feature_handler = changes.get("feature_handler")
            if not feature_handler:
                raise ValueError("No feature handler specified")
                
            # Execute feature activation
            success = feature_handler(config)
            
            return success
        except Exception as e:
            raise Exception(f"Feature activation failed: {str(e)}")
            
    def get_execution_plan(
        self,
        proposal_type: str,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get execution plan for proposal"""
        # Validate first
        self.validate_proposal(proposal_type, changes)
        
        return {
            "type": proposal_type,
            "changes": changes,
            "immutable_params": GOVERNANCE["IMMUTABLE_PARAMS"],
            "allowed_types": self.allowed_types
        } 