"""
Route Analyzer Module for Austin Trails

Analyzes and ranks running routes by elevation metrics to help identify
challenging training routes. Key metric: feet gained per mile.

Reference benchmark: Canyons 50K has ~6,500 ft gain over 31 miles = ~210 ft/mile.
Routes exceeding this ratio are excellent for training.

Example usage:
    from src.route_analyzer import RouteAnalyzer, Route, ElevationPoint

    # Create routes from segment data
    routes = RouteAnalyzer.routes_from_segments(segments)

    # Analyze and rank routes
    analyzer = RouteAnalyzer(routes)
    ranked = analyzer.rank_by_feet_per_mile()

    # Filter for training routes
    training_routes = analyzer.filter_routes(
        min_distance_miles=3.0,
        max_distance_miles=10.0,
        min_elevation_gain_feet=500
    )

    # Generate report
    report = analyzer.generate_report(top_n=10)
    print(report)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import math
from pathlib import Path
import json


# Conversion constants
METERS_TO_FEET = 3.28084
METERS_TO_MILES = 0.000621371
KM_TO_MILES = 0.621371


@dataclass
class ElevationPoint:
    """A single point along a route with elevation data."""
    latitude: float
    longitude: float
    elevation_meters: float
    distance_from_start_meters: float = 0.0

    @property
    def elevation_feet(self) -> float:
        """Elevation in feet."""
        return self.elevation_meters * METERS_TO_FEET

    @property
    def distance_from_start_miles(self) -> float:
        """Distance from start in miles."""
        return self.distance_from_start_meters * METERS_TO_MILES


@dataclass
class RouteMetrics:
    """Calculated metrics for a route."""
    total_distance_miles: float
    total_elevation_gain_feet: float
    total_elevation_loss_feet: float
    feet_per_mile: float
    max_grade_percent: float
    min_elevation_feet: float
    max_elevation_feet: float
    avg_grade_percent: float

    # Training benchmark comparison
    canyons_50k_ratio: float = field(init=False)

    # Reference: Canyons 50K has ~210 ft/mile
    CANYONS_50K_FT_PER_MILE = 210.0

    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.canyons_50k_ratio = self.feet_per_mile / self.CANYONS_50K_FT_PER_MILE

    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary."""
        return {
            'total_distance_miles': round(self.total_distance_miles, 2),
            'total_elevation_gain_feet': round(self.total_elevation_gain_feet, 0),
            'total_elevation_loss_feet': round(self.total_elevation_loss_feet, 0),
            'feet_per_mile': round(self.feet_per_mile, 1),
            'max_grade_percent': round(self.max_grade_percent, 1),
            'min_elevation_feet': round(self.min_elevation_feet, 0),
            'max_elevation_feet': round(self.max_elevation_feet, 0),
            'avg_grade_percent': round(self.avg_grade_percent, 1),
            'canyons_50k_ratio': round(self.canyons_50k_ratio, 2),
        }


@dataclass
class Route:
    """
    Represents a running route with elevation data.

    A route can be a single segment or multiple segments combined.
    """
    id: str
    name: str
    elevation_profile: List[ElevationPoint] = field(default_factory=list)
    source_segment_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Cached metrics
    _metrics: Optional[RouteMetrics] = field(default=None, repr=False)

    @classmethod
    def from_segment(
        cls,
        segment: Dict[str, Any],
        elevation_data: Optional[List[Dict]] = None
    ) -> 'Route':
        """
        Create a Route from a Strava segment dictionary.

        Args:
            segment: Segment dictionary from Strava API
            elevation_data: Optional list of elevation points with lat, lng, elevation

        Returns:
            Route instance
        """
        segment_id = str(segment.get('id', ''))

        # Build elevation profile from data if provided
        elevation_profile = []
        if elevation_data:
            cumulative_distance = 0.0
            prev_point = None

            for point in elevation_data:
                if prev_point:
                    # Calculate distance from previous point
                    dist = _haversine_distance(
                        prev_point['lat'], prev_point['lng'],
                        point['lat'], point['lng']
                    )
                    cumulative_distance += dist

                elev_point = ElevationPoint(
                    latitude=point['lat'],
                    longitude=point['lng'],
                    elevation_meters=point.get('elevation', point.get('ele', 0)),
                    distance_from_start_meters=cumulative_distance
                )
                elevation_profile.append(elev_point)
                prev_point = point

        # Extract metadata
        metadata = {
            'distance_meters': segment.get('distance', 0),
            'elevation_gain_meters': (
                segment.get('elev_difference') or
                segment.get('total_elevation_gain', 0)
            ),
            'avg_grade': segment.get('avg_grade') or segment.get('average_grade', 0),
            'max_grade': segment.get('maximum_grade', 0),
            'city': segment.get('city', ''),
            'state': segment.get('state', ''),
            'climb_category': segment.get('climb_category'),
            'climb_category_desc': segment.get('climb_category_desc', ''),
            'start_latlng': segment.get('start_latlng'),
            'end_latlng': segment.get('end_latlng'),
        }

        return cls(
            id=segment_id,
            name=segment.get('name', f'Segment {segment_id}'),
            elevation_profile=elevation_profile,
            source_segment_ids=[segment_id],
            metadata=metadata,
        )

    @classmethod
    def from_coordinates(
        cls,
        route_id: str,
        name: str,
        coordinates: List[Tuple[float, float, float]]
    ) -> 'Route':
        """
        Create a Route from a list of coordinates with elevations.

        Args:
            route_id: Unique identifier for the route
            name: Route name
            coordinates: List of (latitude, longitude, elevation_meters) tuples

        Returns:
            Route instance
        """
        elevation_profile = []
        cumulative_distance = 0.0
        prev_coord = None

        for lat, lng, elev in coordinates:
            if prev_coord:
                dist = _haversine_distance(
                    prev_coord[0], prev_coord[1],
                    lat, lng
                )
                cumulative_distance += dist

            elev_point = ElevationPoint(
                latitude=lat,
                longitude=lng,
                elevation_meters=elev,
                distance_from_start_meters=cumulative_distance
            )
            elevation_profile.append(elev_point)
            prev_coord = (lat, lng)

        return cls(
            id=route_id,
            name=name,
            elevation_profile=elevation_profile,
        )

    def calculate_metrics(self, force_recalculate: bool = False) -> RouteMetrics:
        """
        Calculate all metrics for this route.

        Args:
            force_recalculate: If True, recalculate even if cached

        Returns:
            RouteMetrics instance
        """
        if self._metrics is not None and not force_recalculate:
            return self._metrics

        # If no elevation profile, use metadata
        if not self.elevation_profile:
            distance_miles = (
                self.metadata.get('distance_meters', 0) * METERS_TO_MILES
            )
            elev_gain_feet = (
                self.metadata.get('elevation_gain_meters', 0) * METERS_TO_FEET
            )

            feet_per_mile = elev_gain_feet / distance_miles if distance_miles > 0 else 0

            self._metrics = RouteMetrics(
                total_distance_miles=distance_miles,
                total_elevation_gain_feet=elev_gain_feet,
                total_elevation_loss_feet=0.0,  # Unknown without profile
                feet_per_mile=feet_per_mile,
                max_grade_percent=self.metadata.get('max_grade', 0),
                min_elevation_feet=0.0,
                max_elevation_feet=elev_gain_feet,  # Approximation
                avg_grade_percent=self.metadata.get('avg_grade', 0),
            )
            return self._metrics

        # Calculate from elevation profile
        total_gain = 0.0
        total_loss = 0.0
        max_grade = 0.0
        elevations = []
        grades = []

        for i, point in enumerate(self.elevation_profile):
            elevations.append(point.elevation_feet)

            if i > 0:
                prev_point = self.elevation_profile[i - 1]
                elev_diff = point.elevation_meters - prev_point.elevation_meters
                dist_diff = (
                    point.distance_from_start_meters -
                    prev_point.distance_from_start_meters
                )

                if elev_diff > 0:
                    total_gain += elev_diff * METERS_TO_FEET
                else:
                    total_loss += abs(elev_diff) * METERS_TO_FEET

                # Calculate grade for this segment
                if dist_diff > 0:
                    grade = (elev_diff / dist_diff) * 100
                    grades.append(grade)
                    if abs(grade) > abs(max_grade):
                        max_grade = grade

        total_distance_miles = (
            self.elevation_profile[-1].distance_from_start_meters * METERS_TO_MILES
            if self.elevation_profile else 0
        )

        feet_per_mile = total_gain / total_distance_miles if total_distance_miles > 0 else 0
        avg_grade = sum(grades) / len(grades) if grades else 0

        self._metrics = RouteMetrics(
            total_distance_miles=total_distance_miles,
            total_elevation_gain_feet=total_gain,
            total_elevation_loss_feet=total_loss,
            feet_per_mile=feet_per_mile,
            max_grade_percent=max_grade,
            min_elevation_feet=min(elevations) if elevations else 0,
            max_elevation_feet=max(elevations) if elevations else 0,
            avg_grade_percent=avg_grade,
        )

        return self._metrics

    def get_elevation_profile_for_plot(self) -> Tuple[List[float], List[float]]:
        """
        Get elevation profile data suitable for plotting.

        Returns:
            Tuple of (distances_miles, elevations_feet)
        """
        if not self.elevation_profile:
            return [], []

        distances = [p.distance_from_start_miles for p in self.elevation_profile]
        elevations = [p.elevation_feet for p in self.elevation_profile]

        return distances, elevations

    def to_dict(self) -> Dict[str, Any]:
        """Convert route to dictionary representation."""
        metrics = self.calculate_metrics()
        return {
            'id': self.id,
            'name': self.name,
            'source_segment_ids': self.source_segment_ids,
            'metrics': metrics.to_dict(),
            'metadata': self.metadata,
        }


class RouteAnalyzer:
    """
    Analyzes and ranks running routes by elevation metrics.

    Primary use case: Finding challenging training routes that match
    or exceed the elevation profile of target races (e.g., Canyons 50K).
    """

    def __init__(self, routes: Optional[List[Route]] = None):
        """
        Initialize the analyzer with routes.

        Args:
            routes: List of Route objects to analyze
        """
        self.routes = routes or []

    @classmethod
    def routes_from_segments(
        cls,
        segments: List[Dict[str, Any]],
        elevation_data_by_id: Optional[Dict[str, List[Dict]]] = None
    ) -> List[Route]:
        """
        Create Route objects from a list of Strava segments.

        Args:
            segments: List of segment dictionaries from Strava API
            elevation_data_by_id: Optional dict mapping segment IDs to elevation data

        Returns:
            List of Route objects
        """
        routes = []
        elevation_data_by_id = elevation_data_by_id or {}

        for segment in segments:
            segment_id = str(segment.get('id', ''))
            elevation_data = elevation_data_by_id.get(segment_id)
            route = Route.from_segment(segment, elevation_data)
            routes.append(route)

        return routes

    def add_route(self, route: Route) -> None:
        """Add a route to the analyzer."""
        self.routes.append(route)

    def add_routes(self, routes: List[Route]) -> None:
        """Add multiple routes to the analyzer."""
        self.routes.extend(routes)

    def rank_by_feet_per_mile(self, descending: bool = True) -> List[Route]:
        """
        Rank routes by feet gained per mile.

        Args:
            descending: If True, highest feet/mile first

        Returns:
            Sorted list of routes
        """
        return sorted(
            self.routes,
            key=lambda r: r.calculate_metrics().feet_per_mile,
            reverse=descending
        )

    def rank_by_total_gain(self, descending: bool = True) -> List[Route]:
        """
        Rank routes by total elevation gain.

        Args:
            descending: If True, highest gain first

        Returns:
            Sorted list of routes
        """
        return sorted(
            self.routes,
            key=lambda r: r.calculate_metrics().total_elevation_gain_feet,
            reverse=descending
        )

    def filter_routes(
        self,
        min_distance_miles: Optional[float] = None,
        max_distance_miles: Optional[float] = None,
        min_elevation_gain_feet: Optional[float] = None,
        max_elevation_gain_feet: Optional[float] = None,
        min_feet_per_mile: Optional[float] = None,
    ) -> List[Route]:
        """
        Filter routes based on criteria.

        Args:
            min_distance_miles: Minimum route distance
            max_distance_miles: Maximum route distance
            min_elevation_gain_feet: Minimum total elevation gain
            max_elevation_gain_feet: Maximum total elevation gain
            min_feet_per_mile: Minimum feet gained per mile

        Returns:
            Filtered list of routes
        """
        filtered = []

        for route in self.routes:
            metrics = route.calculate_metrics()

            if min_distance_miles is not None:
                if metrics.total_distance_miles < min_distance_miles:
                    continue

            if max_distance_miles is not None:
                if metrics.total_distance_miles > max_distance_miles:
                    continue

            if min_elevation_gain_feet is not None:
                if metrics.total_elevation_gain_feet < min_elevation_gain_feet:
                    continue

            if max_elevation_gain_feet is not None:
                if metrics.total_elevation_gain_feet > max_elevation_gain_feet:
                    continue

            if min_feet_per_mile is not None:
                if metrics.feet_per_mile < min_feet_per_mile:
                    continue

            filtered.append(route)

        return filtered

    def find_training_routes(
        self,
        target_feet_per_mile: float = 210.0,
        min_distance_miles: float = 3.0,
        max_distance_miles: Optional[float] = None,
    ) -> List[Route]:
        """
        Find routes suitable for training that meet or exceed target elevation ratio.

        Default target is based on Canyons 50K (~210 ft/mile).

        Args:
            target_feet_per_mile: Target feet gained per mile (default: 210)
            min_distance_miles: Minimum route distance for meaningful training
            max_distance_miles: Optional maximum distance

        Returns:
            List of routes that meet criteria, sorted by feet/mile descending
        """
        filtered = self.filter_routes(
            min_distance_miles=min_distance_miles,
            max_distance_miles=max_distance_miles,
            min_feet_per_mile=target_feet_per_mile,
        )

        return sorted(
            filtered,
            key=lambda r: r.calculate_metrics().feet_per_mile,
            reverse=True
        )

    @staticmethod
    def combine_routes(routes: List[Route], combined_name: str) -> Route:
        """
        Combine multiple routes/segments into a single longer route.

        Useful for planning training runs that chain multiple segments.

        Args:
            routes: List of routes to combine (in order)
            combined_name: Name for the combined route

        Returns:
            New combined Route
        """
        if not routes:
            raise ValueError("At least one route is required to combine")

        combined_profile = []
        cumulative_distance = 0.0
        all_segment_ids = []

        for route in routes:
            all_segment_ids.extend(route.source_segment_ids)

            # If route has elevation profile, use it
            if route.elevation_profile:
                for i, point in enumerate(route.elevation_profile):
                    if i == 0 and combined_profile:
                        # Calculate gap distance between routes
                        last_point = combined_profile[-1]
                        gap_dist = _haversine_distance(
                            last_point.latitude, last_point.longitude,
                            point.latitude, point.longitude
                        )
                        cumulative_distance += gap_dist

                    new_distance = cumulative_distance + point.distance_from_start_meters

                    new_point = ElevationPoint(
                        latitude=point.latitude,
                        longitude=point.longitude,
                        elevation_meters=point.elevation_meters,
                        distance_from_start_meters=new_distance
                    )
                    combined_profile.append(new_point)

                # Update cumulative distance for next route
                if route.elevation_profile:
                    cumulative_distance = combined_profile[-1].distance_from_start_meters

        combined_id = '_'.join(all_segment_ids[:5])  # Limit ID length
        if len(all_segment_ids) > 5:
            combined_id += f'_and_{len(all_segment_ids) - 5}_more'

        combined = Route(
            id=combined_id,
            name=combined_name,
            elevation_profile=combined_profile,
            source_segment_ids=all_segment_ids,
            metadata={
                'is_combined': True,
                'num_segments': len(routes),
            }
        )

        return combined

    def generate_report(
        self,
        top_n: Optional[int] = None,
        sort_by: str = 'feet_per_mile',
        include_benchmark: bool = True
    ) -> str:
        """
        Generate a summary report of routes.

        Args:
            top_n: Number of top routes to include (None for all)
            sort_by: Sort criteria ('feet_per_mile', 'total_gain', 'distance')
            include_benchmark: Include Canyons 50K benchmark comparison

        Returns:
            Formatted report string
        """
        if not self.routes:
            return "No routes to analyze."

        # Sort routes
        if sort_by == 'feet_per_mile':
            sorted_routes = self.rank_by_feet_per_mile()
        elif sort_by == 'total_gain':
            sorted_routes = self.rank_by_total_gain()
        elif sort_by == 'distance':
            sorted_routes = sorted(
                self.routes,
                key=lambda r: r.calculate_metrics().total_distance_miles,
                reverse=True
            )
        else:
            sorted_routes = self.routes

        if top_n:
            sorted_routes = sorted_routes[:top_n]

        # Build report
        lines = []
        lines.append("=" * 100)
        lines.append("ROUTE ANALYSIS REPORT")
        lines.append("=" * 100)
        lines.append("")

        if include_benchmark:
            lines.append("Benchmark: Canyons 50K = 6,500 ft / 31 mi = ~210 ft/mile")
            lines.append("Routes with >100% ratio are harder than Canyons 50K per mile")
            lines.append("")

        lines.append(
            f"{'Rank':<5} {'Name':<35} {'Distance':<10} {'Gain':<10} "
            f"{'Ft/Mile':<10} {'Max Grade':<10} {'vs C50K':<10}"
        )
        lines.append("-" * 100)

        for i, route in enumerate(sorted_routes, 1):
            metrics = route.calculate_metrics()
            name = route.name[:33] if len(route.name) > 33 else route.name

            c50k_pct = f"{metrics.canyons_50k_ratio * 100:.0f}%"

            lines.append(
                f"{i:<5} {name:<35} {metrics.total_distance_miles:>7.2f} mi "
                f"{metrics.total_elevation_gain_feet:>7.0f} ft "
                f"{metrics.feet_per_mile:>7.1f} ft/mi "
                f"{metrics.max_grade_percent:>7.1f}% "
                f"{c50k_pct:>8}"
            )

        lines.append("-" * 100)

        # Summary statistics
        all_metrics = [r.calculate_metrics() for r in sorted_routes]
        if all_metrics:
            avg_fpm = sum(m.feet_per_mile for m in all_metrics) / len(all_metrics)
            max_fpm = max(m.feet_per_mile for m in all_metrics)
            total_routes_above_benchmark = sum(
                1 for m in all_metrics if m.feet_per_mile >= 210
            )

            lines.append("")
            lines.append("SUMMARY:")
            lines.append(f"  Total routes analyzed: {len(sorted_routes)}")
            lines.append(f"  Average ft/mile: {avg_fpm:.1f}")
            lines.append(f"  Max ft/mile: {max_fpm:.1f}")
            lines.append(
                f"  Routes exceeding Canyons 50K ratio: "
                f"{total_routes_above_benchmark} ({total_routes_above_benchmark/len(sorted_routes)*100:.0f}%)"
            )

        lines.append("")
        lines.append("=" * 100)

        return "\n".join(lines)

    def export_to_json(self, filepath: Path) -> None:
        """
        Export route analysis to JSON file.

        Args:
            filepath: Path to save JSON file
        """
        data = {
            'routes': [route.to_dict() for route in self.routes],
            'summary': {
                'total_routes': len(self.routes),
                'benchmark_ft_per_mile': RouteMetrics.CANYONS_50K_FT_PER_MILE,
            }
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def export_rankings_to_csv(self, filepath: Path) -> None:
        """
        Export route rankings to CSV file.

        Args:
            filepath: Path to save CSV file
        """
        import csv

        sorted_routes = self.rank_by_feet_per_mile()

        fieldnames = [
            'rank', 'id', 'name', 'distance_miles', 'elevation_gain_feet',
            'elevation_loss_feet', 'feet_per_mile', 'max_grade_percent',
            'avg_grade_percent', 'canyons_50k_ratio'
        ]

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for rank, route in enumerate(sorted_routes, 1):
                metrics = route.calculate_metrics()
                writer.writerow({
                    'rank': rank,
                    'id': route.id,
                    'name': route.name,
                    'distance_miles': round(metrics.total_distance_miles, 2),
                    'elevation_gain_feet': round(metrics.total_elevation_gain_feet, 0),
                    'elevation_loss_feet': round(metrics.total_elevation_loss_feet, 0),
                    'feet_per_mile': round(metrics.feet_per_mile, 1),
                    'max_grade_percent': round(metrics.max_grade_percent, 1),
                    'avg_grade_percent': round(metrics.avg_grade_percent, 1),
                    'canyons_50k_ratio': round(metrics.canyons_50k_ratio, 2),
                })


def _haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.

    Args:
        lat1: Latitude of point 1
        lon1: Longitude of point 1
        lat2: Latitude of point 2
        lon2: Longitude of point 2

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) *
        math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return R * c


# Convenience functions for common operations

def analyze_segments(
    segments: List[Dict[str, Any]],
    elevation_data_by_id: Optional[Dict[str, List[Dict]]] = None,
    min_feet_per_mile: float = 210.0,
    min_distance_miles: float = 1.0,
    max_distance_miles: Optional[float] = None,
) -> Tuple[List[Route], str]:
    """
    Convenience function to analyze segments and generate a report.

    Args:
        segments: List of segment dictionaries from Strava API
        elevation_data_by_id: Optional elevation data keyed by segment ID
        min_feet_per_mile: Minimum feet/mile to include (default: Canyons 50K ratio)
        min_distance_miles: Minimum distance to include
        max_distance_miles: Maximum distance to include

    Returns:
        Tuple of (filtered routes, report string)
    """
    routes = RouteAnalyzer.routes_from_segments(segments, elevation_data_by_id)
    analyzer = RouteAnalyzer(routes)

    training_routes = analyzer.find_training_routes(
        target_feet_per_mile=min_feet_per_mile,
        min_distance_miles=min_distance_miles,
        max_distance_miles=max_distance_miles,
    )

    # Generate report for all routes but highlight training routes
    report = analyzer.generate_report(sort_by='feet_per_mile')

    return training_routes, report


def quick_rank(segments: List[Dict[str, Any]], top_n: int = 10) -> str:
    """
    Quick ranking of segments by feet per mile.

    Args:
        segments: List of segment dictionaries from Strava API
        top_n: Number of top routes to show

    Returns:
        Formatted report string
    """
    routes = RouteAnalyzer.routes_from_segments(segments)
    analyzer = RouteAnalyzer(routes)
    return analyzer.generate_report(top_n=top_n)
