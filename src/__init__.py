"""Austin Trails - Elevation Training Route Finder"""

__version__ = "2.0.0"

# Elevation API module
from src.elevation import (
    ElevationService,
    ElevationStats,
    ElevationCache,
    calculate_route_stats,
    smooth_elevations,
    get_route_elevation_profile,
    get_elevation,
    get_elevations,
    calculate_distance,
    calculate_total_distance,
)

# Route analyzer module
from src.route_analyzer import (
    Route,
    RouteMetrics,
    RouteAnalyzer,
    analyze_segments,
    quick_rank,
)

# OSM trails module
from src.osm_trails import (
    OSMTrailFetcher,
    get_austin_trails,
    get_trails_near_point,
)
