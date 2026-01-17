"""Configuration management for Austin Trails"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# Create data directory if it doesn't exist
DATA_DIR.mkdir(exist_ok=True)

# Strava API Configuration
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

# Default location (Austin, TX)
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "30.2672"))
DEFAULT_LON = float(os.getenv("DEFAULT_LON", "-97.7431"))

# Query defaults
DEFAULT_MAX_DISTANCE = float(os.getenv("DEFAULT_MAX_DISTANCE", "10"))  # km
DEFAULT_MIN_ELEVATION = float(os.getenv("DEFAULT_MIN_ELEVATION", "50"))  # meters
DEFAULT_SEARCH_RADIUS = float(os.getenv("DEFAULT_SEARCH_RADIUS", "10"))  # km

# API Rate limiting
RATE_LIMIT_DELAY = 0.5  # seconds between requests
