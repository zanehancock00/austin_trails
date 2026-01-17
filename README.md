# Austin Trails - Strava Elevation Query

A Python tool to discover high-elevation trails, segments, and routes in the Austin area using the Strava API. Includes both a **web interface** and command-line tools.

## 🌟 Two Ways to Use

### 1. Web App (Recommended) 🚀

Interactive web interface with real-time filtering and beautiful UI.

```bash
python app.py
# Open http://localhost:5000 in your browser
```

**Features:**
- Interactive filters for elevation, distance, and proximity to Cedar Park
- Sort by elevation gain, intensity, grade, or distance from home
- Click segments to view on Strava
- Responsive design for desktop and mobile
- Real-time filtering (no page reloads)

👉 **See [WEB_APP_GUIDE.md](WEB_APP_GUIDE.md) for detailed instructions**

### 2. Command Line Tool

Query segments from the terminal and export to CSV/JSON.

```bash
python -m src.elevation_query --min-elevation 100 --max-distance 5
```

## Features

- **Web Interface**: Beautiful, interactive segment browser with filters
- Query Strava segments and routes based on location coordinates
- Filter by elevation gain, distance, and proximity to Cedar Park
- Find challenging climbs that aren't too long
- Export results to JSON and CSV formats
- Distance calculations from your home location

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
├── app.py                 # Web application (Flask)
├── templates/
│   └── index.html        # Web UI
├── static/
│   ├── style.css         # Styling
│   └── app.js            # Frontend JavaScript
├── src/
│   ├── __init__.py
│   ├── strava_client.py  # Strava API integration
│   ├── elevation_query.py # Command-line query tool
│   └── utils.py          # Helper functions
├── data/                 # Output directory
├── config.py             # Configuration
├── .env.example         # Environment template
├── requirements.txt
├── README.md
├── WEB_APP_GUIDE.md     # Web app documentation
├── SETUP_CHECKLIST.md   # Setup instructions
└── QUICKSTART.md        # Quick start guide
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
