import time
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from ..location.gps_manager import GPSPoint
from ..utils.validation import validate_gps_point

logger = logging.getLogger(__name__)

@dataclass
class DiagnosticResult:
    success: bool
    valid_points: int
    total_attempts: int
    average_accuracy: float
    error_message: Optional[str] = None

class GPSDiagnostics:
    def __init__(
        self,
        required_points: int = 10,
        max_retries: int = 5,
        accuracy_limit: float = 10.0,
        time_between_points: float = 5.0
    ):
        self.required_points = required_points
        self.max_retries = max_retries
        self.accuracy_limit = accuracy_limit
        self.time_between_points = time_between_points
        self.last_test_result: Optional[DiagnosticResult] = None
        
    async def run_test(self, gps_manager: 'GPSManager') -> DiagnosticResult:
        """Runs GPS diagnostic test"""
        logger.info("Starting GPS diagnostic test...")
        
        valid_points = []
        total_attempts = 0
        total_accuracy = 0
        
        while len(valid_points) < self.required_points and total_attempts < self.max_retries:
            try:
                # Get current position
                point = gps_manager.current_location
                if not point:
                    logger.warning("No GPS data available")
                    total_attempts += 1
                    await self._wait_for_next_try()
                    continue
                    
                # Validate point
                if not self._validate_point(point):
                    logger.warning(
                        f"Invalid GPS point: accuracy={point.accuracy}m"
                    )
                    total_attempts += 1
                    await self._wait_for_next_try()
                    continue
                    
                # Check if point is unique
                if self._is_duplicate_point(point, valid_points):
                    logger.warning("Duplicate GPS point detected")
                    total_attempts += 1
                    await self._wait_for_next_try()
                    continue
                    
                # Point is valid
                valid_points.append(point)
                total_accuracy += point.accuracy
                logger.info(
                    f"Valid point collected: {len(valid_points)}/{self.required_points}"
                )
                
                # Wait before next point
                await self._wait_for_next_try()
                
            except Exception as e:
                logger.error(f"Error during GPS test: {str(e)}")
                total_attempts += 1
                await self._wait_for_next_try()
                
        # Create result
        success = len(valid_points) >= self.required_points
        result = DiagnosticResult(
            success=success,
            valid_points=len(valid_points),
            total_attempts=total_attempts,
            average_accuracy=total_accuracy / len(valid_points) if valid_points else 0,
            error_message=None if success else self._get_error_message(
                len(valid_points),
                total_attempts
            )
        )
        
        self.last_test_result = result
        return result
        
    def _validate_point(self, point: GPSPoint) -> bool:
        """Validates a single GPS point"""
        if not validate_gps_point(point.to_dict()):
            return False
            
        # Check accuracy
        if point.accuracy > self.accuracy_limit:
            return False
            
        return True
        
    def _is_duplicate_point(
        self,
        point: GPSPoint,
        existing_points: List[GPSPoint]
    ) -> bool:
        """Checks if point is duplicate"""
        if not existing_points:
            return False
            
        last_point = existing_points[-1]
        
        # Check if coordinates are identical
        if (
            point.latitude == last_point.latitude and
            point.longitude == last_point.longitude
        ):
            return True
            
        # Check if timestamp is too close
        if (point.timestamp - last_point.timestamp) < 1.0:
            return True
            
        return False
        
    async def _wait_for_next_try(self):
        """Waits before next attempt"""
        await asyncio.sleep(self.time_between_points)
        
    def _get_error_message(self, valid_points: int, attempts: int) -> str:
        """Gets appropriate error message"""
        if valid_points == 0:
            return "Não foi possível obter pontos GPS válidos. Verifique se o dispositivo GPS está funcionando."
            
        if valid_points < self.required_points:
            return f"Precisão do GPS insuficiente. Obtidos {valid_points}/{self.required_points} pontos válidos."
            
        if attempts >= self.max_retries:
            return "Número máximo de tentativas excedido. Tente novamente em local com melhor sinal GPS."
            
        return "Erro desconhecido durante teste de GPS." 