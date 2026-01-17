"""Strava API client for querying segments and routes"""

import time
import requests
from typing import List, Dict, Optional
from stravalib.client import Client
import config


class StravaClient:
    """Client for interacting with Strava API"""

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Strava client

        Args:
            access_token: Strava API access token. If not provided, uses config.
        """
        self.access_token = access_token or config.STRAVA_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError(
                "Strava access token not provided. "
                "Set STRAVA_ACCESS_TOKEN in .env file or pass to constructor."
            )

        self.client = Client(access_token=self.access_token)
        self.base_url = "https://www.strava.com/api/v3"

    def explore_segments(
        self,
        lat: float,
        lon: float,
        activity_type: str = "riding",
        min_cat: int = 0,
        max_cat: int = 5
    ) -> List[Dict]:
        """
        Explore segments near a location

        Args:
            lat: Latitude
            lon: Longitude
            activity_type: Type of activity ('riding' or 'running')
            min_cat: Minimum climb category (0-5)
            max_cat: Maximum climb category (0-5)

        Returns:
            List of segment dictionaries
        """
        try:
            # Use stravalib's segment explore endpoint
            segments = self.client.explore_segments(
                bounds=[lat - 0.1, lon - 0.1, lat + 0.1, lon + 0.1],
                activity_type=activity_type,
                min_cat=min_cat,
                max_cat=max_cat
            )

            # Convert to list of dicts
            segment_list = []
            for seg in segments:
                segment_list.append({
                    'id': seg.id,
                    'name': seg.name,
                    'climb_category': seg.climb_category,
                    'climb_category_desc': seg.climb_category_desc,
                    'avg_grade': seg.avg_grade,
                    'distance': seg.distance,  # in meters
                    'elev_difference': seg.elev_difference,  # in meters
                    'start_latlng': seg.start_latlng,
                    'end_latlng': seg.end_latlng,
                    'points': seg.points if hasattr(seg, 'points') else None
                })

            return segment_list

        except Exception as e:
            print(f"Error exploring segments: {e}")
            return []

    def get_segment_details(self, segment_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific segment

        Args:
            segment_id: Strava segment ID

        Returns:
            Dictionary with segment details
        """
        try:
            time.sleep(config.RATE_LIMIT_DELAY)
            segment = self.client.get_segment(segment_id)

            return {
                'id': segment.id,
                'name': segment.name,
                'activity_type': segment.activity_type,
                'distance': float(segment.distance),  # meters
                'average_grade': float(segment.average_grade),  # percentage
                'maximum_grade': float(segment.maximum_grade),  # percentage
                'elevation_high': float(segment.elevation_high),  # meters
                'elevation_low': float(segment.elevation_low),  # meters
                'total_elevation_gain': float(segment.total_elevation_gain),  # meters
                'climb_category': segment.climb_category,
                'climb_category_desc': segment.climb_category_desc,
                'city': segment.city,
                'state': segment.state,
                'country': segment.country,
                'start_latitude': segment.start_latitude,
                'start_longitude': segment.start_longitude,
                'end_latitude': segment.end_latitude,
                'end_longitude': segment.end_longitude,
                'effort_count': segment.effort_count,
                'athlete_count': segment.athlete_count,
                'star_count': segment.star_count,
            }
        except Exception as e:
            print(f"Error getting segment {segment_id}: {e}")
            return None

    def search_segments_by_bounds(
        self,
        sw_lat: float,
        sw_lon: float,
        ne_lat: float,
        ne_lon: float,
        activity_type: str = "riding"
    ) -> List[Dict]:
        """
        Search for segments within geographic bounds

        Args:
            sw_lat: Southwest latitude
            sw_lon: Southwest longitude
            ne_lat: Northeast latitude
            ne_lon: Northeast longitude
            activity_type: 'riding' or 'running'

        Returns:
            List of segments
        """
        try:
            time.sleep(config.RATE_LIMIT_DELAY)

            # Using the segment explore endpoint with bounds
            url = f"{self.base_url}/segments/explore"
            params = {
                'bounds': f"{sw_lat},{sw_lon},{ne_lat},{ne_lon}",
                'activity_type': activity_type
            }
            headers = {'Authorization': f'Bearer {self.access_token}'}

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            return data.get('segments', [])

        except Exception as e:
            print(f"Error searching segments: {e}")
            return []

    def get_athlete_routes(self, athlete_id: Optional[int] = None) -> List[Dict]:
        """
        Get routes for an athlete

        Args:
            athlete_id: Athlete ID (if None, uses authenticated athlete)

        Returns:
            List of route dictionaries
        """
        try:
            time.sleep(config.RATE_LIMIT_DELAY)

            if athlete_id is None:
                athlete = self.client.get_athlete()
                athlete_id = athlete.id

            routes = self.client.get_routes(athlete_id)

            route_list = []
            for route in routes:
                route_list.append({
                    'id': route.id,
                    'name': route.name,
                    'description': route.description,
                    'distance': float(route.distance),  # meters
                    'elevation_gain': float(route.elevation_gain),  # meters
                    'type': route.type,
                    'sub_type': route.sub_type,
                    'private': route.private,
                    'starred': route.starred,
                    'timestamp': route.timestamp
                })

            return route_list

        except Exception as e:
            print(f"Error getting routes: {e}")
            return []
