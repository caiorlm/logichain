"""
Decentralized oracle system with data validation and aggregation.
Supports multiple data sources and consensus mechanisms.
"""

from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass
import time
import json
import hashlib
import logging
import threading
import statistics
from enum import Enum
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from decimal import Decimal
import asyncio
from cryptography.fernet import Fernet
from abc import ABC, abstractmethod
import aiohttp
from web3 import Web3
from eth_account.messages import encode_defunct

class DataSourceType(Enum):
    """Types of data sources"""
    REST_API = "rest_api"
    WEBSOCKET = "websocket"
    BLOCKCHAIN = "blockchain"
    CUSTOM = "custom"

class ValidationMethod(Enum):
    """Data validation methods"""
    MEDIAN = "median"
    WEIGHTED_MEDIAN = "weighted_median"
    BOUNDED_MEAN = "bounded_mean"
    CONSENSUS = "consensus"

@dataclass
class DataSource:
    """Data source configuration"""
    id: str
    type: DataSourceType
    endpoint: str
    method: str = "GET"
    headers: Dict[str, str] = None
    params: Dict[str, Any] = None
    timeout: int = 30
    weight: float = 1.0
    retry_count: int = 3
    retry_delay: int = 5

@dataclass
class OracleConfig:
    """Oracle configuration"""
    min_responses: int = 3
    validation_method: ValidationMethod = ValidationMethod.MEDIAN
    update_interval: int = 60
    deviation_threshold: float = 0.1
    stale_threshold: int = 300
    validation_threshold: float = 0.67

class OracleResponse:
    """Oracle data response"""
    
    def __init__(self, 
                 source_id: str,
                 value: Any,
                 timestamp: float,
                 signature: Optional[bytes] = None):
        self.source_id = source_id
        self.value = value
        self.timestamp = timestamp
        self.signature = signature
        self.validated = False
        self.weight = 1.0

class OracleRequest:
    """Oracle data request"""
    
    def __init__(self,
                 request_id: str,
                 data_type: str,
                 sources: List[DataSource],
                 callback: Optional[Callable] = None):
        self.id = request_id
        self.data_type = data_type
        self.sources = sources
        self.callback = callback
        self.responses: List[OracleResponse] = []
        self.result: Optional[Any] = None
        self.status = "pending"
        self.created_at = time.time()
        self.completed_at: Optional[float] = None

class OracleData:
    timestamp: int
    value: Union[Decimal, str, dict]
    source: str
    signature: str
    validator_signatures: List[str]

class OracleValidator(ABC):
    @abstractmethod
    async def validate_data(self, data: OracleData) -> bool:
        """Validate incoming oracle data"""
        pass

    @abstractmethod
    async def sign_data(self, data: OracleData) -> str:
        """Sign validated data"""
        pass

class PriceValidator(OracleValidator):
    def __init__(self, min_validators: int = 3, threshold: Decimal = Decimal('0.05')):
        self.min_validators = min_validators
        self.threshold = threshold
        self.recent_prices: Dict[str, List[Decimal]] = {}

    async def validate_data(self, data: OracleData) -> bool:
        if not isinstance(data.value, Decimal):
            return False
        
        if len(data.validator_signatures) < self.min_validators:
            return False

        token = data.source
        if token not in self.recent_prices:
            self.recent_prices[token] = []
        
        recent = self.recent_prices[token]
        if recent:
            avg_price = sum(recent) / len(recent)
            if abs(data.value - avg_price) / avg_price > self.threshold:
                return False
        
        self.recent_prices[token].append(data.value)
        if len(self.recent_prices[token]) > 10:
            self.recent_prices[token].pop(0)
        
        return True

    async def sign_data(self, data: OracleData) -> str:
        message = f"{data.timestamp}:{data.value}:{data.source}"
        private_key = self.get_validator_private_key()  # Implement secure key management
        signed_message = Web3().eth.account.sign_message(
            encode_defunct(text=message),
            private_key=private_key
        )
        return signed_message.signature.hex()

class OracleSystem:
    def __init__(self):
        self.validators: Dict[str, OracleValidator] = {}
        self.data_feeds: Dict[str, List[OracleData]] = {}
        self.encryption_key = Fernet.generate_key()
        self.fernet = Fernet(self.encryption_key)
        
    def register_validator(self, feed_type: str, validator: OracleValidator):
        """Register a new validator for a specific feed type"""
        if feed_type not in self.validators:
            self.validators[feed_type] = []
        self.validators[feed_type].append(validator)

    async def submit_data(self, feed_type: str, data: OracleData) -> bool:
        """Submit new data to the oracle system"""
        if feed_type not in self.validators:
            return False

        # Validate data through all registered validators
        valid_signatures = []
        for validator in self.validators[feed_type]:
            if await validator.validate_data(data):
                signature = await validator.sign_data(data)
                valid_signatures.append(signature)

        if len(valid_signatures) >= len(self.validators[feed_type]) // 2 + 1:
            data.validator_signatures = valid_signatures
            if feed_type not in self.data_feeds:
                self.data_feeds[feed_type] = []
            self.data_feeds[feed_type].append(data)
            return True
        return False

    def get_latest_data(self, feed_type: str) -> Optional[OracleData]:
        """Get the latest validated data for a feed type"""
        if feed_type not in self.data_feeds or not self.data_feeds[feed_type]:
            return None
        return self.data_feeds[feed_type][-1]

    async def fetch_external_price(self, token: str) -> Optional[Decimal]:
        """Fetch token price from external API"""
        async with aiohttp.ClientSession() as session:
            try:
                # Example using CoinGecko API
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={token}&vs_currencies=usd"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if token in data and "usd" in data[token]:
                            return Decimal(str(data[token]["usd"]))
            except Exception as e:
                print(f"Error fetching price for {token}: {e}")
            return None

    def encrypt_data(self, data: Any) -> bytes:
        """Encrypt sensitive data"""
        return self.fernet.encrypt(json.dumps(data).encode())

    def decrypt_data(self, encrypted_data: bytes) -> Any:
        """Decrypt sensitive data"""
        return json.loads(self.fernet.decrypt(encrypted_data).decode())

class OracleNode:
    def __init__(self, oracle_system: OracleSystem):
        self.oracle_system = oracle_system
        self.running = False
        self.update_interval = 60  # seconds

    async def start(self):
        """Start the oracle node"""
        self.running = True
        while self.running:
            try:
                # Fetch and submit price data
                for token in ["bitcoin", "ethereum", "cardano"]:  # Example tokens
                    price = await self.oracle_system.fetch_external_price(token)
                    if price is not None:
                        data = OracleData(
                            timestamp=int(time.time()),
                            value=price,
                            source=token,
                            signature="",  # Will be filled by validators
                            validator_signatures=[]
                        )
                        await self.oracle_system.submit_data("price", data)
                
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in oracle node: {e}")
                await asyncio.sleep(5)  # Short delay before retry

    def stop(self):
        """Stop the oracle node"""
        self.running = False

class Oracle:
    """Main oracle system"""
    
    def __init__(self, config: Optional[OracleConfig] = None):
        self.config = config or OracleConfig()
        
        # State
        self.requests: Dict[str, OracleRequest] = {}
        self.sources: Dict[str, DataSource] = {}
        self.latest_data: Dict[str, Dict[str, Any]] = {}
        
        # Crypto
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.public_key = self.private_key.public_key()
        
        # Threading
        self.running = False
        self.update_thread = None
        self.cleanup_thread = None
        
    def start(self):
        """Start oracle system"""
        if self.running:
            return
            
        self.running = True
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        logging.info("Oracle system started")
        
    def stop(self):
        """Stop oracle system"""
        self.running = False
        if self.update_thread:
            self.update_thread.join()
        if self.cleanup_thread:
            self.cleanup_thread.join()
        logging.info("Oracle system stopped")
        
    def add_data_source(self, source: DataSource):
        """Add new data source"""
        self.sources[source.id] = source
        
    def remove_data_source(self, source_id: str):
        """Remove data source"""
        if source_id in self.sources:
            del self.sources[source_id]
            
    def request_data(self,
                    data_type: str,
                    source_ids: Optional[List[str]] = None,
                    callback: Optional[Callable] = None) -> str:
        """
        Request data from oracle
        
        Args:
            data_type: Type of data requested
            source_ids: Optional list of specific sources to use
            callback: Optional callback for result
            
        Returns:
            str: Request ID
        """
        # Generate request ID
        request_id = hashlib.sha256(
            f"{data_type}-{time.time()}".encode()
        ).hexdigest()
        
        # Get sources
        if source_ids:
            sources = [
                source for source in self.sources.values()
                if source.id in source_ids
            ]
        else:
            sources = list(self.sources.values())
            
        if len(sources) < self.config.min_responses:
            raise ValueError(
                f"Not enough sources. Need {self.config.min_responses}, "
                f"have {len(sources)}"
            )
            
        # Create request
        request = OracleRequest(
            request_id=request_id,
            data_type=data_type,
            sources=sources,
            callback=callback
        )
        
        # Store request
        self.requests[request_id] = request
        
        return request_id
    
    def get_data(self, request_id: str) -> Optional[Any]:
        """Get result for request"""
        if request_id not in self.requests:
            return None
            
        request = self.requests[request_id]
        return request.result
    
    def _update_loop(self):
        """Main update loop"""
        while self.running:
            try:
                self._update_data()
                time.sleep(self.config.update_interval)
            except Exception as e:
                logging.error(f"Update loop error: {e}")
                
    def _cleanup_loop(self):
        """Cleanup old requests"""
        while self.running:
            try:
                now = time.time()
                
                # Remove old requests
                old_requests = [
                    request_id
                    for request_id, request in self.requests.items()
                    if request.status != "pending"
                    and now - request.created_at > self.config.stale_threshold
                ]
                
                for request_id in old_requests:
                    del self.requests[request_id]
                    
                time.sleep(60)
            except Exception as e:
                logging.error(f"Cleanup loop error: {e}")
                
    def _update_data(self):
        """Update data from sources"""
        for request in list(self.requests.values()):
            if request.status != "pending":
                continue
                
            # Collect responses
            for source in request.sources:
                try:
                    value = self._fetch_data(source, request.data_type)
                    if value is not None:
                        response = OracleResponse(
                            source_id=source.id,
                            value=value,
                            timestamp=time.time()
                        )
                        response.signature = self._sign_response(response)
                        response.weight = source.weight
                        request.responses.append(response)
                except Exception as e:
                    logging.error(f"Error fetching from {source.id}: {e}")
                    
            # Check if we have enough responses
            if len(request.responses) >= self.config.min_responses:
                self._validate_request(request)
                
    def _fetch_data(self, source: DataSource, data_type: str) -> Optional[Any]:
        """Fetch data from source"""
        if source.type == DataSourceType.REST_API:
            return self._fetch_rest_api(source, data_type)
        elif source.type == DataSourceType.WEBSOCKET:
            return self._fetch_websocket(source, data_type)
        elif source.type == DataSourceType.BLOCKCHAIN:
            return self._fetch_blockchain(source, data_type)
        elif source.type == DataSourceType.CUSTOM:
            return self._fetch_custom(source, data_type)
        else:
            raise ValueError(f"Unknown source type: {source.type}")
            
    def _fetch_rest_api(self, source: DataSource, data_type: str) -> Optional[Any]:
        """Fetch data from REST API"""
        for attempt in range(source.retry_count):
            try:
                response = requests.request(
                    method=source.method,
                    url=source.endpoint,
                    headers=source.headers,
                    params=source.params,
                    timeout=source.timeout
                )
                response.raise_for_status()
                
                data = response.json()
                return self._extract_value(data, data_type)
                
            except Exception as e:
                if attempt == source.retry_count - 1:
                    raise
                time.sleep(source.retry_delay)
                
    def _fetch_websocket(self, source: DataSource, data_type: str) -> Optional[Any]:
        """Fetch data from WebSocket"""
        # WebSocket implementation here
        pass
        
    def _fetch_blockchain(self, source: DataSource, data_type: str) -> Optional[Any]:
        """Fetch data from blockchain"""
        # Blockchain data fetching implementation here
        pass
        
    def _fetch_custom(self, source: DataSource, data_type: str) -> Optional[Any]:
        """Fetch data from custom source"""
        # Custom source implementation here
        pass
        
    def _extract_value(self, data: Any, data_type: str) -> Optional[Any]:
        """Extract value from response data"""
        if isinstance(data, dict):
            # Handle nested paths
            parts = data_type.split('.')
            value = data
            for part in parts:
                if part not in value:
                    return None
                value = value[part]
            return value
        return data
        
    def _validate_request(self, request: OracleRequest):
        """Validate responses and compute result"""
        values = [
            (response.value, response.weight)
            for response in request.responses
        ]
        
        if self.config.validation_method == ValidationMethod.MEDIAN:
            result = statistics.median(v[0] for v in values)
        elif self.config.validation_method == ValidationMethod.WEIGHTED_MEDIAN:
            # Weighted median implementation
            sorted_values = sorted(values, key=lambda x: x[0])
            total_weight = sum(v[1] for v in values)
            cumulative_weight = 0
            for value, weight in sorted_values:
                cumulative_weight += weight
                if cumulative_weight >= total_weight / 2:
                    result = value
                    break
        elif self.config.validation_method == ValidationMethod.BOUNDED_MEAN:
            # Remove outliers
            mean = statistics.mean(v[0] for v in values)
            std = statistics.stdev(v[0] for v in values)
            filtered = [
                v[0] for v in values
                if abs(v[0] - mean) <= 2 * std
            ]
            result = statistics.mean(filtered)
        else:  # ValidationMethod.CONSENSUS
            # Check if enough responses agree within deviation threshold
            for value, _ in values:
                matching = sum(
                    1 for v in values
                    if abs(v[0] - value) / value <= self.config.deviation_threshold
                )
                if matching / len(values) >= self.config.validation_threshold:
                    result = value
                    break
            else:
                raise ValueError("No consensus reached")
                
        # Update request
        request.result = result
        request.status = "completed"
        request.completed_at = time.time()
        
        # Call callback if provided
        if request.callback:
            try:
                request.callback(result)
            except Exception as e:
                logging.error(f"Callback error: {e}")
                
    def _sign_response(self, response: OracleResponse) -> bytes:
        """Sign oracle response"""
        data = json.dumps({
            'source_id': response.source_id,
            'value': response.value,
            'timestamp': response.timestamp
        }).encode()
        
        signature = self.private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature
        
    def verify_response(self, response: OracleResponse) -> bool:
        """Verify response signature"""
        if not response.signature:
            return False
            
        try:
            data = json.dumps({
                'source_id': response.source_id,
                'value': response.value,
                'timestamp': response.timestamp
            }).encode()
            
            self.public_key.verify(
                response.signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False 