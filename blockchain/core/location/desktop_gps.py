import time
import serial
import pynmea2
from typing import Optional, Dict
import threading
from datetime import datetime

from .gps_manager import GPSManager, GPSPoint

class USBGPSManager(GPSManager):
    def __init__(self, node_id: str, port: str = "/dev/ttyUSB0", baud: int = 9600):
        super().__init__(node_id)
        self.port = port
        self.baud = baud
        self._last_data = None
        self._setup_serial()
        
    def _setup_serial(self):
        """Sets up serial connection to GPS device"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=1.0
            )
        except serial.SerialException as e:
            raise RuntimeError(f"Failed to connect to GPS device: {str(e)}")
            
        # Start reading thread
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._read_serial,
            daemon=True
        )
        self._reader_thread.start()
        
    def _read_serial(self):
        """Continuously reads from serial port"""
        while self._reader_running:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('ascii', errors='ignore')
                    if line.startswith('$'):
                        try:
                            msg = pynmea2.parse(line)
                            if isinstance(msg, pynmea2.GGA):
                                self._last_data = {
                                    'latitude': msg.latitude,
                                    'longitude': msg.longitude,
                                    'timestamp': time.time(),
                                    'accuracy': float(msg.horizontal_dil) if msg.horizontal_dil else 10.0,
                                    'altitude': float(msg.altitude) if msg.altitude else None
                                }
                            elif isinstance(msg, pynmea2.VTG):
                                if self._last_data:
                                    self._last_data.update({
                                        'speed': float(msg.spd_over_grnd_kmph) if msg.spd_over_grnd_kmph else None,
                                        'heading': float(msg.true_track) if msg.true_track else None
                                    })
                        except pynmea2.ParseError:
                            continue
            except Exception as e:
                print(f"Error reading GPS: {str(e)}")
                time.sleep(1)
                
    def _collect_gps_data(self) -> Optional[GPSPoint]:
        """Collects GPS data from USB device"""
        if not self._last_data:
            return None
            
        data = self._last_data
        return GPSPoint(
            latitude=data['latitude'],
            longitude=data['longitude'],
            timestamp=data['timestamp'],
            accuracy=data['accuracy'],
            speed=data.get('speed'),
            heading=data.get('heading')
        )
        
    def stop_collection(self):
        """Stops GPS collection and closes serial port"""
        super().stop_collection()
        
        self._reader_running = False
        if hasattr(self, '_reader_thread'):
            self._reader_thread.join(timeout=5.0)
            
        if hasattr(self, 'serial'):
            self.serial.close()
            
class GPSDManager(GPSManager):
    """Alternative implementation using gpsd daemon"""
    def __init__(self, node_id: str, host: str = 'localhost', port: int = 2947):
        super().__init__(node_id)
        self.host = host
        self.port = port
        self._setup_gpsd()
        
    def _setup_gpsd(self):
        """Sets up connection to gpsd daemon"""
        try:
            import gps
            self.session = gps.gps(
                host=self.host,
                port=self.port,
                mode=gps.WATCH_ENABLE
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to gpsd: {str(e)}")
            
    def _collect_gps_data(self) -> Optional[GPSPoint]:
        """Collects GPS data from gpsd"""
        try:
            report = self.session.next()
            if report['class'] != 'TPV':
                return None
                
            return GPSPoint(
                latitude=report.lat,
                longitude=report.lon,
                timestamp=time.time(),
                accuracy=report.epx if hasattr(report, 'epx') else 10.0,
                speed=report.speed if hasattr(report, 'speed') else None,
                heading=report.track if hasattr(report, 'track') else None
            )
        except Exception as e:
            print(f"Error reading gpsd: {str(e)}")
            return None
            
    def stop_collection(self):
        """Stops GPS collection and closes gpsd connection"""
        super().stop_collection()
        if hasattr(self, 'session'):
            self.session.close() 