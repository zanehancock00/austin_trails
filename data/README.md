# Data Directory

This directory contains output files from Strava queries.

## Generated Files

When you run `python -m src.elevation_query`, the following files will be created:

- **segments.json**: Raw segment data from Strava API in JSON format
- **segments.csv**: Formatted CSV file with key metrics for easy analysis in Excel/Google Sheets

## File Format

### segments.csv columns:
- `id`: Unique Strava segment identifier
- `name`: Segment name
- `distance_km`: Segment length in kilometers
- `elevation_gain_m`: Total elevation gain in meters
- `avg_grade`: Average gradient (percentage)
- `elevation_per_km`: Elevation gain per kilometer (m/km) - useful metric for climb intensity
- `climb_category`: Strava's climb categorization (0-5)
- `climb_category_desc`: Description of climb category
- `city`, `state`: Location information
- `start_latitude`, `start_longitude`: GPS coordinates of segment start

## Example Usage

View results in terminal:
```bash
cat segments.csv | column -t -s ','
```

Count segments:
```bash
wc -l segments.csv
```

Find hardest climbs by grade:
```bash
sort -t',' -k5 -nr segments.csv | head -10
```

## Note

By default, `.gitignore` excludes JSON and CSV files from version control to avoid committing potentially large result sets. If you want to track specific results, you can force-add them:

```bash
git add -f data/segments.csv
```
