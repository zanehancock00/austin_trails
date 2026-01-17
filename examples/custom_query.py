#!/usr/bin/env python3
"""
Example: Custom Strava segment query

This example shows how to use the StravaClient programmatically
to build custom queries and analysis.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strava_client import StravaClient
from src.utils import filter_segments, sort_segments_by_elevation, calculate_elevation_per_km


def find_best_training_climbs():
    """
    Find the best training climbs:
    - Moderate distance (3-7 km)
    - Good elevation gain (75-150m)
    - Steady gradient (4-8%)

    These are perfect for interval training and building climbing strength.
    """
    print("Finding best training climbs near Austin...\n")

    # Initialize client
    client = StravaClient()

    # Austin coordinates
    austin_lat = 30.2672
    austin_lon = -97.7431

    # Search parameters
    radius = 15  # km
    radius_deg = radius / 111.0

    # Get segments
    segments = client.search_segments_by_bounds(
        austin_lat - radius_deg,
        austin_lon - radius_deg,
        austin_lat + radius_deg,
        austin_lon + radius_deg,
        activity_type='riding'
    )

    print(f"Found {len(segments)} total segments")

    # Filter for training climbs
    training_climbs = []
    for seg in segments:
        distance_km = seg.get('distance', 0) / 1000
        elev_gain = seg.get('elev_difference', 0)
        avg_grade = abs(seg.get('avg_grade', 0))

        # Training climb criteria
        if (3 <= distance_km <= 7 and
            75 <= elev_gain <= 150 and
            4 <= avg_grade <= 8):
            training_climbs.append(seg)

    print(f"Found {len(training_climbs)} ideal training climbs\n")

    # Sort by elevation per km (intensity)
    training_climbs = sorted(
        training_climbs,
        key=calculate_elevation_per_km,
        reverse=True
    )

    # Display top 10
    print("Top 10 Training Climbs (by intensity):\n")
    print(f"{'Name':<35} {'Dist (km)':<10} {'Elev (m)':<10} {'Grade %':<10} {'m/km'}")
    print("-" * 85)

    for seg in training_climbs[:10]:
        name = seg.get('name', 'Unknown')[:33]
        dist = seg.get('distance', 0) / 1000
        elev = seg.get('elev_difference', 0)
        grade = seg.get('avg_grade', 0)
        intensity = calculate_elevation_per_km(seg)

        print(f"{name:<35} {dist:<10.1f} {elev:<10.0f} {grade:<10.1f} {intensity:.1f}")

    return training_climbs


def find_epic_climbs():
    """
    Find epic climbs:
    - Significant elevation (200m+)
    - Can be longer
    - High climb category
    """
    print("\n\nFinding epic climbs near Austin...\n")

    client = StravaClient()

    austin_lat = 30.2672
    austin_lon = -97.7431
    radius = 20  # larger radius for epic climbs
    radius_deg = radius / 111.0

    segments = client.search_segments_by_bounds(
        austin_lat - radius_deg,
        austin_lon - radius_deg,
        austin_lat + radius_deg,
        austin_lon + radius_deg,
        activity_type='riding'
    )

    # Filter for epic climbs
    epic_climbs = filter_segments(
        segments,
        max_distance_km=20,  # longer is okay
        min_elevation_m=200,  # substantial elevation
    )

    epic_climbs = sort_segments_by_elevation(epic_climbs)

    print(f"Found {len(epic_climbs)} epic climbs\n")

    if epic_climbs:
        print("Top Epic Climbs:\n")
        print(f"{'Name':<40} {'Dist (km)':<10} {'Elev (m)':<10} {'Category'}")
        print("-" * 80)

        for seg in epic_climbs[:5]:
            name = seg.get('name', 'Unknown')[:38]
            dist = seg.get('distance', 0) / 1000
            elev = seg.get('elev_difference', 0)
            cat = seg.get('climb_category_desc', 'N/A')

            print(f"{name:<40} {dist:<10.1f} {elev:<10.0f} {cat}")
    else:
        print("No epic climbs found in this area.")
        print("Austin is relatively flat - try expanding the search radius!")

    return epic_climbs


def analyze_elevation_distribution(segments):
    """Analyze the distribution of elevation gains"""
    print("\n\nElevation Distribution Analysis:\n")

    # Create buckets
    buckets = {
        '0-50m': 0,
        '50-100m': 0,
        '100-150m': 0,
        '150-200m': 0,
        '200m+': 0
    }

    for seg in segments:
        elev = seg.get('elev_difference', 0)
        if elev < 50:
            buckets['0-50m'] += 1
        elif elev < 100:
            buckets['50-100m'] += 1
        elif elev < 150:
            buckets['100-150m'] += 1
        elif elev < 200:
            buckets['150-200m'] += 1
        else:
            buckets['200m+'] += 1

    print("Elevation Gain Distribution:")
    for bucket, count in buckets.items():
        bar = '█' * (count // 5)
        print(f"  {bucket:<12} {count:>4} {bar}")


def main():
    """Run all examples"""
    try:
        # Find different types of climbs
        training_climbs = find_best_training_climbs()
        epic_climbs = find_epic_climbs()

        # Combine all segments for analysis
        all_segments = training_climbs + epic_climbs
        if all_segments:
            analyze_elevation_distribution(all_segments)

        print("\n" + "=" * 85)
        print("Analysis complete!")
        print("=" * 85)

    except ValueError as e:
        print(f"Error: {e}")
        print("\nMake sure you have configured your Strava API credentials in .env")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
