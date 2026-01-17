#!/usr/bin/env python3
"""
Main script to query Strava for high-elevation trails near Austin, TX

This script finds segments with high elevation gain that aren't too long,
perfect for challenging climbs without excessive distance.
"""

import argparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.strava_client import StravaClient
from src.utils import (
    filter_segments,
    sort_segments_by_elevation,
    save_to_json,
    save_to_csv,
    print_segment_summary
)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Query Strava for high-elevation trails near a location'
    )

    parser.add_argument(
        '--lat',
        type=float,
        default=config.DEFAULT_LAT,
        help=f'Latitude (default: {config.DEFAULT_LAT} - Austin, TX)'
    )

    parser.add_argument(
        '--lon',
        type=float,
        default=config.DEFAULT_LON,
        help=f'Longitude (default: {config.DEFAULT_LON} - Austin, TX)'
    )

    parser.add_argument(
        '--max-distance',
        type=float,
        default=config.DEFAULT_MAX_DISTANCE,
        help=f'Maximum segment distance in km (default: {config.DEFAULT_MAX_DISTANCE})'
    )

    parser.add_argument(
        '--min-elevation',
        type=float,
        default=config.DEFAULT_MIN_ELEVATION,
        help=f'Minimum elevation gain in meters (default: {config.DEFAULT_MIN_ELEVATION})'
    )

    parser.add_argument(
        '--radius',
        type=float,
        default=config.DEFAULT_SEARCH_RADIUS,
        help=f'Search radius in km (default: {config.DEFAULT_SEARCH_RADIUS})'
    )

    parser.add_argument(
        '--activity-type',
        choices=['riding', 'running'],
        default='riding',
        help='Activity type (default: riding)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(config.DATA_DIR),
        help=f'Output directory (default: {config.DATA_DIR})'
    )

    parser.add_argument(
        '--get-details',
        action='store_true',
        help='Fetch detailed information for each segment (slower but more data)'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=None,
        help='Only show top N segments by elevation gain'
    )

    return parser.parse_args()


def main():
    """Main execution function"""
    args = parse_args()

    print("=" * 100)
    print("Austin Trails - Strava Elevation Query")
    print("=" * 100)
    print(f"\nSearch Parameters:")
    print(f"  Location: ({args.lat}, {args.lon})")
    print(f"  Search Radius: {args.radius} km")
    print(f"  Max Distance: {args.max_distance} km")
    print(f"  Min Elevation Gain: {args.min_elevation} m")
    print(f"  Activity Type: {args.activity_type}")
    print()

    # Initialize Strava client
    try:
        client = StravaClient()
        print("✓ Connected to Strava API")
    except ValueError as e:
        print(f"✗ Error: {e}")
        print("\nPlease set up your Strava API credentials in the .env file")
        print("See README.md for instructions")
        return 1

    # Search for segments
    print(f"\nSearching for segments near ({args.lat}, {args.lon})...")

    # Calculate bounds for search
    # Approximate: 1 degree latitude ≈ 111 km
    radius_deg = args.radius / 111.0
    sw_lat = args.lat - radius_deg
    sw_lon = args.lon - radius_deg
    ne_lat = args.lat + radius_deg
    ne_lon = args.lon + radius_deg

    segments = client.search_segments_by_bounds(
        sw_lat, sw_lon, ne_lat, ne_lon,
        activity_type=args.activity_type
    )

    print(f"✓ Found {len(segments)} segments in search area")

    if not segments:
        print("\nNo segments found. Try:")
        print("  - Increasing the search radius (--radius)")
        print("  - Changing the location (--lat, --lon)")
        print("  - Changing activity type (--activity-type)")
        return 0

    # Filter segments
    print(f"\nFiltering segments...")
    filtered = filter_segments(
        segments,
        max_distance_km=args.max_distance,
        min_elevation_m=args.min_elevation,
        center_lat=args.lat,
        center_lon=args.lon,
        radius_km=args.radius
    )

    print(f"✓ {len(filtered)} segments match criteria:")
    print(f"  - Distance ≤ {args.max_distance} km")
    print(f"  - Elevation gain ≥ {args.min_elevation} m")

    if not filtered:
        print("\nNo segments match the criteria. Try:")
        print("  - Lowering minimum elevation (--min-elevation)")
        print("  - Increasing maximum distance (--max-distance)")
        return 0

    # Get detailed information if requested
    if args.get_details:
        print(f"\nFetching detailed information for {len(filtered)} segments...")
        detailed_segments = []
        for i, seg in enumerate(filtered, 1):
            print(f"  [{i}/{len(filtered)}] {seg.get('name', 'Unknown')}", end='\r')
            details = client.get_segment_details(seg['id'])
            if details:
                detailed_segments.append(details)

        print()  # New line after progress
        filtered = detailed_segments
        print(f"✓ Retrieved details for {len(filtered)} segments")

    # Sort by elevation gain
    sorted_segments = sort_segments_by_elevation(filtered)

    # Limit to top N if specified
    if args.top:
        sorted_segments = sorted_segments[:args.top]
        print(f"\nShowing top {len(sorted_segments)} segments by elevation gain")

    # Print summary
    print_segment_summary(sorted_segments)

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    json_file = output_dir / "segments.json"
    csv_file = output_dir / "segments.csv"

    print(f"\nSaving results...")
    save_to_json(sorted_segments, json_file)
    save_to_csv(sorted_segments, csv_file)

    print(f"\n{'=' * 100}")
    print(f"✓ Complete! Found {len(sorted_segments)} high-elevation segments")
    print(f"  Results saved to: {output_dir}")
    print(f"{'=' * 100}\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
