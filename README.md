# Austin Trails - Strava Elevation Query

A Python tool to discover high-elevation trails, segments, and routes in the Austin area using the Strava API.

## Features

- Query Strava segments and routes based on location coordinates
- Filter by elevation gain and distance
- Find challenging climbs that aren't too long
- Export results to JSON and CSV formats

## Prerequisites

- Python 3.8+
- Strava API account and credentials

## Setup

1. **Get Strava API Credentials**
   - Go to https://www.strava.com/settings/api
   - Create an application
   - Note your `Client ID` and `Client Secret`
   - Get your access token (you can use the initial token or implement OAuth2 flow)

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your Strava API credentials
   ```

## Usage

### Basic Query

Query segments near Austin with high elevation gain:

```bash
python -m src.elevation_query
```

### Custom Query

```bash
python -m src.elevation_query \
  --lat 30.2672 \
  --lon -97.7431 \
  --max-distance 10 \
  --min-elevation 100 \
  --radius 10
```

### Parameters

- `--lat`: Latitude (default: 30.2672 for Austin, TX)
- `--lon`: Longitude (default: -97.7431 for Austin, TX)
- `--max-distance`: Maximum segment distance in kilometers (default: 10)
- `--min-elevation`: Minimum elevation gain in meters (default: 50)
- `--radius`: Search radius in kilometers (default: 10)

## Output

Results are saved to the `data/` directory:
- `segments.json`: Raw segment data from Strava
- `segments.csv`: Formatted CSV with key metrics
- `routes.json`: Route data (if queried)

## Project Structure

```
austin_trails/
├── src/
│   ├── __init__.py
│   ├── strava_client.py    # Strava API integration
│   ├── elevation_query.py  # Main query script
│   └── utils.py            # Helper functions
├── data/                   # Output directory
├── .env.example           # Environment template
├── .gitignore
├── requirements.txt
└── README.md
```

## API Rate Limits

Strava API has rate limits:
- 100 requests per 15 minutes
- 1,000 requests per day

This tool implements automatic rate limiting and backoff.

## Contributing

Feel free to submit issues or pull requests to improve the functionality.

## License

MIT License
