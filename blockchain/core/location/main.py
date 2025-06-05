import argparse
import sys
import signal
import logging
from typing import Optional

from .gps_manager import GPSManager
from .desktop_gps import USBGPSManager, GPSDManager
from .mobile_gps import MobileGPSManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_gps_manager(args) -> Optional[GPSManager]:
    """Creates appropriate GPS manager based on platform and arguments"""
    try:
        # Try mobile first
        try:
            from android.content import Context
            context = Context()
            logger.info("Using Android GPS manager")
            return MobileGPSManager(args.node_id, context)
        except ImportError:
            pass
            
        # Try USB GPS
        if args.gps_device:
            try:
                logger.info(f"Using USB GPS manager with device {args.gps_device}")
                return USBGPSManager(
                    args.node_id,
                    port=args.gps_device,
                    baud=args.gps_baud
                )
            except Exception as e:
                logger.warning(f"Failed to initialize USB GPS: {str(e)}")
                
        # Fall back to gpsd
        logger.info(f"Using GPSD manager at {args.gpsd_host}:{args.gpsd_port}")
        return GPSDManager(
            args.node_id,
            host=args.gpsd_host,
            port=args.gpsd_port
        )
    except Exception as e:
        logger.error(f"Failed to initialize any GPS manager: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description="LogiChain GPS Tracking")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--gps-device", help="Path to GPS device")
    parser.add_argument("--gps-baud", type=int, default=9600, help="GPS baud rate")
    parser.add_argument("--gpsd-host", default="localhost", help="GPSD host")
    parser.add_argument("--gpsd-port", type=int, default=2947, help="GPSD port")
    parser.add_argument("--db-path", default="gps_cache.db", help="Path to SQLite database")
    
    args = parser.parse_args()
    
    # Initialize GPS manager
    gps_manager = get_gps_manager(args)
    if not gps_manager:
        logger.error("Failed to initialize GPS manager")
        sys.exit(1)
        
    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        logger.info("Shutting down GPS manager...")
        gps_manager.stop_collection()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start GPS collection
    try:
        logger.info("Starting GPS collection...")
        gps_manager.start_collection()
        
        # Keep main thread alive
        signal.pause()
    except Exception as e:
        logger.error(f"Error during GPS collection: {str(e)}")
        gps_manager.stop_collection()
        sys.exit(1)

if __name__ == "__main__":
    main() 