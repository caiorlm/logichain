"""
LogiChain Mesh Logger
Handles logging for mesh network operations
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

class MeshLogger:
    """Mesh network logger"""
    
    def __init__(
        self,
        log_dir: str = "logs",
        log_file: str = "mesh_activity.log",
        max_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / log_file
        self.max_size = max_size
        self.backup_count = backup_count
        
        # Event handlers
        self.event_handlers: List[Callable] = []
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        self._configure_logging()
        
        # Get logger
        self.logger = logging.getLogger("mesh")
        
    def _configure_logging(self):
        """Configure logging handlers"""
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # File handler
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=self.max_size,
            backupCount=self.backup_count
        )
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure logger
        logger = logging.getLogger("mesh")
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    def register_handler(self, handler: Callable):
        """Register event handler"""
        if handler not in self.event_handlers:
            self.event_handlers.append(handler)
            
    def unregister_handler(self, handler: Callable):
        """Unregister event handler"""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
            
    def _notify_handlers(self, event: Dict):
        """Notify event handlers"""
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Event handler error: {str(e)}")
                
    def log_node_event(
        self,
        node_id: str,
        event_type: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log node event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "node_id": node_id,
            "type": "node_event",
            "event_type": event_type,
            "status": status
        }
        
        if details:
            event["details"] = details
            
        self.logger.info(f"Node event: {json.dumps(event)}")
        self._notify_handlers(event)
        
    def log_sync_event(
        self,
        node_id: str,
        sync_type: str,
        height: int,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log sync event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "node_id": node_id,
            "type": "sync_event",
            "sync_type": sync_type,
            "height": height,
            "status": status
        }
        
        if details:
            event["details"] = details
            
        self.logger.info(f"Sync event: {json.dumps(event)}")
        self._notify_handlers(event)
        
    def log_contract_event(
        self,
        contract_id: str,
        event_type: str,
        status: str,
        node_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log contract event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "contract_id": contract_id,
            "type": "contract_event",
            "event_type": event_type,
            "status": status
        }
        
        if node_id:
            event["node_id"] = node_id
            
        if details:
            event["details"] = details
            
        self.logger.info(f"Contract event: {json.dumps(event)}")
        self._notify_handlers(event)
        
    def log_validation_event(
        self,
        contract_id: str,
        validator_id: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log validation event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "contract_id": contract_id,
            "validator_id": validator_id,
            "type": "validation_event",
            "status": status
        }
        
        if details:
            event["details"] = details
            
        self.logger.info(f"Validation event: {json.dumps(event)}")
        self._notify_handlers(event)
        
    def log_error(
        self,
        error_type: str,
        message: str,
        node_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log error event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "error_event",
            "error_type": error_type,
            "message": message
        }
        
        if node_id:
            event["node_id"] = node_id
            
        if details:
            event["details"] = details
            
        self.logger.error(f"Error event: {json.dumps(event)}")
        self._notify_handlers(event)
        
    def get_recent_events(
        self,
        event_type: Optional[str] = None,
        node_id: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """Get recent events from log"""
        events = []
        
        try:
            with open(self.log_file, "r") as f:
                for line in reversed(list(f)):
                    # Parse event
                    try:
                        event_str = line.split("event: ")[1]
                        event = json.loads(event_str)
                        
                        # Apply filters
                        if event_type and event.get("type") != event_type:
                            continue
                            
                        if node_id and event.get("node_id") != node_id:
                            continue
                            
                        events.append(event)
                        
                        if len(events) >= limit:
                            break
                            
                    except Exception:
                        continue
                        
        except Exception as e:
            self.logger.error(f"Failed to get recent events: {str(e)}")
            
        return events
        
    def clear_logs(self):
        """Clear all logs"""
        try:
            # Remove main log
            if self.log_file.exists():
                self.log_file.unlink()
                
            # Remove backups
            for i in range(self.backup_count):
                backup = self.log_file.with_suffix(f".log.{i+1}")
                if backup.exists():
                    backup.unlink()
                    
            # Reconfigure logging
            self._configure_logging()
            
            self.logger.info("Logs cleared")
            
        except Exception as e:
            self.logger.error(f"Failed to clear logs: {str(e)}")
            
    def archive_logs(self, archive_dir: Optional[str] = None):
        """Archive current logs"""
        try:
            # Use timestamp for archive name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create archive directory
            if archive_dir:
                archive_path = Path(archive_dir)
            else:
                archive_path = self.log_dir / "archives"
                
            archive_path.mkdir(parents=True, exist_ok=True)
            
            # Archive main log
            if self.log_file.exists():
                archive_file = archive_path / f"mesh_activity_{timestamp}.log"
                self.log_file.rename(archive_file)
                
            # Archive backups
            for i in range(self.backup_count):
                backup = self.log_file.with_suffix(f".log.{i+1}")
                if backup.exists():
                    archive_backup = archive_path / f"mesh_activity_{timestamp}.log.{i+1}"
                    backup.rename(archive_backup)
                    
            # Reconfigure logging
            self._configure_logging()
            
            self.logger.info(f"Logs archived to {archive_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to archive logs: {str(e)}") 