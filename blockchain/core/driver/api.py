from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import time

from .adapter import DriverNodeAdapter

class TimestampRange(BaseModel):
    start_time: float
    end_time: float

class GPSSubmission(BaseModel):
    route_id: str
    points: List[Dict]

class ContractAcceptance(BaseModel):
    contract_id: str

app = FastAPI(title="LogiChain Driver Node API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global adapter instance
driver_adapter: Optional[DriverNodeAdapter] = None

def init_api(adapter: DriverNodeAdapter):
    """Initializes API with adapter instance"""
    global driver_adapter
    driver_adapter = adapter

@app.get("/gps/verify")
async def verify_gps():
    """Verifies GPS device and unlocks contract functionality"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    success, message = await driver_adapter.verify_gps_device()
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
        
    return {
        "status": "success",
        "message": message
    }

@app.get("/gps/last")
async def get_last_point():
    """Gets last recorded GPS point"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    if not driver_adapter.gps_manager.current_location:
        raise HTTPException(status_code=404, detail="No GPS data available")
        
    return {
        "point": driver_adapter.gps_manager.current_location.to_dict(),
        "route_id": driver_adapter.current_route_id,
        "timestamp": time.time()
    }

@app.post("/gps/proof")
async def generate_proof(time_range: TimestampRange):
    """Generates cryptographic proof for route segment"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    if not driver_adapter.contracts_unlocked:
        raise HTTPException(
            status_code=403,
            detail="GPS não verificado. Execute /gps/verify primeiro."
        )
        
    if not driver_adapter.current_route_id:
        raise HTTPException(status_code=400, detail="No active route")
        
    return driver_adapter.get_route_proof(
        time_range.start_time,
        time_range.end_time
    )

@app.post("/gps/submit")
async def submit_points(submission: GPSSubmission):
    """Submits GPS points to blockchain"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    if not driver_adapter.contracts_unlocked:
        raise HTTPException(
            status_code=403,
            detail="GPS não verificado. Execute /gps/verify primeiro."
        )
        
    # Start route if not already started
    if not driver_adapter.current_route_id:
        await driver_adapter.start_route(submission.route_id)
        
    # Process each point
    for point_data in submission.points:
        try:
            point = driver_adapter.gps_manager.GPSPoint(**point_data)
            await driver_adapter.process_gps_point(point)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid point data: {str(e)}"
            )
            
    return {"status": "success", "points_processed": len(submission.points)}

@app.get("/contracts")
async def get_contracts():
    """Gets available delivery contracts"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    if not driver_adapter.contracts_unlocked:
        raise HTTPException(
            status_code=403,
            detail="GPS não verificado. Execute /gps/verify primeiro."
        )
        
    try:
        contracts = await driver_adapter.get_available_contracts()
        return {"contracts": contracts}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get contracts: {str(e)}"
        )

@app.post("/contracts/accept")
async def accept_contract(acceptance: ContractAcceptance):
    """Accepts a delivery contract"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    if not driver_adapter.contracts_unlocked:
        raise HTTPException(
            status_code=403,
            detail="GPS não verificado. Execute /gps/verify primeiro."
        )
        
    try:
        success = await driver_adapter.accept_contract(acceptance.contract_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to accept contract"
            )
            
        return {"status": "success", "contract_id": acceptance.contract_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error accepting contract: {str(e)}"
        )

@app.get("/status")
async def get_status():
    """Gets adapter status"""
    if not driver_adapter:
        raise HTTPException(status_code=500, detail="Adapter not initialized")
        
    return {
        "gps_verified": driver_adapter.contracts_unlocked,
        "route_id": driver_adapter.current_route_id,
        "pending_points": len(driver_adapter.pending_points),
        "gps_active": driver_adapter.gps_manager._running,
        "merkle_root": driver_adapter.merkle_tree.get_merkle_root(),
        "wallet_address": driver_adapter.wallet.address,
        "last_gps_test": driver_adapter.gps_diagnostics.last_test_result.__dict__ if driver_adapter.gps_diagnostics.last_test_result else None
    } 