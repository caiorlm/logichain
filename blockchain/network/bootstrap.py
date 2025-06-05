"""
LogiChain Bootstrap System
Manages P2P node discovery using seed nodes
"""

import os
import json
import random
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass
class SeedNode:
    """Seed node information"""
    address: str  # IP or domain
    port: int
    region: str
    type: str  # "validator" or "full_node"
    version: str
    
    @property
    def endpoint(self) -> str:
        """Get node endpoint"""
        return f"{self.address}:{self.port}"

class BootstrapManager:
    """Manages P2P node discovery"""
    
    # Default bootstrap sources
    DEFAULT_SOURCES = [
        "https://raw.githubusercontent.com/logichain/network/main/bootstrap.json",
        "https://logichain.network/bootstrap.json",
        "https://cdn.logichain.network/bootstrap.json"
    ]
    
    # Local cache file
    CACHE_FILE = "bootstrap_cache.json"
    
    # Cache expiry in seconds (1 hour)
    CACHE_EXPIRY = 3600
    
    def __init__(
        self,
        sources: Optional[List[str]] = None,
        cache_dir: str = ".logichain"
    ):
        self.sources = sources or self.DEFAULT_SOURCES
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
        
    def get_seed_nodes(
        self,
        count: int = 5,
        region: Optional[str] = None,
        node_type: Optional[str] = None
    ) -> List[SeedNode]:
        """Get list of seed nodes"""
        # Try to load from cache first
        nodes = self._load_cache()
        
        # Fetch from sources if cache empty/expired
        if not nodes:
            nodes = self._fetch_nodes()
            self._save_cache(nodes)
            
        # Filter nodes
        filtered = self._filter_nodes(nodes, region, node_type)
        
        # Return random selection
        return random.sample(
            filtered,
            min(count, len(filtered))
        )
        
    def add_seed_node(
        self,
        node: SeedNode,
        source: Optional[str] = None
    ):
        """Add new seed node"""
        # Load existing nodes
        nodes = self._load_cache() or []
        
        # Add new node
        nodes.append(node)
        
        # Save updated cache
        self._save_cache(nodes)
        
        # Update source if provided
        if source:
            self._update_source(source, nodes)
            
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_path(self) -> str:
        """Get cache file path"""
        return os.path.join(self.cache_dir, self.CACHE_FILE)
        
    def _load_cache(self) -> Optional[List[SeedNode]]:
        """Load nodes from cache"""
        try:
            cache_path = self._get_cache_path()
            
            # Check if cache exists and is fresh
            if not os.path.exists(cache_path):
                return None
                
            # Check cache age
            age = time.time() - os.path.getmtime(cache_path)
            if age > self.CACHE_EXPIRY:
                return None
                
            # Load cache
            with open(cache_path, "r") as f:
                data = json.load(f)
                
            # Parse nodes
            return [
                SeedNode(**node)
                for node in data["nodes"]
            ]
            
        except Exception:
            return None
            
    def _save_cache(self, nodes: List[SeedNode]):
        """Save nodes to cache"""
        cache_path = self._get_cache_path()
        
        # Convert to dict
        data = {
            "timestamp": time.time(),
            "nodes": [
                {
                    "address": node.address,
                    "port": node.port,
                    "region": node.region,
                    "type": node.type,
                    "version": node.version
                }
                for node in nodes
            ]
        }
        
        # Save to file
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
            
    def _fetch_nodes(self) -> List[SeedNode]:
        """Fetch nodes from sources"""
        nodes = []
        
        for source in self.sources:
            try:
                # Fetch data
                response = requests.get(
                    source,
                    timeout=5,
                    verify=True  # Verify HTTPS
                )
                response.raise_for_status()
                
                # Parse nodes
                data = response.json()
                source_nodes = [
                    SeedNode(**node)
                    for node in data["nodes"]
                ]
                
                nodes.extend(source_nodes)
                
            except Exception as e:
                print(f"Failed to fetch from {source}: {str(e)}")
                continue
                
        return nodes
        
    def _filter_nodes(
        self,
        nodes: List[SeedNode],
        region: Optional[str],
        node_type: Optional[str]
    ) -> List[SeedNode]:
        """Filter nodes by criteria"""
        filtered = nodes
        
        # Filter by region
        if region:
            filtered = [
                node for node in filtered
                if node.region == region
            ]
            
        # Filter by type
        if node_type:
            filtered = [
                node for node in filtered
                if node.type == node_type
            ]
            
        return filtered
        
    def _update_source(
        self,
        source: str,
        nodes: List[SeedNode]
    ):
        """Update nodes in source"""
        try:
            # Parse URL
            url = urlparse(source)
            
            # Only support file:// URLs for updates
            if url.scheme != "file":
                return
                
            # Convert to dict
            data = {
                "timestamp": time.time(),
                "nodes": [
                    {
                        "address": node.address,
                        "port": node.port,
                        "region": node.region,
                        "type": node.type,
                        "version": node.version
                    }
                    for node in nodes
                ]
            }
            
            # Save to file
            with open(url.path, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Failed to update source {source}: {str(e)}")
            
    def verify_node(self, node: SeedNode) -> bool:
        """Verify node is accessible"""
        try:
            # Try to connect
            response = requests.get(
                f"http://{node.endpoint}/status",
                timeout=5
            )
            response.raise_for_status()
            
            # Verify version
            data = response.json()
            return data["version"] == node.version
            
        except Exception:
            return False 