# BottosCon Personal Schedule Viewer

A Flask web application that solves the concurrent viewing problem for board game convention schedules stored in Google Sheets.

## CAUTION
<em>All the code and documentation for at least the first version of this app was written by Claude.ai based on prompts from Harvey Dueck.
Claude is a great coding tool, but it has a tendency to overstate things, e.g. claiming that untested code is complete and that minimal tests are "comprehensive".  Take all such value judgements with a large grain of salt.
</em>
## Purpose

The convention uses a shared Google Sheet for personal schedules with a dropdown in cell B1 to select which player's schedule to display. This means only one person can view their schedule at a time - if someone else changes the dropdown, everyone's view changes.

This app allows **all players to view their personal schedules concurrently** without conflicts.

## Features

- **Personal Schedule View**: Each player gets a unique URL to view only their games
- **Searchable Player List**: Home page with search to quickly find any player
- **All Games View**: See the complete convention schedule
- **Auto-refresh**: Data refreshes from the Google Sheet every hour
- **Manual Update**: "Update Schedule" button with tooltip to force immediate refresh
- **Mobile-friendly**: Responsive design works on phones and tablets
- **Printable**: Print button for physical schedule copies
- **No Authentication Required**: Uses public Google Sheets CSV export

## Architecture

```
Google Sheets (Signup Form)
        ↓ (CSV export URL)
Flask App (Cloud Run)
        ↓
Player Views (concurrent access)
```

## Quick Start - Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run locally**:
   ```bash
   python app.py
   ```

3. **Open browser**:
   - Navigate to `http://localhost:8080`
   - Search for your name and click to see your schedule

## Deployment to Google Cloud Run

### Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed ([install guide](https://cloud.google.com/sdk/docs/install))
- Docker installed (optional, Cloud Run can build for you)

### Option 1: Deploy with Cloud Build (Easiest)

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs (first time only)
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy (Cloud Build will build the container for you)
gcloud run deploy bottoscon-scheduler \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300

# The command will output your service URL when complete
```

### Option 2: Build and Deploy with Docker

```bash
# Build the container
docker build -t gcr.io/$PROJECT_ID/bottoscon-scheduler .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/bottoscon-scheduler

# Deploy to Cloud Run
gcloud run deploy bottoscon-scheduler \
  --image gcr.io/$PROJECT_ID/bottoscon-scheduler \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1
```

### Post-Deployment

After deployment, you'll get a URL like:
```
https://bottoscon-scheduler-xxxxx-uc.a.run.app
```

Share this URL with convention attendees!

## Configuration

### Changing the Google Sheet Source

Edit `app.py` and update the `SIGNUP_SHEET_URL` constant:

```python
SIGNUP_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=YOUR_GID"
```

**Important**: The Google Sheet must be publicly accessible (anyone with the link can view).

To get the correct URL:
1. Open your Google Sheet
2. Note the sheet ID from the URL: `https://docs.google.com/spreadsheets/d/SHEET_ID/edit#gid=GID`
3. Replace in the export URL format above

### Adjusting Cache Duration

By default, the app caches data for 1 hour to reduce Google Sheets API calls. Users can manually refresh using the "Update Schedule" button on any page. To change the cache duration:

```python
CACHE_DURATION = 3600  # seconds (3600 = 1 hour)
```

## Cost Estimate

Google Cloud Run pricing (as of 2024):
- **Free tier**: 2 million requests/month, 360,000 GB-seconds of memory
- **Expected cost for convention**: $0 - $2 (well within free tier for <200 players)
- Billing is per-request and only when the service is being used

## Troubleshooting

### "Access denied" errors

**Problem**: App can't fetch data from Google Sheets

**Solutions**:
1. Verify the Google Sheet is set to "Anyone with the link can view"
2. Make sure you're using the CSV export URL format (not the regular sheet URL)
3. Test the export URL in your browser - it should download a CSV file

### Players not showing up

**Problem**: Some players are missing from the list

**Possible causes**:
1. Player name is in a column beyond the expected range (columns 23-31)
2. Player cell contains only "N/A" or is empty
3. Sheet structure has changed

**Debug**: Check the `parse_games_and_players()` function in `app.py`

### Slow loading

**Problem**: App takes a long time to load

**Solutions**:
1. Increase Cloud Run memory allocation: `--memory 1Gi`
2. First request after idle period will be slower (cold start) - this is normal
3. Consider reducing cache duration if you need more frequent updates

## Customization

### Styling

Edit the CSS in the `<style>` blocks in:
- `templates/base.html` - Overall theme
- `templates/index.html` - Player list page
- `templates/schedule.html` - Individual schedules
- `templates/all_games.html` - All games view

### Adding Features

Some ideas for enhancements:
- **QR codes**: Generate QR code for each player's schedule URL
- **iCal export**: Allow players to add games to their calendar
- **Filtering**: Filter by game type, day, or time
- **Notifications**: Email/SMS when games are added to schedule
- **Game search**: Search for specific games by name

## Project Structure

```
bottoscon/
├── app.py                 # Flask application and logic
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── .dockerignore         # Files to exclude from container
├── README.md             # This file
└── templates/
    ├── base.html         # Base template with common layout
    ├── index.html        # Home page - player list
    ├── schedule.html     # Individual player schedule
    └── all_games.html    # All games view
```

## Development Notes

### How It Works

1. App fetches CSV data from Google Sheets export URL
2. Parses CSV to extract games and player signups (columns 23-31)
3. Builds an index of which games each player is in
4. Serves personalized views via Flask routes
5. Caches data for 1 hour to avoid hitting Google too frequently
6. Users can force refresh via "Update Schedule" button at any time

### Data Flow

```
Google Sheet → CSV Export → Flask Parser → Player Index → Web Views
                  ↓                              ↑
              Cache (1 hour)          Manual Refresh Button
```

### Player Name Extraction

The app handles player entries in these formats:
- `John Doe` → `John Doe`
- `John Doe <john@example.com>` → `John Doe`
- `N/A` → (ignored)
- Empty cell → (ignored)

## Contributing

This is a single-purpose tool built for BottosCon, but feel free to:
- Fork for your own convention
- Submit issues if you find bugs
- Suggest improvements via pull requests

## License

MIT License - feel free to use and modify for your own conventions!

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the Google Sheets CSV export URL format
3. Verify the sheet is publicly accessible
4. Check Cloud Run logs: `gcloud run logs read bottoscon-scheduler --limit 50`

## Acknowledgments

Built to solve a real problem at BottosCon board game convention. Thanks to the organizers for using Google Sheets in a creative way - this app just makes it work better for everyone!
