# Setup Checklist - Get Austin Trails Running

Follow these steps in order to get the Strava elevation query tool working.

## ✅ Step-by-Step Setup

### 1. Install Python Dependencies

```bash
cd /home/user/austin_trails
pip install -r requirements.txt
```

**What this installs:**
- `stravalib` - Strava API client library
- `requests` - HTTP library for API calls
- `python-dotenv` - For loading environment variables from .env file

---

### 2. Get Your Strava API Credentials

#### 2a. Create a Strava API Application

1. Go to **https://www.strava.com/settings/api**
2. Log in to your Strava account
3. Click **"Create an App"** (or use existing app if you have one)
4. Fill out the form:
   - **Application Name**: `Austin Trails Query` (or any name)
   - **Category**: Choose "Data Importer" or "Visualizer"
   - **Club**: Leave blank
   - **Website**: `http://localhost` (if you don't have a website)
   - **Authorization Callback Domain**: `localhost`
5. Agree to terms and click **"Create"**

#### 2b. Copy Your Client ID and Secret

After creating the app, you'll see:
- **Client ID** - A number (e.g., `12345`)
- **Client Secret** - A long string of letters/numbers

**Write these down!** You'll need them in Step 3.

#### 2c. Get Your Access Token

**Quick Method (good for 6 hours):**
- On the same API settings page, you'll see "Your Access Token"
- Copy this token - it's valid for testing

**Long-term Method (recommended):**

1. Build this URL (replace `YOUR_CLIENT_ID` with your actual Client ID):
   ```
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all
   ```

2. Open that URL in your browser and click **"Authorize"**

3. You'll be redirected to a URL like:
   ```
   http://localhost/?state=&code=abc123def456...&scope=read,activity:read_all
   ```

4. Copy the `code` part (the long string after `code=`)

5. Exchange the code for tokens using this command (replace the placeholders):
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_CLIENT_ID \
     -d client_secret=YOUR_CLIENT_SECRET \
     -d code=THE_CODE_FROM_STEP_4 \
     -d grant_type=authorization_code
   ```

6. The response will look like:
   ```json
   {
     "access_token": "abc123...",
     "refresh_token": "def456...",
     "expires_at": 1234567890
   }
   ```

7. Save both the `access_token` and `refresh_token`

---

### 3. Create Your .env File and Add Credentials

**This is where you put your Strava credentials!**

```bash
# Copy the example file
cp .env.example .env
```

Now open the `.env` file in a text editor:

```bash
nano .env
# or
vim .env
# or use any text editor
```

**Replace the placeholder values with your actual credentials:**

```bash
# Strava API Credentials
STRAVA_CLIENT_ID=12345
STRAVA_CLIENT_SECRET=abc123def456ghi789
STRAVA_ACCESS_TOKEN=xyz789abc123def456
STRAVA_REFRESH_TOKEN=refresh123token456

# Default Search Location (Austin, TX) - you can change these
DEFAULT_LAT=30.2672
DEFAULT_LON=-97.7431

# Query Parameters - you can adjust these defaults
DEFAULT_MAX_DISTANCE=10  # kilometers
DEFAULT_MIN_ELEVATION=50  # meters
DEFAULT_SEARCH_RADIUS=10  # kilometers
```

**Save the file!**

**IMPORTANT:**
- The `.env` file is in your `.gitignore`, so it won't be committed to git
- Never share your credentials publicly
- If you accidentally commit credentials, regenerate them on Strava

---

### 4. Test the Installation

Run a simple test query:

```bash
python -m src.elevation_query --top 5
```

**Expected output:**
- Should show "✓ Connected to Strava API"
- Should find segments near Austin
- Should display a table with 5 segments
- Should create files in `data/segments.json` and `data/segments.csv`

**If you see errors:**
- "Access token not provided" → Check your `.env` file exists and has `STRAVA_ACCESS_TOKEN`
- "401 Unauthorized" → Your access token may be expired, get a new one
- "No module named..." → Run `pip install -r requirements.txt`

---

## 🎯 You're Done! Now What?

### Basic Usage Examples

**Find high-elevation segments near Austin:**
```bash
python -m src.elevation_query
```

**Find really challenging climbs (100m+, max 5km):**
```bash
python -m src.elevation_query --min-elevation 100 --max-distance 5
```

**Find running trails:**
```bash
python -m src.elevation_query --activity-type running --min-elevation 30
```

**Search near a different location (Mount Bonnell):**
```bash
python -m src.elevation_query --lat 30.3166 --lon -97.7714 --radius 5
```

**Get detailed information on top 10 segments:**
```bash
python -m src.elevation_query --get-details --top 10
```

### View Your Results

Results are saved in the `data/` directory:

```bash
# View CSV in terminal
cat data/segments.csv | column -t -s ','

# Open in Excel/Google Sheets
# Just open data/segments.csv

# View JSON
cat data/segments.json
```

---

## 📝 Quick Reference

| What | Where |
|------|-------|
| **Put credentials** | `.env` file in project root |
| **Get credentials** | https://www.strava.com/settings/api |
| **View results** | `data/segments.csv` or `data/segments.json` |
| **Main command** | `python -m src.elevation_query` |
| **Help** | `python -m src.elevation_query --help` |

---

## ❓ Troubleshooting

**"No such file or directory: .env"**
- You need to create it: `cp .env.example .env`
- Then edit it with your credentials

**"Access token not provided"**
- Make sure `.env` file exists in `/home/user/austin_trails/`
- Make sure `STRAVA_ACCESS_TOKEN=` has a value after the `=`
- No spaces around the `=`

**"No segments found"**
- Austin is relatively flat - try increasing search radius: `--radius 20`
- Lower minimum elevation: `--min-elevation 20`
- Try a different location with more hills

**"Rate limit exceeded"**
- Strava limits: 100 requests per 15 minutes, 1000 per day
- Wait 15 minutes and try again
- Use `--top 20` to limit results
- Avoid `--get-details` for large queries

---

## 🔒 Security Notes

- `.env` is in `.gitignore` - it won't be committed
- Never share your access token publicly
- If compromised, revoke and regenerate at https://www.strava.com/settings/api
- Access tokens expire - you may need to refresh them periodically

---

Happy climbing! 🚴‍♂️⛰️
