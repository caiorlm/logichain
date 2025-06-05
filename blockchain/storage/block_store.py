import os
import json
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime

from ..core.block import Block
from ..core.transaction import Transaction

@dataclass
class BlockMetadata:
    """Metadados de um bloco."""
    height: int
    timestamp: datetime
    transactions: int
    size: int
    
class BlockStore:
    """
    Implementação simplificada de armazenamento de blocos.
    Armazena blocos em arquivos individuais.
    Sem pruning, sem índices complexos.
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.blocks_dir = os.path.join(data_dir, "blocks")
        self.metadata: Dict[str, BlockMetadata] = {}
        
        # Cria diretórios
        os.makedirs(self.blocks_dir, exist_ok=True)
        
        # Carrega metadados
        self._load_metadata()
        
    def _load_metadata(self):
        """Carrega metadados dos blocos."""
        metadata_file = os.path.join(self.data_dir, "metadata.json")
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                    
                for block_hash, meta in data.items():
                    self.metadata[block_hash] = BlockMetadata(
                        height=meta["height"],
                        timestamp=datetime.fromisoformat(meta["timestamp"]),
                        transactions=meta["transactions"],
                        size=meta["size"]
                    )
                    
                logging.info(f"Loaded metadata for {len(self.metadata)} blocks")
                
            except Exception as e:
                logging.error(f"Failed to load metadata: {e}")
                
    def _save_metadata(self):
        """Salva metadados dos blocos."""
        metadata_file = os.path.join(self.data_dir, "metadata.json")
        
        try:
            data = {}
            for block_hash, meta in self.metadata.items():
                data[block_hash] = {
                    "height": meta.height,
                    "timestamp": meta.timestamp.isoformat(),
                    "transactions": meta.transactions,
                    "size": meta.size
                }
                
            with open(metadata_file, "w") as f:
                json.dump(data, f, indent=2)
                
            logging.info("Saved block metadata")
            
        except Exception as e:
            logging.error(f"Failed to save metadata: {e}")
            
    def store_block(self, block: Block, height: int) -> bool:
        """
        Armazena um bloco.
        
        Args:
            block: Bloco a ser armazenado
            height: Altura do bloco
            
        Returns:
            bool: True se bloco foi armazenado com sucesso
        """
        block_hash = block.get_hash()
        block_file = os.path.join(self.blocks_dir, f"{block_hash}.json")
        
        try:
            # Salva bloco
            block_data = {
                "header": {
                    "version": block.version,
                    "prev_block": block.prev_block,
                    "merkle_root": block.merkle_root,
                    "timestamp": block.timestamp.isoformat(),
                    "bits": block.bits,
                    "nonce": block.nonce
                },
                "transactions": [tx.to_dict() for tx in block.transactions]
            }
            
            with open(block_file, "w") as f:
                json.dump(block_data, f, indent=2)
                
            # Atualiza metadados
            self.metadata[block_hash] = BlockMetadata(
                height=height,
                timestamp=block.timestamp,
                transactions=len(block.transactions),
                size=os.path.getsize(block_file)
            )
            
            self._save_metadata()
            
            logging.info(f"Stored block {block_hash}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to store block {block_hash}: {e}")
            return False
            
    def get_block(self, block_hash: str) -> Optional[Block]:
        """
        Retorna um bloco.
        
        Args:
            block_hash: Hash do bloco
            
        Returns:
            Block: Bloco ou None se não encontrado
        """
        block_file = os.path.join(self.blocks_dir, f"{block_hash}.json")
        
        if not os.path.exists(block_file):
            return None
            
        try:
            with open(block_file, "r") as f:
                data = json.load(f)
                
            # Reconstrói bloco
            header = data["header"]
            transactions = [
                Transaction.from_dict(tx) for tx in data["transactions"]
            ]
            
            block = Block(
                version=header["version"],
                prev_block=header["prev_block"],
                merkle_root=header["merkle_root"],
                timestamp=datetime.fromisoformat(header["timestamp"]),
                bits=header["bits"],
                nonce=header["nonce"],
                transactions=transactions
            )
            
            return block
            
        except Exception as e:
            logging.error(f"Failed to load block {block_hash}: {e}")
            return None
            
    def get_block_metadata(self, block_hash: str) -> Optional[BlockMetadata]:
        """
        Retorna metadados de um bloco.
        
        Args:
            block_hash: Hash do bloco
            
        Returns:
            BlockMetadata: Metadados ou None se não encontrado
        """
        return self.metadata.get(block_hash)
        
    def get_blocks_by_height(self, start: int, end: int) -> List[Block]:
        """
        Retorna blocos por altura.
        
        Args:
            start: Altura inicial
            end: Altura final
            
        Returns:
            List[Block]: Lista de blocos
        """
        blocks = []
        
        for block_hash, meta in self.metadata.items():
            if start <= meta.height <= end:
                block = self.get_block(block_hash)
                if block:
                    blocks.append(block)
                    
        return sorted(blocks, key=lambda b: self.metadata[b.get_hash()].height)
        
    def get_latest_block(self) -> Optional[Block]:
        """
        Retorna o bloco mais recente.
        
        Returns:
            Block: Bloco mais recente ou None se não houver blocos
        """
        if not self.metadata:
            return None
            
        # Encontra bloco com maior altura
        latest_hash = max(
            self.metadata.items(),
            key=lambda x: x[1].height
        )[0]
        
        return self.get_block(latest_hash)
        
    def delete_block(self, block_hash: str) -> bool:
        """
        Remove um bloco.
        
        Args:
            block_hash: Hash do bloco
            
        Returns:
            bool: True se bloco foi removido com sucesso
        """
        block_file = os.path.join(self.blocks_dir, f"{block_hash}.json")
        
        try:
            if os.path.exists(block_file):
                os.remove(block_file)
                
            if block_hash in self.metadata:
                del self.metadata[block_hash]
                self._save_metadata()
                
            logging.info(f"Deleted block {block_hash}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to delete block {block_hash}: {e}")
            return False
            
    @property
    def block_count(self) -> int:
        """Retorna número de blocos."""
        return len(self.metadata)
        
    @property
    def total_size(self) -> int:
        """Retorna tamanho total em bytes."""
        return sum(meta.size for meta in self.metadata.values()) 