"""
Flask web application for browsing Austin trail segments from Strava

Run with: python app.py
Then open http://localhost:5000 in your browser
"""

from flask import Flask, render_template, jsonify, request
from pathlib import Path
import sys
import json

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import config
from src.strava_client import StravaClient
from src.utils import (
    filter_segments,
    sort_segments_by_elevation,
    calculate_distance,
    calculate_elevation_per_km
)

app = Flask(__name__)

# Cedar Park, TX coordinates
CEDAR_PARK_LAT = 30.5052
CEDAR_PARK_LON = -97.8203

# Global cache for segments
segments_cache = None


def get_segments():
    """Get segments from cache or fetch from Strava"""
    global segments_cache

    if segments_cache is not None:
        return segments_cache

    try:
        # Initialize Strava client
        client = StravaClient()

        # Search parameters (wide area around Austin)
        center_lat = config.DEFAULT_LAT
        center_lon = config.DEFAULT_LON
        radius = 25  # km - wider search radius
        radius_deg = radius / 111.0

        # Get segments
        segments = client.search_segments_by_bounds(
            center_lat - radius_deg,
            center_lon - radius_deg,
            center_lat + radius_deg,
            center_lon + radius_deg,
            activity_type='riding'
        )

        # Enrich segments with calculated fields
        for seg in segments:
            # Distance from Cedar Park
            if 'start_latlng' in seg and seg['start_latlng']:
                seg['distance_from_cedar_park'] = calculate_distance(
                    CEDAR_PARK_LAT, CEDAR_PARK_LON,
                    seg['start_latlng'][0], seg['start_latlng'][1]
                )
            else:
                seg['distance_from_cedar_park'] = None

            # Convert to km for easier display
            seg['distance_km'] = seg.get('distance', 0) / 1000

            # Elevation per km
            seg['elevation_per_km'] = calculate_elevation_per_km(seg)

            # Strava URL
            seg['strava_url'] = f"https://www.strava.com/segments/{seg['id']}"

        segments_cache = segments
        return segments

    except Exception as e:
        print(f"Error fetching segments: {e}")
        return []


@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')


@app.route('/api/segments')
def api_segments():
    """API endpoint to get filtered segments"""
    segments = get_segments()

    if not segments:
        return jsonify({
            'error': 'No segments available. Check Strava credentials.',
            'segments': []
        })

    # Get filter parameters
    min_elevation = float(request.args.get('min_elevation', 0))
    max_elevation = float(request.args.get('max_elevation', 1000))
    min_distance = float(request.args.get('min_distance', 0))
    max_distance = float(request.args.get('max_distance', 100))
    max_distance_from_cedar = float(request.args.get('max_distance_from_cedar', 100))
    sort_by = request.args.get('sort_by', 'elevation')

    # Filter segments
    filtered = []
    for seg in segments:
        elev = seg.get('elev_difference', 0)
        dist = seg.get('distance_km', 0)
        dist_from_cedar = seg.get('distance_from_cedar_park')

        # Apply filters
        if elev < min_elevation or elev > max_elevation:
            continue
        if dist < min_distance or dist > max_distance:
            continue
        if dist_from_cedar is not None and dist_from_cedar > max_distance_from_cedar:
            continue

        filtered.append(seg)

    # Sort
    if sort_by == 'elevation':
        filtered.sort(key=lambda x: x.get('elev_difference', 0), reverse=True)
    elif sort_by == 'distance':
        filtered.sort(key=lambda x: x.get('distance_km', 0), reverse=True)
    elif sort_by == 'elevation_per_km':
        filtered.sort(key=lambda x: x.get('elevation_per_km', 0), reverse=True)
    elif sort_by == 'distance_from_cedar':
        filtered.sort(key=lambda x: x.get('distance_from_cedar_park') or 999)
    elif sort_by == 'grade':
        filtered.sort(key=lambda x: abs(x.get('avg_grade', 0)), reverse=True)

    return jsonify({
        'segments': filtered,
        'total': len(filtered),
        'cedar_park_location': {
            'lat': CEDAR_PARK_LAT,
            'lon': CEDAR_PARK_LON
        }
    })


@app.route('/api/stats')
def api_stats():
    """Get statistics about available segments"""
    segments = get_segments()

    if not segments:
        return jsonify({'error': 'No segments available'})

    elevations = [s.get('elev_difference', 0) for s in segments]
    distances = [s.get('distance_km', 0) for s in segments]

    return jsonify({
        'total_segments': len(segments),
        'elevation_range': {
            'min': min(elevations) if elevations else 0,
            'max': max(elevations) if elevations else 0
        },
        'distance_range': {
            'min': min(distances) if distances else 0,
            'max': max(distances) if distances else 0
        }
    })


@app.route('/api/refresh')
def api_refresh():
    """Refresh segments from Strava"""
    global segments_cache
    segments_cache = None
    get_segments()
    return jsonify({'status': 'refreshed', 'total': len(segments_cache) if segments_cache else 0})


if __name__ == '__main__':
    print("\n" + "="*80)
    print("Austin Trails Web App")
    print("="*80)
    print("\nStarting web server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("="*80 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
