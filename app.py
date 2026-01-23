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
        print(f"Returning cached segments: {len(segments_cache)} segments")
        return segments_cache

    print("Fetching fresh segments from Strava...")

    try:
        # Initialize Strava client
        client = StravaClient()

        # Search parameters (Greater Austin area)
        center_lat = config.DEFAULT_LAT
        center_lon = config.DEFAULT_LON
        radius = 30  # km - covers Cedar Park, Round Rock, Lakeway, Pflugerville
        radius_deg = radius / 111.0

        # Get segments
        segments = client.search_segments_by_bounds(
            center_lat - radius_deg,
            center_lon - radius_deg,
            center_lat + radius_deg,
            center_lon + radius_deg,
            activity_type='running'
        )

        print(f"Found {len(segments)} running segments in the area")
        print(f"Search bounds: SW({center_lat - radius_deg:.4f}, {center_lon - radius_deg:.4f}) to NE({center_lat + radius_deg:.4f}, {center_lon + radius_deg:.4f})")

        # Debug: Print first few segment names
        if segments:
            print("Sample segments:")
            for seg in segments[:5]:
                print(f"  - {seg.get('name', 'Unknown')}: {seg.get('elev_difference', 0)}m elevation, {seg.get('distance', 0)/1000:.2f}km")

        # Mt. Bonnell is around 30.3167, -97.7714
        print(f"Mt. Bonnell approximate location: 30.3167, -97.7714")
        print(f"Is Mt. Bonnell in search bounds? {(center_lat - radius_deg) <= 30.3167 <= (center_lat + radius_deg) and (center_lon - radius_deg) <= -97.7714 <= (center_lon + radius_deg)}")

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

            # Imperial conversions
            seg['distance_miles'] = seg['distance_km'] * 0.621371
            seg['elev_difference_feet'] = seg.get('elev_difference', 0) * 3.28084
            if seg.get('distance_from_cedar_park') is not None:
                seg['distance_from_cedar_park_miles'] = seg['distance_from_cedar_park'] * 0.621371

            # Elevation per km
            seg['elevation_per_km'] = calculate_elevation_per_km(seg)

            # Elevation per mile (feet per mile)
            if seg['distance_miles'] > 0:
                seg['elevation_per_mile'] = seg['elev_difference_feet'] / seg['distance_miles']
            else:
                seg['elevation_per_mile'] = 0

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
    filter_stats = {
        'total': len(segments),
        'failed_elevation': 0,
        'failed_distance': 0,
        'failed_cedar_distance': 0
    }

    for seg in segments:
        elev = seg.get('elev_difference', 0)
        dist = seg.get('distance_km', 0)
        dist_from_cedar = seg.get('distance_from_cedar_park')

        # Apply filters
        if elev < min_elevation or elev > max_elevation:
            filter_stats['failed_elevation'] += 1
            continue
        if dist < min_distance or dist > max_distance:
            filter_stats['failed_distance'] += 1
            continue
        if dist_from_cedar is not None and dist_from_cedar > max_distance_from_cedar:
            filter_stats['failed_cedar_distance'] += 1
            continue

        filtered.append(seg)

    print(f"Filter results: {len(filtered)}/{filter_stats['total']} segments passed filters")
    print(f"  - Failed elevation filter ({min_elevation}m-{max_elevation}m): {filter_stats['failed_elevation']}")
    print(f"  - Failed distance filter ({min_distance}km-{max_distance}km): {filter_stats['failed_distance']}")
    print(f"  - Failed Cedar Park distance filter (<{max_distance_from_cedar}km): {filter_stats['failed_cedar_distance']}")

    # Sort
    if sort_by == 'elevation_desc':
        filtered.sort(key=lambda x: x.get('elev_difference', 0), reverse=True)
    elif sort_by == 'elevation_asc':
        filtered.sort(key=lambda x: x.get('elev_difference', 0), reverse=False)
    elif sort_by == 'distance_desc':
        filtered.sort(key=lambda x: x.get('distance_km', 0), reverse=True)
    elif sort_by == 'distance_asc':
        filtered.sort(key=lambda x: x.get('distance_km', 0), reverse=False)
    elif sort_by == 'elevation_per_km':
        filtered.sort(key=lambda x: x.get('elevation_per_km', 0), reverse=True)
    elif sort_by == 'distance_from_cedar':
        filtered.sort(key=lambda x: x.get('distance_from_cedar_park') or 999)
    elif sort_by == 'grade':
        filtered.sort(key=lambda x: abs(x.get('avg_grade', 0)), reverse=True)
    # Legacy support for old 'elevation' and 'distance' values
    elif sort_by == 'elevation':
        filtered.sort(key=lambda x: x.get('elev_difference', 0), reverse=True)
    elif sort_by == 'distance':
        filtered.sort(key=lambda x: x.get('distance_km', 0), reverse=True)

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


@app.route('/api/routes')
def api_routes():
    """Get athlete's personal routes"""
    try:
        client = StravaClient()
        routes = client.get_athlete_routes()

        # Enrich routes with calculated fields (similar to segments)
        for route in routes:
            # Distance conversions
            route['distance_km'] = route.get('distance', 0) / 1000
            route['distance_miles'] = route['distance_km'] * 0.621371

            # Elevation conversions
            route['elev_difference'] = route.get('elevation_gain', 0)
            route['elev_difference_feet'] = route['elev_difference'] * 3.28084

            # Calculate intensity
            if route['distance_km'] > 0:
                route['elevation_per_km'] = route['elev_difference'] / route['distance_km']
                route['elevation_per_mile'] = route['elev_difference_feet'] / route['distance_miles']
            else:
                route['elevation_per_km'] = 0
                route['elevation_per_mile'] = 0

            # Strava URL
            route['strava_url'] = f"https://www.strava.com/routes/{route['id']}"
            route['is_route'] = True  # Flag to distinguish from segments

        return jsonify({
            'routes': routes,
            'total': len(routes)
        })

    except Exception as e:
        return jsonify({
            'error': f'Error fetching routes: {str(e)}',
            'routes': []
        })


@app.route('/elevation-routes')
def elevation_routes():
    """Render the elevation training routes page"""
    return render_template('elevation_routes.html')


@app.route('/api/elevation-routes')
def api_elevation_routes():
    """API endpoint for elevation training routes with enhanced filtering"""
    segments = get_segments()

    if not segments:
        return jsonify({
            'error': 'No segments available. Check Strava credentials.',
            'segments': []
        })

    # Get filter parameters (in imperial units from frontend)
    min_distance_miles = float(request.args.get('min_distance', 0))
    max_distance_miles = float(request.args.get('max_distance', 50))
    min_ft_per_mile = float(request.args.get('min_ft_per_mile', 0))
    max_ft_per_mile = float(request.args.get('max_ft_per_mile', 1000))
    surface_type = request.args.get('surface_type', 'all')  # all, paved, trail
    sort_by = request.args.get('sort_by', 'ft_per_mile_desc')

    # Filter segments
    filtered = []
    for seg in segments:
        dist_miles = seg.get('distance_miles', 0)
        ft_per_mile = seg.get('elevation_per_mile', 0)

        # Apply distance filter
        if dist_miles < min_distance_miles or dist_miles > max_distance_miles:
            continue

        # Apply feet-per-mile filter
        if ft_per_mile < min_ft_per_mile or ft_per_mile > max_ft_per_mile:
            continue

        # Surface type filter (heuristic based on segment name/category)
        if surface_type != 'all':
            name_lower = seg.get('name', '').lower()
            is_trail = any(word in name_lower for word in ['trail', 'path', 'greenbelt', 'creek', 'park', 'nature'])
            is_paved = any(word in name_lower for word in ['road', 'street', 'ave', 'blvd', 'highway', 'hwy'])

            if surface_type == 'trail' and not is_trail:
                continue
            if surface_type == 'paved' and not is_paved and is_trail:
                continue

        # Add color coding based on intensity (ft/mile)
        if ft_per_mile >= 300:
            seg['intensity_color'] = '#d32f2f'  # Red - very steep
            seg['intensity_label'] = 'Very Steep'
        elif ft_per_mile >= 200:
            seg['intensity_color'] = '#f57c00'  # Orange - steep
            seg['intensity_label'] = 'Steep'
        elif ft_per_mile >= 100:
            seg['intensity_color'] = '#fbc02d'  # Yellow - moderate
            seg['intensity_label'] = 'Moderate'
        else:
            seg['intensity_color'] = '#388e3c'  # Green - easy
            seg['intensity_label'] = 'Easy'

        filtered.append(seg)

    # Sort
    if sort_by == 'ft_per_mile_desc':
        filtered.sort(key=lambda x: x.get('elevation_per_mile', 0), reverse=True)
    elif sort_by == 'ft_per_mile_asc':
        filtered.sort(key=lambda x: x.get('elevation_per_mile', 0))
    elif sort_by == 'distance_desc':
        filtered.sort(key=lambda x: x.get('distance_miles', 0), reverse=True)
    elif sort_by == 'distance_asc':
        filtered.sort(key=lambda x: x.get('distance_miles', 0))
    elif sort_by == 'elevation_desc':
        filtered.sort(key=lambda x: x.get('elev_difference_feet', 0), reverse=True)
    elif sort_by == 'elevation_asc':
        filtered.sort(key=lambda x: x.get('elev_difference_feet', 0))
    elif sort_by == 'grade_desc':
        filtered.sort(key=lambda x: abs(x.get('avg_grade', 0)), reverse=True)

    return jsonify({
        'segments': filtered,
        'total': len(filtered),
        'center': {
            'lat': config.DEFAULT_LAT,
            'lon': config.DEFAULT_LON
        }
    })


@app.route('/api/segment/<int:segment_id>/streams')
def api_segment_streams(segment_id):
    """Get elevation stream data for a segment (for elevation profile chart)"""
    try:
        client = StravaClient()

        # Try to get segment details, but don't fail if it doesn't work
        segment_details = client.get_segment_details(segment_id)
        has_details = segment_details and 'error' not in segment_details

        if not has_details:
            # Log the error but continue to try fetching stream data
            if segment_details and 'error' in segment_details:
                print(f"Segment {segment_id} details unavailable: {segment_details['error']}")
            else:
                print(f"Segment {segment_id} details returned None")

            # Set default values for segment details
            segment_details = {
                'name': f'Segment {segment_id}',
                'total_elevation_gain': 0,
                'average_grade': 0,
                'maximum_grade': 0,
                'elevation_high': 0,
                'elevation_low': 0
            }

        # Try to get stream data from Strava API
        try:
            import requests
            import time

            time.sleep(config.RATE_LIMIT_DELAY)

            url = f"https://www.strava.com/api/v3/segments/{segment_id}/streams"
            params = {
                'keys': 'distance,altitude,latlng',
                'key_by_type': 'true'
            }
            headers = {'Authorization': f'Bearer {client.access_token}'}

            response = requests.get(url, params=params, headers=headers)

            if response.status_code == 200:
                stream_data = response.json()

                # Process stream data for elevation profile
                distance_data = stream_data.get('distance', {}).get('data', [])
                altitude_data = stream_data.get('altitude', {}).get('data', [])
                latlng_data = stream_data.get('latlng', {}).get('data', [])

                # Convert to feet and miles
                distance_miles = [d * 0.000621371 for d in distance_data]
                altitude_feet = [a * 3.28084 for a in altitude_data]

                # Calculate grade for each point
                grades = []
                steep_sections = []
                for i in range(len(distance_data)):
                    if i == 0:
                        grades.append(0)
                    else:
                        dist_diff = distance_data[i] - distance_data[i-1]
                        alt_diff = altitude_data[i] - altitude_data[i-1]
                        if dist_diff > 0:
                            grade = (alt_diff / dist_diff) * 100
                            grades.append(grade)
                            # Mark steep sections (>8% grade)
                            if abs(grade) > 8:
                                steep_sections.append({
                                    'start_distance': distance_miles[i-1],
                                    'end_distance': distance_miles[i],
                                    'grade': grade
                                })
                        else:
                            grades.append(0)

                return jsonify({
                    'segment_id': segment_id,
                    'name': segment_details.get('name', 'Unknown'),
                    'distance_miles': distance_miles,
                    'altitude_feet': altitude_feet,
                    'latlng': latlng_data,
                    'grades': grades,
                    'steep_sections': steep_sections,
                    'total_elevation_gain_feet': segment_details.get('total_elevation_gain', 0) * 3.28084,
                    'avg_grade': segment_details.get('average_grade', 0),
                    'max_grade': segment_details.get('maximum_grade', 0),
                    'elevation_high_feet': segment_details.get('elevation_high', 0) * 3.28084,
                    'elevation_low_feet': segment_details.get('elevation_low', 0) * 3.28084
                })
            else:
                # Fallback to basic segment info without stream
                return jsonify({
                    'segment_id': segment_id,
                    'name': segment_details.get('name', 'Unknown'),
                    'distance_miles': [],
                    'altitude_feet': [],
                    'latlng': [],
                    'grades': [],
                    'steep_sections': [],
                    'total_elevation_gain_feet': segment_details.get('total_elevation_gain', 0) * 3.28084,
                    'avg_grade': segment_details.get('average_grade', 0),
                    'max_grade': segment_details.get('maximum_grade', 0),
                    'elevation_high_feet': segment_details.get('elevation_high', 0) * 3.28084,
                    'elevation_low_feet': segment_details.get('elevation_low', 0) * 3.28084,
                    'message': 'Stream data not available for this segment'
                })

        except Exception as stream_error:
            print(f"Error fetching stream data: {stream_error}")
            return jsonify({
                'segment_id': segment_id,
                'name': segment_details.get('name', 'Unknown'),
                'error': f'Stream data not available: {str(stream_error)}',
                'total_elevation_gain_feet': segment_details.get('total_elevation_gain', 0) * 3.28084,
                'avg_grade': segment_details.get('average_grade', 0),
                'max_grade': segment_details.get('maximum_grade', 0)
            })

    except Exception as e:
        return jsonify({'error': f'Error fetching segment: {str(e)}'}), 500


@app.route('/api/segment/<int:segment_id>')
def api_segment_details(segment_id):
    """Get detailed information about a specific segment"""
    try:
        client = StravaClient()
        details = client.get_segment_details(segment_id)

        if not details:
            return jsonify({'error': 'Segment not found'}), 404

        # Check if details contains an error
        if 'error' in details:
            error_msg = details['error']
            print(f"Segment {segment_id} error: {error_msg}")
            return jsonify({'error': f'Unable to load segment: {error_msg}'}), 404

        # Add imperial conversions
        details['distance_miles'] = details.get('distance', 0) * 0.000621371
        details['total_elevation_gain_feet'] = details.get('total_elevation_gain', 0) * 3.28084
        details['elevation_high_feet'] = details.get('elevation_high', 0) * 3.28084
        details['elevation_low_feet'] = details.get('elevation_low', 0) * 3.28084

        if details['distance_miles'] > 0:
            details['elevation_per_mile'] = details['total_elevation_gain_feet'] / details['distance_miles']
        else:
            details['elevation_per_mile'] = 0

        details['strava_url'] = f"https://www.strava.com/segments/{segment_id}"

        return jsonify(details)

    except Exception as e:
        return jsonify({'error': f'Error fetching segment: {str(e)}'}), 500


if __name__ == '__main__':
    import os

    print("\n" + "="*80)
    print("Austin Trails Web App")
    print("="*80)
    print("\nStarting web server...")

    # Use PORT environment variable for production deployments (Heroku, Render, etc.)
    port = int(os.environ.get('PORT', 5000))

    # Debug mode should be off in production
    debug = os.environ.get('FLASK_ENV') != 'production'

    print(f"Server running on port {port}")
    print(f"Debug mode: {debug}")
    print("Open your browser to: http://localhost:5000" if port == 5000 else f"Open your browser to: http://0.0.0.0:{port}")
    print("\nPress Ctrl+C to stop the server")
    print("="*80 + "\n")

    app.run(debug=debug, host='0.0.0.0', port=port)
