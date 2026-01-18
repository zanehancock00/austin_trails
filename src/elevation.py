"""
Elevation data module for GPS coordinates.

This module provides functionality to query elevation data from the Open-Elevation API
and calculate elevation statistics for GPS routes. It includes caching, batching,
rate limit handling, and noise filtering capabilities.

Example usage:
    from src.elevation import ElevationService, calculate_route_stats

    # Create service instance
    service = ElevationService()

    # Get elevations for coordinates
    coords = [(30.2672, -97.7431), (30.2700, -97.7400)]
    elevations = service.get_elevations(coords)

    # Calculate route statistics
    stats = calculate_route_stats(coords, elevations)
    print(f"Total gain: {stats['total_gain_ft']} ft")
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

# Constants
METERS_TO_FEET = 3.28084
METERS_TO_MILES = 0.000621371
OPEN_ELEVATION_API_URL = "https://api.open-elevation.com/api/v1/lookup"
MAX_POINTS_PER_REQUEST = 100
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "data" / "elevation_cache"

# Rate limiting defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 1.0  # seconds
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_REQUEST_DELAY = 0.1  # seconds between requests


@dataclass
class ElevationStats:
    """Statistics for elevation data along a route."""

    total_gain_ft: float
    total_loss_ft: float
    max_elevation_ft: float
    min_elevation_ft: float
    net_elevation_change_ft: float
    total_distance_miles: float
    feet_per_mile: float
    start_elevation_ft: float
    end_elevation_ft: float

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "total_gain_ft": round(self.total_gain_ft, 1),
            "total_loss_ft": round(self.total_loss_ft, 1),
            "max_elevation_ft": round(self.max_elevation_ft, 1),
            "min_elevation_ft": round(self.min_elevation_ft, 1),
            "net_elevation_change_ft": round(self.net_elevation_change_ft, 1),
            "total_distance_miles": round(self.total_distance_miles, 3),
            "feet_per_mile": round(self.feet_per_mile, 1),
            "start_elevation_ft": round(self.start_elevation_ft, 1),
            "end_elevation_ft": round(self.end_elevation_ft, 1),
        }


class ElevationCache:
    """
    File-based cache for elevation data.

    Caches elevation lookups to avoid repeated API calls for the same coordinates.
    Uses a hash of coordinates as the cache key.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the elevation cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to data/elevation_cache.
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, float] = {}

    def _get_cache_key(self, lat: float, lon: float) -> str:
        """Generate a cache key for a coordinate pair."""
        # Round to 5 decimal places (~1.1m precision) for cache key
        coord_str = f"{lat:.5f},{lon:.5f}"
        return hashlib.md5(coord_str.encode()).hexdigest()[:12]

    def _get_cache_file(self) -> Path:
        """Get the path to the cache file."""
        return self.cache_dir / "elevations.json"

    def _load_cache(self) -> dict[str, float]:
        """Load the cache from disk."""
        cache_file = self._get_cache_file()
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self, cache: dict[str, float]) -> None:
        """Save the cache to disk."""
        cache_file = self._get_cache_file()
        try:
            with open(cache_file, "w") as f:
                json.dump(cache, f)
        except IOError:
            pass  # Silently fail on cache write errors

    def get(self, lat: float, lon: float) -> Optional[float]:
        """
        Get cached elevation for a coordinate.

        Args:
            lat: Latitude in degrees.
            lon: Longitude in degrees.

        Returns:
            Elevation in meters if cached, None otherwise.
        """
        key = self._get_cache_key(lat, lon)

        # Check memory cache first
        if key in self._memory_cache:
            return self._memory_cache[key]

        # Check disk cache
        disk_cache = self._load_cache()
        if key in disk_cache:
            self._memory_cache[key] = disk_cache[key]
            return disk_cache[key]

        return None

    def set(self, lat: float, lon: float, elevation: float) -> None:
        """
        Cache an elevation value for a coordinate.

        Args:
            lat: Latitude in degrees.
            lon: Longitude in degrees.
            elevation: Elevation in meters.
        """
        key = self._get_cache_key(lat, lon)
        self._memory_cache[key] = elevation

    def set_batch(self, coordinates: list[tuple[float, float]], elevations: list[float]) -> None:
        """
        Cache multiple elevation values at once.

        Args:
            coordinates: List of (lat, lon) tuples.
            elevations: List of elevation values in meters.
        """
        for (lat, lon), elev in zip(coordinates, elevations):
            key = self._get_cache_key(lat, lon)
            self._memory_cache[key] = elev

        # Persist to disk
        disk_cache = self._load_cache()
        disk_cache.update(self._memory_cache)
        self._save_cache(disk_cache)

    def clear(self) -> None:
        """Clear all cached data."""
        self._memory_cache.clear()
        cache_file = self._get_cache_file()
        if cache_file.exists():
            cache_file.unlink()


class ElevationService:
    """
    Service for querying elevation data from the Open-Elevation API.

    Handles batching, caching, and rate limiting for elevation lookups.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        request_delay: float = DEFAULT_REQUEST_DELAY,
    ):
        """
        Initialize the elevation service.

        Args:
            cache_dir: Directory for cache storage.
            max_retries: Maximum number of retry attempts for failed requests.
            initial_backoff: Initial backoff time in seconds.
            backoff_multiplier: Multiplier for exponential backoff.
            request_delay: Delay between API requests in seconds.
        """
        self.cache = ElevationCache(cache_dir)
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        self.request_delay = request_delay
        self._last_request_time = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Wait if needed to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def _make_request(self, coordinates: list[tuple[float, float]]) -> list[float]:
        """
        Make a single API request for elevation data.

        Args:
            coordinates: List of (lat, lon) tuples (max 100).

        Returns:
            List of elevations in meters.

        Raises:
            requests.RequestException: If the request fails after all retries.
        """
        locations = [{"latitude": lat, "longitude": lon} for lat, lon in coordinates]
        payload = {"locations": locations}

        backoff = self.initial_backoff
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()
                self._last_request_time = time.time()

                response = requests.post(
                    OPEN_ELEVATION_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(response.headers.get("Retry-After", backoff))
                    time.sleep(retry_after)
                    backoff *= self.backoff_multiplier
                    continue

                response.raise_for_status()

                data = response.json()
                return [result["elevation"] for result in data["results"]]

            except requests.RequestException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
                    backoff *= self.backoff_multiplier

        raise last_exception or requests.RequestException("Request failed after retries")

    def get_elevations(
        self,
        coordinates: list[tuple[float, float]],
        use_cache: bool = True,
    ) -> list[float]:
        """
        Get elevation data for a list of coordinates.

        Elevations are returned in feet. The method handles batching for large
        coordinate lists and uses caching to avoid redundant API calls.

        Args:
            coordinates: List of (lat, lon) tuples.
            use_cache: Whether to use cached values (default True).

        Returns:
            List of elevations in feet, in the same order as input coordinates.

        Raises:
            requests.RequestException: If API requests fail.
            ValueError: If coordinates list is empty.
        """
        if not coordinates:
            raise ValueError("Coordinates list cannot be empty")

        # Initialize results with None
        results: list[Optional[float]] = [None] * len(coordinates)
        uncached_indices: list[int] = []
        uncached_coords: list[tuple[float, float]] = []

        # Check cache for each coordinate
        for i, (lat, lon) in enumerate(coordinates):
            if use_cache:
                cached_elev = self.cache.get(lat, lon)
                if cached_elev is not None:
                    results[i] = cached_elev * METERS_TO_FEET
                    continue

            uncached_indices.append(i)
            uncached_coords.append((lat, lon))

        # Fetch uncached coordinates in batches
        if uncached_coords:
            fetched_elevations: list[float] = []

            for batch_start in range(0, len(uncached_coords), MAX_POINTS_PER_REQUEST):
                batch_end = min(batch_start + MAX_POINTS_PER_REQUEST, len(uncached_coords))
                batch = uncached_coords[batch_start:batch_end]

                batch_elevations = self._make_request(batch)
                fetched_elevations.extend(batch_elevations)

            # Cache the fetched values and update results
            self.cache.set_batch(uncached_coords, fetched_elevations)

            for idx, elev_meters in zip(uncached_indices, fetched_elevations):
                results[idx] = elev_meters * METERS_TO_FEET

        # All results should be filled now
        return [e for e in results if e is not None]

    def get_elevation(self, lat: float, lon: float, use_cache: bool = True) -> float:
        """
        Get elevation for a single coordinate.

        Args:
            lat: Latitude in degrees.
            lon: Longitude in degrees.
            use_cache: Whether to use cached values (default True).

        Returns:
            Elevation in feet.
        """
        return self.get_elevations([(lat, lon)], use_cache)[0]

    def clear_cache(self) -> None:
        """Clear the elevation cache."""
        self.cache.clear()


def smooth_elevations(
    elevations: list[float],
    window_size: int = 5,
    method: str = "moving_average",
) -> list[float]:
    """
    Smooth elevation data to reduce GPS noise.

    Args:
        elevations: List of elevation values in feet.
        window_size: Size of the smoothing window (must be odd for median).
        method: Smoothing method - 'moving_average' or 'median'.

    Returns:
        Smoothed elevation values.

    Raises:
        ValueError: If window_size is invalid or method is unknown.
    """
    if not elevations:
        return []

    if len(elevations) < window_size:
        return elevations.copy()

    if window_size < 1:
        raise ValueError("Window size must be at least 1")

    if method == "moving_average":
        smoothed = []
        half_window = window_size // 2

        for i in range(len(elevations)):
            start = max(0, i - half_window)
            end = min(len(elevations), i + half_window + 1)
            window = elevations[start:end]
            smoothed.append(sum(window) / len(window))

        return smoothed

    elif method == "median":
        if window_size % 2 == 0:
            raise ValueError("Window size must be odd for median smoothing")

        smoothed = []
        half_window = window_size // 2

        for i in range(len(elevations)):
            start = max(0, i - half_window)
            end = min(len(elevations), i + half_window + 1)
            window = sorted(elevations[start:end])
            mid = len(window) // 2
            smoothed.append(window[mid])

        return smoothed

    else:
        raise ValueError(f"Unknown smoothing method: {method}")


def calculate_distance(
    coord1: tuple[float, float],
    coord2: tuple[float, float],
) -> float:
    """
    Calculate distance between two coordinates using the Haversine formula.

    Args:
        coord1: First coordinate as (lat, lon) tuple.
        coord2: Second coordinate as (lat, lon) tuple.

    Returns:
        Distance in miles.
    """
    import math

    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Earth's radius in meters
    earth_radius_m = 6371000

    distance_m = earth_radius_m * c
    return distance_m * METERS_TO_MILES


def calculate_total_distance(coordinates: list[tuple[float, float]]) -> float:
    """
    Calculate total distance of a route.

    Args:
        coordinates: List of (lat, lon) tuples defining the route.

    Returns:
        Total distance in miles.
    """
    if len(coordinates) < 2:
        return 0.0

    total = 0.0
    for i in range(len(coordinates) - 1):
        total += calculate_distance(coordinates[i], coordinates[i + 1])

    return total


def calculate_route_stats(
    coordinates: list[tuple[float, float]],
    elevations: list[float],
    smooth: bool = True,
    smooth_window: int = 5,
    smooth_method: str = "moving_average",
    min_elevation_change: float = 3.0,
) -> ElevationStats:
    """
    Calculate comprehensive elevation statistics for a route.

    Args:
        coordinates: List of (lat, lon) tuples defining the route.
        elevations: List of elevation values in feet (same length as coordinates).
        smooth: Whether to apply smoothing to elevation data.
        smooth_window: Window size for smoothing.
        smooth_method: Smoothing method ('moving_average' or 'median').
        min_elevation_change: Minimum elevation change in feet to count as gain/loss.
            Helps filter out GPS noise.

    Returns:
        ElevationStats object with computed statistics.

    Raises:
        ValueError: If coordinates and elevations have different lengths.
    """
    if len(coordinates) != len(elevations):
        raise ValueError(
            f"Coordinates ({len(coordinates)}) and elevations ({len(elevations)}) "
            "must have the same length"
        )

    if not elevations:
        return ElevationStats(
            total_gain_ft=0.0,
            total_loss_ft=0.0,
            max_elevation_ft=0.0,
            min_elevation_ft=0.0,
            net_elevation_change_ft=0.0,
            total_distance_miles=0.0,
            feet_per_mile=0.0,
            start_elevation_ft=0.0,
            end_elevation_ft=0.0,
        )

    # Apply smoothing if requested
    if smooth and len(elevations) > 1:
        smoothed = smooth_elevations(elevations, smooth_window, smooth_method)
    else:
        smoothed = elevations.copy()

    # Calculate gain and loss with threshold
    total_gain = 0.0
    total_loss = 0.0

    for i in range(1, len(smoothed)):
        diff = smoothed[i] - smoothed[i - 1]
        if abs(diff) >= min_elevation_change:
            if diff > 0:
                total_gain += diff
            else:
                total_loss += abs(diff)

    # Calculate distance
    total_distance = calculate_total_distance(coordinates)

    # Calculate feet per mile
    feet_per_mile = total_gain / total_distance if total_distance > 0 else 0.0

    return ElevationStats(
        total_gain_ft=total_gain,
        total_loss_ft=total_loss,
        max_elevation_ft=max(smoothed),
        min_elevation_ft=min(smoothed),
        net_elevation_change_ft=smoothed[-1] - smoothed[0] if smoothed else 0.0,
        total_distance_miles=total_distance,
        feet_per_mile=feet_per_mile,
        start_elevation_ft=smoothed[0] if smoothed else 0.0,
        end_elevation_ft=smoothed[-1] if smoothed else 0.0,
    )


def get_route_elevation_profile(
    coordinates: list[tuple[float, float]],
    service: Optional[ElevationService] = None,
    smooth: bool = True,
) -> tuple[list[float], list[float], ElevationStats]:
    """
    Get complete elevation profile for a route.

    This is a convenience function that fetches elevations, calculates cumulative
    distances, and computes statistics in one call.

    Args:
        coordinates: List of (lat, lon) tuples defining the route.
        service: ElevationService instance (creates new one if not provided).
        smooth: Whether to apply smoothing to elevation data.

    Returns:
        Tuple of (cumulative_distances, elevations, stats) where:
        - cumulative_distances: Distance from start in miles for each point
        - elevations: Elevation in feet for each point (smoothed if requested)
        - stats: ElevationStats object with computed statistics
    """
    if service is None:
        service = ElevationService()

    # Get elevations
    elevations = service.get_elevations(coordinates)

    # Calculate cumulative distances
    cumulative_distances = [0.0]
    for i in range(1, len(coordinates)):
        dist = calculate_distance(coordinates[i - 1], coordinates[i])
        cumulative_distances.append(cumulative_distances[-1] + dist)

    # Smooth if requested
    if smooth:
        smoothed_elevations = smooth_elevations(elevations)
    else:
        smoothed_elevations = elevations

    # Calculate stats
    stats = calculate_route_stats(coordinates, elevations, smooth=smooth)

    return cumulative_distances, smoothed_elevations, stats


# Module-level convenience functions
_default_service: Optional[ElevationService] = None


def get_default_service() -> ElevationService:
    """Get or create the default elevation service instance."""
    global _default_service
    if _default_service is None:
        _default_service = ElevationService()
    return _default_service


def get_elevation(lat: float, lon: float) -> float:
    """
    Get elevation for a single coordinate using the default service.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        Elevation in feet.
    """
    return get_default_service().get_elevation(lat, lon)


def get_elevations(coordinates: list[tuple[float, float]]) -> list[float]:
    """
    Get elevations for multiple coordinates using the default service.

    Args:
        coordinates: List of (lat, lon) tuples.

    Returns:
        List of elevations in feet.
    """
    return get_default_service().get_elevations(coordinates)
