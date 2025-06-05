import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional

def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    node_id: Optional[str] = None
) -> None:
    """Configura sistema de logging
    
    Args:
        log_dir: Diretório para arquivos de log
        log_level: Nível de logging
        node_id: ID do nó para identificação nos logs
    """
    # Cria diretório de logs se não existir
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Nome base do arquivo de log
    base_filename = datetime.now().strftime("%Y%m%d")
    if node_id:
        base_filename = f"{base_filename}_{node_id}"
        
    # Configura handlers
    handlers = []
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)
    
    # Handler para arquivo geral
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f"{base_filename}.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    handlers.append(file_handler)
    
    # Handler para erros
    error_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f"{base_filename}_error.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s\n'
        'Exception:\n%(exc_info)s'
    )
    error_handler.setFormatter(error_formatter)
    handlers.append(error_handler)
    
    # Handler para métricas
    metrics_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f"{base_filename}_metrics.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    metrics_handler.setLevel(logging.INFO)
    metrics_formatter = logging.Formatter(
        '%(asctime)s - %(message)s'
    )
    metrics_handler.setFormatter(metrics_formatter)
    handlers.append(metrics_handler)
    
    # Configura logging raiz
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )
    
    # Configura loggers específicos
    loggers = {
        'network': logging.getLogger('blockchain.network'),
        'dag': logging.getLogger('blockchain.dag'),
        'sync': logging.getLogger('blockchain.sync'),
        'metrics': logging.getLogger('blockchain.metrics')
    }
    
    for name, logger in loggers.items():
        logger.setLevel(log_level)
        for handler in handlers:
            logger.addHandler(handler)
            
    # Log inicial
    logging.info(f"Logging initialized for node {node_id}")
    logging.info(f"Log directory: {os.path.abspath(log_dir)}")
    logging.info(f"Log level: {logging.getLevelName(log_level)}")
    
def get_logger(name: str) -> logging.Logger:
    """Retorna logger configurado
    
    Args:
        name: Nome do logger
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(f"blockchain.{name}")
    
class LoggerAdapter(logging.LoggerAdapter):
    """Adapter para adicionar contexto aos logs"""
    
    def process(self, msg, kwargs):
        """Processa mensagem de log
        
        Args:
            msg: Mensagem original
            kwargs: Argumentos adicionais
            
        Returns:
            Tupla (mensagem processada, kwargs)
        """
        # Adiciona informações de contexto
        context = {
            'node_id': self.extra.get('node_id'),
            'component': self.extra.get('component'),
            'peer_id': self.extra.get('peer_id')
        }
        
        context_str = ' '.join(f'[{k}={v}]' for k, v in context.items() if v)
        
        if context_str:
            msg = f"{context_str} {msg}"
            
        return msg, kwargs
        
def get_component_logger(
    component: str,
    node_id: Optional[str] = None,
    peer_id: Optional[str] = None
) -> LoggerAdapter:
    """Retorna logger adaptado para componente
    
    Args:
        component: Nome do componente
        node_id: ID do nó
        peer_id: ID do peer
        
    Returns:
        Logger adaptado com contexto
    """
    logger = get_logger(component)
    
    extra = {
        'component': component,
        'node_id': node_id,
        'peer_id': peer_id
    }
    
    return LoggerAdapter(logger, extra) 