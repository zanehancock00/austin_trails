# Austin Trails Web App Guide

A beautiful web interface to browse and filter Strava segments near Cedar Park, TX.

## Features

- **Interactive Filtering**: Adjust elevation range, distance, and proximity to Cedar Park in real-time
- **Multiple Sort Options**: Sort by elevation gain, distance, intensity, grade, or proximity
- **Distance from Cedar Park**: See how far each segment is from your location
- **Click to View**: Click any segment to open it on Strava.com
- **Responsive Design**: Works great on desktop and mobile

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Credentials

Make sure you have your `.env` file configured with Strava credentials:

```bash
cp .env.example .env
# Edit .env and add your Strava credentials
```

### 3. Run the Web App

```bash
python app.py
```

### 4. Open in Browser

Open your browser to: **http://localhost:5000**

You should see the Austin Trails Explorer interface!

## Using the Web App

### Filter Options

- **Min/Max Elevation**: Set the elevation gain range (in meters)
  - Example: 50-200m for moderate climbs
  - Example: 100-300m for challenging climbs

- **Min/Max Distance**: Set the segment length range (in kilometers)
  - Example: 0-5km for short, intense climbs
  - Example: 5-15km for longer rides

- **Max Distance from Cedar Park**: How far from Cedar Park to search (in kilometers)
  - Example: 10km for nearby segments
  - Example: 30km for wider area

- **Sort By**: Choose how to order results
  - **Elevation Gain**: Highest climbs first (default)
  - **Distance**: Longest segments first
  - **Intensity (m/km)**: Steepest average gradient first
  - **Average Grade**: Highest grade percentage first
  - **Distance from Cedar Park**: Closest segments first

### Understanding the Results

Each segment card shows:

- **Segment Name**: The name on Strava
- **Category**: Strava's climb categorization (HC, 1-5)
- **Elevation Gain**: Total meters of climbing
- **Distance**: Segment length in kilometers
- **Average Grade**: Overall steepness percentage
- **Intensity**: Meters of elevation per kilometer (m/km)
- **From Cedar Park**: Distance from Cedar Park in kilometers
- **Location**: City and state
- **View on Strava**: Click to open segment on Strava.com

### Color Indicators

- **Purple highlight**: High elevation or intensity
- **Orange/Yellow**: Very steep grade (8%+)

## Customization

### Change Default Location

Edit `app.py` and modify:

```python
# Cedar Park, TX coordinates
CEDAR_PARK_LAT = 30.5052
CEDAR_PARK_LON = -97.8203
```

Change these to your preferred coordinates.

### Adjust Search Radius

In `app.py`, find:

```python
radius = 25  # km - wider search radius
```

Increase for more segments, decrease for local segments only.

### Modify Default Filters

Edit `templates/index.html` to change default filter values:

```html
<input type="number" id="minElevation" value="30" min="0" step="10">
<input type="number" id="maxElevation" value="300" min="0" step="10">
```

## Troubleshooting

### "No segments available"

1. Check that your `.env` file has valid Strava credentials
2. Make sure your access token hasn't expired
3. Click "Refresh from Strava" button

### Slow Loading

- The first load fetches data from Strava (can take 10-30 seconds)
- After that, data is cached for faster filtering
- Click "Refresh from Strava" to get latest data

### Port 5000 Already in Use

Change the port in `app.py`:

```python
app.run(debug=True, host='0.0.0.0', port=5001)  # Use port 5001 instead
```

Then open `http://localhost:5001`

### Proxy/Network Errors

If running in a restricted environment (like Claude Code), you'll need to run this on your local computer where you can access Strava's API directly.

## Tips

1. **Start with defaults**: The default filters (30-300m elevation, 0-15km distance) work well for finding interesting climbs

2. **Find training climbs**: Set filters to 3-7km distance and 75-150m elevation for ideal training segments

3. **Discover local gems**: Set "Max Distance from Cedar Park" to 10km and sort by "Elevation Gain"

4. **Challenge yourself**: Sort by "Intensity (m/km)" to find the steepest climbs

5. **Plan routes**: Use "Distance from Cedar Park" sort to plan rides by proximity

## Architecture

```
app.py                  - Flask backend with API endpoints
templates/index.html    - HTML user interface
static/style.css        - Styling and responsive design
static/app.js          - JavaScript for filters and interactivity
src/strava_client.py   - Strava API integration
src/utils.py           - Helper functions
config.py              - Configuration and environment variables
```

## API Endpoints

### GET /api/segments

Returns filtered segments based on query parameters.

**Parameters:**
- `min_elevation` - Minimum elevation gain (meters)
- `max_elevation` - Maximum elevation gain (meters)
- `min_distance` - Minimum distance (km)
- `max_distance` - Maximum distance (km)
- `max_distance_from_cedar` - Maximum distance from Cedar Park (km)
- `sort_by` - Sort field (elevation, distance, elevation_per_km, grade, distance_from_cedar)

**Response:**
```json
{
  "segments": [...],
  "total": 42,
  "cedar_park_location": {"lat": 30.5052, "lon": -97.8203}
}
```

### GET /api/stats

Returns statistics about available segments.

### GET /api/refresh

Clears cache and re-fetches data from Strava.

## Performance

- Initial load: 10-30 seconds (fetches from Strava)
- Filtering: Instant (uses cached data)
- Typical dataset: 100-300 segments in Austin area

## Security Notes

- Never commit `.env` file with credentials
- Web app runs on localhost by default
- To make accessible on network, update `host='0.0.0.0'` in app.py

---

Happy exploring! 🚴‍♂️⛰️
