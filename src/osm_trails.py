"""
OpenStreetMap Trail Data Fetcher for Austin, TX

This module provides functionality to fetch trail and path data from OpenStreetMap
using the Overpass API. It includes caching to avoid repeated API calls and
supports filtering trails within a specific radius of a point.

Example usage:
    from src.osm_trails import OSMTrailFetcher

    fetcher = OSMTrailFetcher()
    trails = fetcher.get_trails()

    # Get trails near a specific point
    nearby = fetcher.get_trails_within_radius(30.2672, -97.7431, radius_miles=5)
"""

import json
import hashlib
import time
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import urllib.error


# Austin, TX bounding box (approximate)
AUSTIN_BBOX = {
    'south': 30.1,
    'north': 30.5,
    'west': -98.0,
    'east': -97.5
}

# Overpass API endpoint
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# Cache settings
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_EXPIRY_HOURS = 24

# Meters to miles conversion
METERS_TO_MILES = 0.000621371


class OSMTrailFetcher:
    """
    Fetches trail and path data from OpenStreetMap for the Austin, TX area.

    Attributes:
        bbox: Bounding box dictionary with south, north, west, east keys
        cache_dir: Directory for storing cached responses
        cache_expiry_hours: Number of hours before cache expires
    """

    def __init__(
        self,
        bbox: Optional[Dict[str, float]] = None,
        cache_dir: Optional[Path] = None,
        cache_expiry_hours: int = CACHE_EXPIRY_HOURS
    ):
        """
        Initialize the OSM Trail Fetcher.

        Args:
            bbox: Custom bounding box. Defaults to Austin area.
            cache_dir: Directory for cache files. Defaults to project cache dir.
            cache_expiry_hours: Hours until cached data expires. Defaults to 24.
        """
        self.bbox = bbox or AUSTIN_BBOX.copy()
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_expiry_hours = cache_expiry_hours

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, query: str) -> str:
        """
        Generate a cache key from a query string.

        Args:
            query: The Overpass query string

        Returns:
            MD5 hash of the query for use as cache filename
        """
        return hashlib.md5(query.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get the file path for a cache entry.

        Args:
            cache_key: The cache key (hash)

        Returns:
            Path to the cache file
        """
        return self.cache_dir / f"osm_trails_{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if a cache file exists and is not expired.

        Args:
            cache_path: Path to the cache file

        Returns:
            True if cache is valid, False otherwise
        """
        if not cache_path.exists():
            return False

        # Check modification time
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = mtime + timedelta(hours=self.cache_expiry_hours)

        return datetime.now() < expiry_time

    def _read_cache(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """
        Read data from cache file.

        Args:
            cache_path: Path to the cache file

        Returns:
            Cached data dictionary or None if read fails
        """
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _write_cache(self, cache_path: Path, data: Dict[str, Any]) -> None:
        """
        Write data to cache file.

        Args:
            cache_path: Path to the cache file
            data: Data to cache
        """
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not write cache: {e}")

    def _build_overpass_query(
        self,
        bbox: Optional[Dict[str, float]] = None,
        chunk_index: int = 0,
        chunk_size: int = 0
    ) -> str:
        """
        Build an Overpass QL query for trails.

        Args:
            bbox: Bounding box to query. Uses instance bbox if not provided.
            chunk_index: Index of chunk for paginated queries (not used in bbox queries)
            chunk_size: Size of chunks (not used in bbox queries)

        Returns:
            Overpass QL query string
        """
        box = bbox or self.bbox
        bbox_str = f"{box['south']},{box['west']},{box['north']},{box['east']}"

        # Query for ways tagged as trails, paths, footways, or tracks
        query = f"""
[out:json][timeout:90];
(
  // Paths and footways
  way["highway"="path"]({bbox_str});
  way["highway"="footway"]({bbox_str});
  way["highway"="track"]({bbox_str});

  // Leisure tracks (running tracks, etc.)
  way["leisure"="track"]({bbox_str});

  // Ways with explicit trail/hiking tags
  way["sac_scale"]({bbox_str});
  way["trail_visibility"]({bbox_str});
  way["hiking"="yes"]({bbox_str});
  way["foot"="designated"]({bbox_str});

  // Named trails
  way["route"="hiking"]({bbox_str});
);
out body geom;
"""
        return query.strip()

    def _execute_query(self, query: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Execute an Overpass API query with optional caching.

        Args:
            query: The Overpass QL query string
            use_cache: Whether to use caching. Defaults to True.

        Returns:
            API response as dictionary or None on failure
        """
        cache_key = self._get_cache_key(query)
        cache_path = self._get_cache_path(cache_key)

        # Check cache first
        if use_cache and self._is_cache_valid(cache_path):
            cached_data = self._read_cache(cache_path)
            if cached_data is not None:
                return cached_data

        # Execute API request
        try:
            data = urllib.parse.urlencode({'data': query}).encode('utf-8')
            request = urllib.request.Request(
                OVERPASS_API_URL,
                data=data,
                headers={
                    'User-Agent': 'AustinTrailsFetcher/1.0',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))

                # Cache the result
                if use_cache:
                    self._write_cache(cache_path, result)

                return result

        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}")
            if e.code == 429:
                print("Rate limited. Waiting 60 seconds...")
                time.sleep(60)
                return self._execute_query(query, use_cache)
            return None
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return None

    def _calculate_way_length(self, geometry: List[Dict[str, float]]) -> float:
        """
        Calculate the length of a way from its geometry.

        Args:
            geometry: List of coordinate dictionaries with 'lat' and 'lon' keys

        Returns:
            Length in meters
        """
        if not geometry or len(geometry) < 2:
            return 0.0

        total_length = 0.0

        for i in range(len(geometry) - 1):
            lat1 = geometry[i]['lat']
            lon1 = geometry[i]['lon']
            lat2 = geometry[i + 1]['lat']
            lon2 = geometry[i + 1]['lon']

            total_length += self._haversine_distance(lat1, lon1, lat2, lon2)

        return total_length

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two points using Haversine formula.

        Args:
            lat1: Latitude of point 1 in degrees
            lon1: Longitude of point 1 in degrees
            lat2: Latitude of point 2 in degrees
            lon2: Longitude of point 2 in degrees

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth's radius in meters

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _parse_way(self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse an OSM way element into a trail dictionary.

        Args:
            element: OSM way element from Overpass response

        Returns:
            Trail dictionary or None if parsing fails
        """
        if element.get('type') != 'way':
            return None

        geometry = element.get('geometry', [])
        if not geometry:
            return None

        tags = element.get('tags', {})

        # Extract coordinates as list of (lat, lon) tuples
        coordinates = [(point['lat'], point['lon']) for point in geometry]

        # Calculate length
        length_meters = self._calculate_way_length(geometry)
        length_miles = length_meters * METERS_TO_MILES

        # Get surface type
        surface = tags.get('surface', 'unknown')

        # Get trail name
        name = tags.get('name', '')
        if not name:
            # Try alternative name tags
            name = tags.get('ref', '') or tags.get('description', '')

        # Build trail dictionary
        trail = {
            'osm_id': element.get('id'),
            'name': name or f"Unnamed Trail {element.get('id')}",
            'coordinates': coordinates,
            'length_miles': round(length_miles, 2),
            'length_meters': round(length_meters, 1),
            'surface': surface,
            'highway_type': tags.get('highway', ''),
            'leisure_type': tags.get('leisure', ''),
            'access': tags.get('access', ''),
            'foot': tags.get('foot', ''),
            'bicycle': tags.get('bicycle', ''),
            'horse': tags.get('horse', ''),
            'sac_scale': tags.get('sac_scale', ''),
            'trail_visibility': tags.get('trail_visibility', ''),
            'width': tags.get('width', ''),
            'incline': tags.get('incline', ''),
            'operator': tags.get('operator', ''),
            'network': tags.get('network', ''),
            'description': tags.get('description', ''),
            'tags': tags  # Include all tags for reference
        }

        # Add centroid for proximity searches
        if coordinates:
            avg_lat = sum(c[0] for c in coordinates) / len(coordinates)
            avg_lon = sum(c[1] for c in coordinates) / len(coordinates)
            trail['centroid'] = (avg_lat, avg_lon)

        return trail

    def get_trails(
        self,
        bbox: Optional[Dict[str, float]] = None,
        use_cache: bool = True,
        min_length_miles: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Fetch all trails within the bounding box.

        Args:
            bbox: Custom bounding box. Uses instance bbox if not provided.
            use_cache: Whether to use caching. Defaults to True.
            min_length_miles: Minimum trail length to include. Defaults to 0.

        Returns:
            List of trail dictionaries
        """
        query = self._build_overpass_query(bbox)
        response = self._execute_query(query, use_cache)

        if not response:
            return []

        elements = response.get('elements', [])
        trails = []

        for element in elements:
            trail = self._parse_way(element)
            if trail and trail['length_miles'] >= min_length_miles:
                trails.append(trail)

        # Sort by length (longest first)
        trails.sort(key=lambda t: t['length_miles'], reverse=True)

        return trails

    def get_trails_within_radius(
        self,
        center_lat: float,
        center_lon: float,
        radius_miles: float = 5.0,
        use_cache: bool = True,
        min_length_miles: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get trails within a specific radius of a point.

        This method fetches trails from the full Austin bbox and then filters
        to those within the specified radius of the center point.

        Args:
            center_lat: Latitude of center point
            center_lon: Longitude of center point
            radius_miles: Radius in miles. Defaults to 5.
            use_cache: Whether to use caching. Defaults to True.
            min_length_miles: Minimum trail length to include. Defaults to 0.

        Returns:
            List of trail dictionaries within the radius, sorted by distance
        """
        # Convert radius to meters for calculation
        radius_meters = radius_miles / METERS_TO_MILES

        # Get all trails (uses cache)
        all_trails = self.get_trails(use_cache=use_cache, min_length_miles=min_length_miles)

        nearby_trails = []

        for trail in all_trails:
            centroid = trail.get('centroid')
            if not centroid:
                continue

            # Calculate distance from center to trail centroid
            distance = self._haversine_distance(
                center_lat, center_lon,
                centroid[0], centroid[1]
            )

            if distance <= radius_meters:
                # Add distance to trail info
                trail_copy = trail.copy()
                trail_copy['distance_from_center_miles'] = round(distance * METERS_TO_MILES, 2)
                nearby_trails.append(trail_copy)

        # Sort by distance from center
        nearby_trails.sort(key=lambda t: t['distance_from_center_miles'])

        return nearby_trails

    def get_trails_chunked(
        self,
        chunk_lat_size: float = 0.1,
        chunk_lon_size: float = 0.1,
        use_cache: bool = True,
        min_length_miles: float = 0.0,
        delay_seconds: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Fetch trails in chunks to handle large areas and avoid API timeouts.

        This method divides the bounding box into smaller chunks and queries
        each chunk separately, then deduplicates the results.

        Args:
            chunk_lat_size: Size of each chunk in latitude degrees. Defaults to 0.1.
            chunk_lon_size: Size of each chunk in longitude degrees. Defaults to 0.1.
            use_cache: Whether to use caching. Defaults to True.
            min_length_miles: Minimum trail length to include. Defaults to 0.
            delay_seconds: Delay between API calls to avoid rate limiting. Defaults to 1.

        Returns:
            Deduplicated list of trail dictionaries
        """
        all_trails: Dict[int, Dict[str, Any]] = {}  # Use OSM ID as key for deduplication

        # Calculate number of chunks
        lat_range = self.bbox['north'] - self.bbox['south']
        lon_range = self.bbox['east'] - self.bbox['west']

        num_lat_chunks = math.ceil(lat_range / chunk_lat_size)
        num_lon_chunks = math.ceil(lon_range / chunk_lon_size)
        total_chunks = num_lat_chunks * num_lon_chunks

        print(f"Fetching trails in {total_chunks} chunks...")

        chunk_num = 0
        for lat_idx in range(num_lat_chunks):
            for lon_idx in range(num_lon_chunks):
                chunk_num += 1

                # Calculate chunk bounds
                south = self.bbox['south'] + (lat_idx * chunk_lat_size)
                north = min(south + chunk_lat_size, self.bbox['north'])
                west = self.bbox['west'] + (lon_idx * chunk_lon_size)
                east = min(west + chunk_lon_size, self.bbox['east'])

                chunk_bbox = {
                    'south': south,
                    'north': north,
                    'west': west,
                    'east': east
                }

                print(f"  Chunk {chunk_num}/{total_chunks}: "
                      f"({south:.3f}, {west:.3f}) to ({north:.3f}, {east:.3f})")

                # Fetch trails for this chunk
                chunk_trails = self.get_trails(
                    bbox=chunk_bbox,
                    use_cache=use_cache,
                    min_length_miles=min_length_miles
                )

                # Add to results (deduplicating by OSM ID)
                for trail in chunk_trails:
                    osm_id = trail.get('osm_id')
                    if osm_id and osm_id not in all_trails:
                        all_trails[osm_id] = trail

                # Delay between requests (only if not using cached data)
                if chunk_num < total_chunks and delay_seconds > 0:
                    time.sleep(delay_seconds)

        # Convert to list and sort by length
        trails_list = list(all_trails.values())
        trails_list.sort(key=lambda t: t['length_miles'], reverse=True)

        print(f"Found {len(trails_list)} unique trails")

        return trails_list

    def clear_cache(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of cache files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("osm_trails_*.json"):
            try:
                cache_file.unlink()
                count += 1
            except IOError:
                pass
        return count

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about cached data.

        Returns:
            Dictionary with cache statistics
        """
        cache_files = list(self.cache_dir.glob("osm_trails_*.json"))

        total_size = sum(f.stat().st_size for f in cache_files)

        oldest = None
        newest = None

        for f in cache_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if oldest is None or mtime < oldest:
                oldest = mtime
            if newest is None or mtime > newest:
                newest = mtime

        return {
            'cache_dir': str(self.cache_dir),
            'num_files': len(cache_files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'oldest_entry': oldest.isoformat() if oldest else None,
            'newest_entry': newest.isoformat() if newest else None,
            'expiry_hours': self.cache_expiry_hours
        }


def get_austin_trails(
    use_cache: bool = True,
    min_length_miles: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch all Austin area trails.

    Args:
        use_cache: Whether to use caching. Defaults to True.
        min_length_miles: Minimum trail length to include. Defaults to 0.1.

    Returns:
        List of trail dictionaries
    """
    fetcher = OSMTrailFetcher()
    return fetcher.get_trails(use_cache=use_cache, min_length_miles=min_length_miles)


def get_trails_near_point(
    lat: float,
    lon: float,
    radius_miles: float = 5.0,
    use_cache: bool = True,
    min_length_miles: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch trails near a specific point.

    Args:
        lat: Latitude of the point
        lon: Longitude of the point
        radius_miles: Search radius in miles. Defaults to 5.
        use_cache: Whether to use caching. Defaults to True.
        min_length_miles: Minimum trail length to include. Defaults to 0.1.

    Returns:
        List of trail dictionaries sorted by distance from the point
    """
    fetcher = OSMTrailFetcher()
    return fetcher.get_trails_within_radius(
        lat, lon,
        radius_miles=radius_miles,
        use_cache=use_cache,
        min_length_miles=min_length_miles
    )


# Example usage and CLI interface
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch trail data from OpenStreetMap for Austin, TX'
    )
    parser.add_argument(
        '--lat',
        type=float,
        default=30.2672,
        help='Center latitude (default: 30.2672 - Austin downtown)'
    )
    parser.add_argument(
        '--lon',
        type=float,
        default=-97.7431,
        help='Center longitude (default: -97.7431 - Austin downtown)'
    )
    parser.add_argument(
        '--radius',
        type=float,
        default=10.0,
        help='Search radius in miles (default: 10)'
    )
    parser.add_argument(
        '--min-length',
        type=float,
        default=0.1,
        help='Minimum trail length in miles (default: 0.1)'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching'
    )
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear cache and exit'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output JSON file path'
    )

    args = parser.parse_args()

    fetcher = OSMTrailFetcher()

    if args.clear_cache:
        count = fetcher.clear_cache()
        print(f"Cleared {count} cache files")
        exit(0)

    print(f"Fetching trails within {args.radius} miles of ({args.lat}, {args.lon})...")
    print(f"Minimum trail length: {args.min_length} miles")
    print()

    trails = fetcher.get_trails_within_radius(
        args.lat, args.lon,
        radius_miles=args.radius,
        use_cache=not args.no_cache,
        min_length_miles=args.min_length
    )

    print(f"Found {len(trails)} trails\n")

    # Print summary
    print(f"{'Name':<45} {'Length':<12} {'Surface':<15} {'Distance':<10}")
    print("-" * 85)

    for trail in trails[:20]:  # Show top 20
        name = trail['name'][:43] if trail['name'] else 'Unnamed'
        length = f"{trail['length_miles']:.2f} mi"
        surface = trail['surface'][:13] if trail['surface'] else 'unknown'
        distance = f"{trail.get('distance_from_center_miles', 0):.2f} mi"

        print(f"{name:<45} {length:<12} {surface:<15} {distance:<10}")

    if len(trails) > 20:
        print(f"\n... and {len(trails) - 20} more trails")

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(trails, f, indent=2)
        print(f"\nSaved {len(trails)} trails to {output_path}")

    # Show cache info
    cache_info = fetcher.get_cache_info()
    print(f"\nCache: {cache_info['num_files']} files, {cache_info['total_size_mb']} MB")
