# Quick Start Guide

Get started with Austin Trails in 5 minutes!

## Step 1: Get Strava API Credentials

1. Go to https://www.strava.com/settings/api
2. Click "Create App" or use an existing app
3. Fill in the required fields:
   - **Application Name**: Austin Trails Query
   - **Category**: Data Importer
   - **Website**: http://localhost (or your website)
   - **Authorization Callback Domain**: localhost
4. Click "Create"
5. Note your **Client ID** and **Client Secret**

## Step 2: Get Your Access Token

You need an access token to make API requests. Here are two methods:

### Method A: Quick Token (For Testing)

1. After creating your app, you'll see an "Access Token" on the app page
2. Copy this token - it's valid for 6 hours
3. Use this for quick testing

### Method B: OAuth2 Flow (For Production)

For a longer-lasting token, you'll need to complete the OAuth2 flow:

1. Build the authorization URL:
   ```
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all
   ```

2. Open this URL in your browser and authorize the app

3. You'll be redirected to a URL like:
   ```
   http://localhost/?state=&code=AUTHORIZATION_CODE&scope=read,activity:read_all
   ```

4. Copy the `code` parameter

5. Exchange the code for a token:
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -F client_id=YOUR_CLIENT_ID \
     -F client_secret=YOUR_CLIENT_SECRET \
     -F code=AUTHORIZATION_CODE \
     -F grant_type=authorization_code
   ```

6. The response will include your `access_token` and `refresh_token`

## Step 3: Configure Environment

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   STRAVA_ACCESS_TOKEN=your_access_token
   STRAVA_REFRESH_TOKEN=your_refresh_token
   ```

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 5: Run Your First Query

Find high-elevation segments near Austin:

```bash
python -m src.elevation_query
```

This will search for segments with:
- Elevation gain ≥ 50 meters
- Distance ≤ 10 km
- Within 10 km of Austin city center

### Custom Queries

Find challenging climbs (100m+, max 5km):
```bash
python -m src.elevation_query --min-elevation 100 --max-distance 5
```

Find running trails:
```bash
python -m src.elevation_query --activity-type running --min-elevation 30
```

Search near a specific location (Mount Bonnell coordinates):
```bash
python -m src.elevation_query --lat 30.3166 --lon -97.7714 --radius 5
```

Get detailed segment information:
```bash
python -m src.elevation_query --get-details --top 10
```

## Understanding the Output

The script will create two files in the `data/` directory:

1. **segments.json**: Complete segment data in JSON format
2. **segments.csv**: Formatted spreadsheet with key metrics

### CSV Columns

- `id`: Strava segment ID
- `name`: Segment name
- `distance_km`: Length in kilometers
- `elevation_gain_m`: Total elevation gain in meters
- `avg_grade`: Average gradient percentage
- `elevation_per_km`: Meters of elevation gain per kilometer
- `climb_category`: Strava climb category (0-5, with 5 being hardest)
- `city`, `state`: Location information
- `start_latitude`, `start_longitude`: Segment start coordinates

## Tips

1. **Start Small**: Begin with default parameters and adjust based on results
2. **Rate Limits**: Strava limits to 100 requests per 15 minutes
3. **Use --top**: Limit results to avoid hitting rate limits: `--top 20`
4. **Get Details**: Use `--get-details` only when needed (slower)
5. **View on Strava**: Visit `https://www.strava.com/segments/{segment_id}` to see segment on map

## Troubleshooting

### "Access token not provided"
- Make sure `.env` file exists and contains `STRAVA_ACCESS_TOKEN`

### "No segments found"
- Increase search radius: `--radius 20`
- Lower minimum elevation: `--min-elevation 20`
- Check if location has segments (try a different city)

### Rate limit errors
- Wait 15 minutes between large queries
- Use `--top` to limit results
- Avoid `--get-details` for large result sets

## Next Steps

- Modify query parameters to find your perfect climbs
- Export results to CSV for analysis
- Build custom filters using the Python API
- Combine with other data sources (weather, traffic, etc.)

Happy climbing! 🚴‍♂️⛰️
