import time
from typing import Optional
import android.location
from android.location import Location, LocationManager, LocationListener
from android.content import Context
from android.os import PowerManager
from jnius import autoclass, cast

from .gps_manager import GPSManager, GPSPoint

class MobileGPSManager(GPSManager):
    def __init__(self, node_id: str, context: Context):
        super().__init__(node_id)
        self.context = context
        self._setup_location_manager()
        self._setup_wake_lock()
        
    def _setup_location_manager(self):
        """Sets up Android location manager"""
        self.location_manager = cast(
            'android.location.LocationManager',
            self.context.getSystemService(Context.LOCATION_SERVICE)
        )
        
        class LocationCallback(LocationListener):
            def __init__(self, manager):
                self.manager = manager
                
            def onLocationChanged(self, location):
                self.manager._last_location = location
                
            def onProviderDisabled(self, provider):
                pass
                
            def onProviderEnabled(self, provider):
                pass
                
            def onStatusChanged(self, provider, status, extras):
                pass
                
        self.location_callback = LocationCallback(self)
        
        # Request location updates
        self.location_manager.requestLocationUpdates(
            LocationManager.GPS_PROVIDER,
            1000,  # min time between updates (ms)
            1,     # min distance between updates (meters)
            self.location_callback
        )
        
    def _setup_wake_lock(self):
        """Sets up wake lock to keep device awake"""
        power_manager = cast(
            'android.os.PowerManager',
            self.context.getSystemService(Context.POWER_SERVICE)
        )
        
        self.wake_lock = power_manager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "LogiChain:GPSTracking"
        )
        self.wake_lock.acquire()
        
    def _collect_gps_data(self) -> Optional[GPSPoint]:
        """Collects GPS data from Android location services"""
        if not hasattr(self, '_last_location'):
            return None
            
        location = self._last_location
        
        if not location:
            return None
            
        return GPSPoint(
            latitude=location.getLatitude(),
            longitude=location.getLongitude(),
            timestamp=location.getTime() / 1000.0,  # Convert to seconds
            accuracy=location.getAccuracy(),
            speed=location.getSpeed() if location.hasSpeed() else None,
            heading=location.getBearing() if location.hasBearing() else None
        )
        
    def stop_collection(self):
        """Stops GPS collection and releases wake lock"""
        super().stop_collection()
        
        if hasattr(self, 'location_manager') and hasattr(self, 'location_callback'):
            self.location_manager.removeUpdates(self.location_callback)
            
        if hasattr(self, 'wake_lock') and self.wake_lock.isHeld():
            self.wake_lock.release() 