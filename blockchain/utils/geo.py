"""
Geographic utilities for route calculations
"""

from math import radians, sin, cos, sqrt, atan2
from typing import Tuple

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    Returns distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return round(distance, 2)

def is_route_sequential(
    end_lat: float,
    end_lon: float,
    next_start_lat: float,
    next_start_lon: float,
    max_distance_km: float = 1.0
) -> bool:
    """
    Check if two route points are sequential (close enough)
    Returns True if points are within max_distance_km
    """
    distance = calculate_distance(end_lat, end_lon, next_start_lat, next_start_lon)
    return distance <= max_distance_km

def get_route_center(points: list) -> Tuple[float, float]:
    """
    Calculate the center point of a route
    Returns (latitude, longitude)
    """
    if not points:
        return 0.0, 0.0
        
    total_lat = sum(p["lat"] for p in points)
    total_lon = sum(p["lng"] for p in points)
    count = len(points)
    
    return round(total_lat/count, 6), round(total_lon/count, 6)

def calculate_route_deviation(
    actual_points: list,
    planned_points: list,
    max_deviation_km: float = 1.0
) -> Tuple[float, bool]:
    """
    Calculate deviation between actual and planned route
    Returns (max_deviation_km, is_within_limits)
    """
    if len(actual_points) != len(planned_points):
        return max_deviation_km + 1, False
        
    max_deviation = 0
    for actual, planned in zip(actual_points, planned_points):
        deviation = calculate_distance(
            actual["lat"], actual["lng"],
            planned["lat"], planned["lng"]
        )
        max_deviation = max(max_deviation, deviation)
        
    return max_deviation, max_deviation <= max_deviation_km 