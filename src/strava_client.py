"""Strava API client for querying segments and routes"""

import time
import requests
import certifi
from typing import List, Dict, Optional
from stravalib.client import Client
import config


# Create a requests session with proper SSL certificates
def get_session():
    """Get a requests session configured with proper SSL certificates"""
    session = requests.Session()
    session.verify = certifi.where()
    return session


# Global token storage (persists across requests within the same process)
_token_cache = {
    'access_token': None,
    'refresh_token': None,
    'expires_at': 0
}


class StravaClient:
    """Client for interacting with Strava API"""

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Strava client with automatic token refresh

        Args:
            access_token: Strava API access token. If not provided, uses config.
        """
        global _token_cache

        # Initialize from cache or config
        if _token_cache['access_token'] and _token_cache['expires_at'] > time.time():
            self.access_token = _token_cache['access_token']
            self.refresh_token = _token_cache['refresh_token']
            self.expires_at = _token_cache['expires_at']
        else:
            self.access_token = access_token or config.STRAVA_ACCESS_TOKEN
            self.refresh_token = config.STRAVA_REFRESH_TOKEN
            self.expires_at = 0  # Assume expired, will refresh on first use

        if not self.access_token:
            raise ValueError(
                "Strava access token not provided. "
                "Set STRAVA_ACCESS_TOKEN in .env file or pass to constructor."
            )

        # Ensure token is valid before proceeding
        self._ensure_valid_token()

        self.client = Client(access_token=self.access_token)
        self.base_url = "https://www.strava.com/api/v3"

    def _ensure_valid_token(self):
        """Check if token is expired and refresh if needed"""
        # Add 60 second buffer to avoid edge cases
        if self.expires_at > 0 and time.time() < (self.expires_at - 60):
            return  # Token still valid

        # Try to refresh the token
        if self.refresh_token and config.STRAVA_CLIENT_ID and config.STRAVA_CLIENT_SECRET:
            self._refresh_access_token()

    def _refresh_access_token(self):
        """Refresh the access token using the refresh token"""
        global _token_cache

        print("Refreshing Strava access token...")

        try:
            response = requests.post(
                'https://www.strava.com/oauth/token',
                data={
                    'client_id': config.STRAVA_CLIENT_ID,
                    'client_secret': config.STRAVA_CLIENT_SECRET,
                    'grant_type': 'refresh_token',
                    'refresh_token': self.refresh_token
                },
                verify=certifi.where()
            )
            response.raise_for_status()
            token_data = response.json()

            # Update instance variables
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            self.expires_at = token_data['expires_at']

            # Update global cache
            _token_cache['access_token'] = self.access_token
            _token_cache['refresh_token'] = self.refresh_token
            _token_cache['expires_at'] = self.expires_at

            # Update the stravalib client if it exists
            if hasattr(self, 'client'):
                self.client = Client(access_token=self.access_token)

            print(f"Token refreshed successfully. Expires at: {time.ctime(self.expires_at)}")

        except requests.exceptions.RequestException as e:
            print(f"Failed to refresh token: {e}")
            raise ValueError(
                f"Failed to refresh Strava access token: {e}. "
                "Check your STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and STRAVA_REFRESH_TOKEN."
            )

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
        self._ensure_valid_token()
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
            Dictionary with segment details, or dict with 'error' key if failed
        """
        self._ensure_valid_token()
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
            import traceback
            error_msg = str(e)
            print(f"Error getting segment {segment_id}: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")

            # Provide more specific error messages
            if '404' in error_msg or 'not found' in error_msg.lower():
                error_msg = 'Segment not found or no longer available'
            elif '403' in error_msg or 'forbidden' in error_msg.lower():
                error_msg = 'Segment is private or access is restricted'
            elif '401' in error_msg or 'unauthorized' in error_msg.lower():
                error_msg = 'Authentication error - please refresh your Strava token'
            elif 'rate limit' in error_msg.lower():
                error_msg = 'Strava API rate limit exceeded - please try again later'

            # Return error info instead of None for better debugging
            return {'error': error_msg, 'segment_id': segment_id}

    def search_segments_by_bounds(
        self,
        sw_lat: float,
        sw_lon: float,
        ne_lat: float,
        ne_lon: float,
        activity_type: str = "riding"
    ) -> List[Dict]:
        """
        Search for segments within geographic bounds using multiple overlapping queries
        to get more than the API's 10 segment limit per query

        Args:
            sw_lat: Southwest latitude
            sw_lon: Southwest longitude
            ne_lat: Northeast latitude
            ne_lon: Northeast longitude
            activity_type: 'riding' or 'running'

        Returns:
            List of segments
        """
        self._ensure_valid_token()
        try:
            all_segments = []
            seen_ids = set()

            # Strava's explore endpoint only returns ~10 segments per query
            # So we'll divide the area into a grid and query each cell
            # Using 5x5 grid (25 queries) - balance between coverage and speed
            grid_size = 5  # 5x5 grid = 25 queries
            lat_step = (ne_lat - sw_lat) / grid_size
            lon_step = (ne_lon - sw_lon) / grid_size

            print(f"Searching {grid_size}x{grid_size} grid for more segments...")

            for i in range(grid_size):
                for j in range(grid_size):
                    cell_sw_lat = sw_lat + (i * lat_step)
                    cell_sw_lon = sw_lon + (j * lon_step)
                    cell_ne_lat = sw_lat + ((i + 1) * lat_step)
                    cell_ne_lon = sw_lon + ((j + 1) * lon_step)

                    time.sleep(config.RATE_LIMIT_DELAY)

                    url = f"{self.base_url}/segments/explore"
                    params = {
                        'bounds': f"{cell_sw_lat},{cell_sw_lon},{cell_ne_lat},{cell_ne_lon}",
                        'activity_type': activity_type
                    }
                    headers = {'Authorization': f'Bearer {self.access_token}'}

                    try:
                        response = requests.get(url, params=params, headers=headers, verify=certifi.where())
                        response.raise_for_status()
                        data = response.json()
                        segments = data.get('segments', [])

                        # Deduplicate based on segment ID
                        for seg in segments:
                            if seg['id'] not in seen_ids:
                                seen_ids.add(seg['id'])
                                all_segments.append(seg)

                        print(f"  Grid cell ({i},{j}): {len(segments)} segments (total unique: {len(all_segments)})")

                    except Exception as e:
                        print(f"  Error in grid cell ({i},{j}): {e}")
                        continue

            return all_segments

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
        self._ensure_valid_token()
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
