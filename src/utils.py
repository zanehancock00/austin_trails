"""Utility functions for Austin Trails"""

import json
import csv
from typing import List, Dict
from pathlib import Path
import math


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula

    Args:
        lat1: Latitude of point 1
        lon1: Longitude of point 1
        lat2: Latitude of point 2
        lon2: Longitude of point 2

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def filter_segments(
    segments: List[Dict],
    max_distance_km: float = 10,
    min_elevation_m: float = 50,
    center_lat: float = None,
    center_lon: float = None,
    radius_km: float = None
) -> List[Dict]:
    """
    Filter segments based on criteria

    Args:
        segments: List of segment dictionaries
        max_distance_km: Maximum segment distance in km
        min_elevation_m: Minimum elevation gain in meters
        center_lat: Center latitude for radius filter
        center_lon: Center longitude for radius filter
        radius_km: Maximum distance from center in km

    Returns:
        Filtered list of segments
    """
    filtered = []

    for seg in segments:
        # Convert distance to km
        distance_km = seg.get('distance', 0) / 1000

        # Get elevation gain
        elev_gain = seg.get('elev_difference') or seg.get('total_elevation_gain', 0)

        # Check distance and elevation criteria
        if distance_km > max_distance_km:
            continue

        if elev_gain < min_elevation_m:
            continue

        # Check radius if specified
        if center_lat is not None and center_lon is not None and radius_km is not None:
            # Use start coordinates
            seg_lat = None
            seg_lon = None

            if 'start_latlng' in seg and seg['start_latlng']:
                seg_lat = seg['start_latlng'][0]
                seg_lon = seg['start_latlng'][1]
            elif 'start_latitude' in seg:
                seg_lat = seg['start_latitude']
                seg_lon = seg['start_longitude']

            if seg_lat and seg_lon:
                dist = calculate_distance(center_lat, center_lon, seg_lat, seg_lon)
                if dist > radius_km:
                    continue

        filtered.append(seg)

    return filtered


def sort_segments_by_elevation(segments: List[Dict], reverse: bool = True) -> List[Dict]:
    """
    Sort segments by elevation gain

    Args:
        segments: List of segment dictionaries
        reverse: If True, sort descending (highest first)

    Returns:
        Sorted list of segments
    """
    def get_elevation(seg):
        return seg.get('elev_difference') or seg.get('total_elevation_gain', 0)

    return sorted(segments, key=get_elevation, reverse=reverse)


def calculate_elevation_per_km(segment: Dict) -> float:
    """
    Calculate elevation gain per kilometer

    Args:
        segment: Segment dictionary

    Returns:
        Elevation gain per km (m/km)
    """
    distance_km = segment.get('distance', 0) / 1000
    if distance_km == 0:
        return 0

    elev_gain = segment.get('elev_difference') or segment.get('total_elevation_gain', 0)
    return elev_gain / distance_km


def save_to_json(data: List[Dict], filepath: Path):
    """Save data to JSON file"""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Saved {len(data)} items to {filepath}")


def save_to_csv(segments: List[Dict], filepath: Path):
    """Save segments to CSV file"""
    if not segments:
        print("No segments to save")
        return

    # Determine fields
    fields = [
        'id', 'name', 'distance_km', 'elevation_gain_m', 'avg_grade',
        'elevation_per_km', 'climb_category', 'climb_category_desc',
        'city', 'state', 'start_latitude', 'start_longitude'
    ]

    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for seg in segments:
            row = {
                'id': seg.get('id'),
                'name': seg.get('name'),
                'distance_km': round(seg.get('distance', 0) / 1000, 2),
                'elevation_gain_m': seg.get('elev_difference') or seg.get('total_elevation_gain', 0),
                'avg_grade': seg.get('avg_grade') or seg.get('average_grade', 0),
                'elevation_per_km': round(calculate_elevation_per_km(seg), 1),
                'climb_category': seg.get('climb_category'),
                'climb_category_desc': seg.get('climb_category_desc'),
                'city': seg.get('city'),
                'state': seg.get('state'),
                'start_latitude': seg.get('start_latitude') or (
                    seg.get('start_latlng')[0] if seg.get('start_latlng') else None
                ),
                'start_longitude': seg.get('start_longitude') or (
                    seg.get('start_latlng')[1] if seg.get('start_latlng') else None
                ),
            }
            writer.writerow(row)

    print(f"Saved {len(segments)} segments to {filepath}")


def print_segment_summary(segments: List[Dict]):
    """Print a summary of segments"""
    if not segments:
        print("No segments found")
        return

    print(f"\nFound {len(segments)} segments:\n")
    print(f"{'Name':<40} {'Distance':<10} {'Elev Gain':<12} {'Avg Grade':<10} {'Category'}")
    print("-" * 100)

    for seg in segments:
        name = seg.get('name', 'Unknown')[:38]
        distance_km = seg.get('distance', 0) / 1000
        elev_gain = seg.get('elev_difference') or seg.get('total_elevation_gain', 0)
        avg_grade = seg.get('avg_grade') or seg.get('average_grade', 0)
        category = seg.get('climb_category_desc', 'N/A')

        print(f"{name:<40} {distance_km:>8.2f} km {elev_gain:>9.0f} m {avg_grade:>8.1f}% {category}")
