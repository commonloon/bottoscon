# BottosCon App - Specification Document

**Updated by Claude AI at 2025-11-05 15:45:00**

This document describes the current features, architecture, and implementation details of the BottosCon schedule viewer application.

## 1. Overview

BottosCon is a Flask web application that displays game signup information and schedules from a Google Sheets signup form. It provides convention attendees with multiple views of the same game scheduling data to help them plan their day.

**Purpose**: Help convention participants find their games, see schedules, and navigate the event.

**Data Source**: Google Sheets signup form (live CSV export)

**Deployment**: Google Cloud Run (containerized Flask app)

---

## 2. Core Features

### 2.1 Home Page (`/`)

**Purpose**: Browse all players at the convention

**Display**:
- Alphabetically sorted list of all unique player names
- Count of total players
- Each player name is clickable

**User Action**: Click a player name to view their schedule

**Data**: Extracted from game player slots across all games

---

### 2.2 Player Schedule - List View (`/schedule/<player_name>`)

**Purpose**: View a specific player's games in chronological list format

**Display**:
- Player name in header
- Count of games scheduled for this player
- Games listed chronologically (Thursday ’ Sunday, then by start time)
- For each game:
  - Game ID and name
  - Start time and end time
  - Duration
  - Table location
  - Game status (FULL or OPEN)
  - List of all players in the game

**Data**: All games where the player name appears in the player slots

---

### 2.3 Player Schedule - Calendar View (`/calendar/<player_name>`)

**Purpose**: View a specific player's games in calendar format

**Display**:
- 4-day calendar view (Thursday through Sunday)
- FullCalendar library rendering games as time-blocked events
- Color-coded by status:
  - Green: OPEN (has available spots)
  - Red: FULL (no available spots)
- For each game event:
  - Game title
  - Time range
  - Table location
- Time grid showing 9 AM to midnight

**Printing**: Landscape layout optimized for printing player schedules

---

### 2.4 All Games - List View (`/all-games`)

**Purpose**: Browse all games at the convention

**Display**:
- Total game count badge
- Games grouped by day (Thursday, Friday, Saturday, Sunday)
- For each game:
  - Game ID and name
  - Start time and end time
  - Duration
  - Table location
  - Status badge (FULL/OPEN)
  - Player count and player names

---

### 2.5 All Games - Calendar View (`/calendar/all-games`)

**Purpose**: View all games in calendar format with day-by-day navigation

**Display**:
- Day selection tabs (Thursday, Friday, Saturday, Sunday)
- 1-day time grid view (selected day only)
- FullCalendar showing all games for that day
- Color-coded by status (green for OPEN, red for FULL)
- Game details on hover
- Time grid showing 9 AM to midnight

**Printing**: Portrait layout optimized for printing full schedule

---

### 2.6 Cache Refresh API (`/api/refresh-cache`)

**Purpose**: Force refresh data from Google Sheets (bypass 1-hour cache)

**Method**: POST

**Response**: JSON with success/error message

**Use Case**: Admin/organizer needs to reload updated signup data

---

## 3. Data Model

### 3.1 Game Object

```python
game = {
    'id': '167',                           # String: Game ID from column 0
    'name': 'New Cold War',                # String: Game name from column 1
    'status': 'FULL',                      # String: FULL or OPEN or OPEN - BELOW MIN PLAYERS
    'start_day': 'Friday',                 # String: Thursday, Friday, Saturday, Sunday
    'start_time': '09:00:00',              # String: HH:MM or HH:MM:SS format
    'end_day': 'Friday',                   # String: Convention day
    'end_time': '13:00',                   # String: HH:MM or HH:MM:SS format
    'duration': '04:00',                   # String: HH:MM format
    'table': 'H23',                        # String: Table/room location
    'players': [                           # List: Player names
        'Grant Linneberg',
        'Oleg Savelyev',
        'Benjamin Suan',
        'Geoff Conn'
    ]
}
```

### 3.2 Player-Game Mapping

```python
player_games = {
    'Grant Linneberg': [game1, game2, ...],    # All games for this player
    'Oleg Savelyev': [game1, game3, ...],
    ...
}
```

---

## 4. Routes and Endpoints

| Route | Method | Purpose | Returns |
|-------|--------|---------|---------|
| `/` | GET | Home page with player list | HTML page |
| `/all-games` | GET | All games in list view | HTML page |
| `/calendar/all-games` | GET | All games in calendar view | HTML page |
| `/schedule/<player_name>` | GET | Player's games in list view | HTML page or 404 |
| `/calendar/<player_name>` | GET | Player's games in calendar view | HTML page or 404 |
| `/api/refresh-cache` | POST | Force cache refresh | JSON response |

---

## 5. Data Source and Processing

### 5.1 Google Sheets CSV Export

**Source URL**:
```
https://docs.google.com/spreadsheets/d/1GZX_Nxs-eWcV9JRYwVO4jH8jEnMJvGDlwKevCtyAkjg/export?format=csv&gid=1882561680
```

**Format**: CSV exported from Google Sheets signup form

### 5.2 Column Mapping

| Column Index | Field | Source |
|--------------|-------|--------|
| 0 | Game ID | First column in form |
| 1 | Game Name | Game name field |
| 2 | Status | Status field |
| 11 | Start Day | Day selection |
| 12 | Start Time | Start time (24-hour) |
| 13 | End Day | End day selection |
| 14 | End Time | End time |
| 19 | Duration | Calculated or provided |
| 20 | Table | Table/room location |
| 23-31 | Player Slots | Player name entries (8 slots) |

### 5.3 Data Processing Pipeline

```
Google Sheets CSV
       “
fetch_sheet_data()
  - HTTP request to CSV export URL
  - Parse with csv.reader()
  - Cache for 1 hour
       “
parse_games_and_players()
  - Skip first 2 header rows
  - For each row:
    - Skip if < 23 columns
    - Skip if no Game ID
    - Extract game fields from column indices
    - Extract players from columns 23-31
    - Clean player names (remove emails)
  - Build player_games index
       “
sort_games_chronologically()
  - Sort by: Day (Thu’Fri’Sat’Sun), Hour, Minute
       “
Render templates with data
```

### 5.4 Data Filtering Rules

Games are **included** if they have:
-  At least 23 columns in CSV row
-  Non-empty Game ID (column 0)
-  Non-empty Game Name (column 1)

Games are **excluded** if they have:
-  Less than 23 columns
-  Empty Game ID
-  Empty Game Name

### 5.5 Player Name Extraction

Player names are extracted from columns 23-31 with cleaning:
- Remove email addresses: `Rob Bottos <email@example.com>` ’ `Rob Bottos`
- Filter out `N/A` and empty strings
- Result: Clean list of player names

---

## 6. Configuration

### 6.1 Convention Dates (`config.py`)

```python
CONVENTION_START_DATE = datetime(2025, 11, 6)  # Convention start (Thursday)

CONVENTION_DAYS = {
    'Thursday': 0,    # 2025-11-06
    'Friday': 1,      # 2025-11-07
    'Saturday': 2,    # 2025-11-08
    'Sunday': 3       # 2025-11-09
}
```

### 6.2 Caching (`app.py`)

```python
CACHE_DURATION = 3600  # 1 hour in seconds
```

- Data is cached in-memory for 1 hour
- Cache is bypassed on `/api/refresh-cache` POST requests
- No persistent database - cache lives only in application memory

---

## 7. Display Features

### 7.1 Calendar Views (FullCalendar 6.1.10)

**Technologies**:
- FullCalendar JavaScript library
- Custom event rendering
- Time grid layout

**Time Format Handling**:
- Supports both `HH:MM` and `HH:MM:SS` time formats
- Normalizes to ISO 8601 format for FullCalendar: `YYYY-MM-DDTHH:MM:SS`
- Prevents invalid timestamps like `09:00:00:00` (bug fix for game 167)

**Status Color Coding**:
- OPEN games: Green (#d4edda)
- FULL games: Red (#f8d7da)

### 7.2 Responsive Design

- Print-friendly layouts (portrait for all-games, landscape for player schedule)
- Mobile-friendly navigation
- Viewport scaling

---

## 8. Error Handling

### 8.1 Route Errors

| Scenario | Response |
|----------|----------|
| Player not found | 404 "Player 'name' not found" |
| Data load failure | 500 "Error loading games: [error message]" |
| Server error | 500 "Error loading calendar: [error message]" |

### 8.2 Data Errors

| Issue | Behavior |
|-------|----------|
| Invalid day name | Game sorted to end (day_order = 99) |
| Unparseable time | Defaults to 00:00 |
| Missing columns | Row skipped entirely |
| Empty game name | Game excluded from display |

---

## 9. Performance Characteristics

### 9.1 Load Times

- **Page load**: ~500ms (with cached data)
- **Calendar render**: ~1-2 seconds (JavaScript)
- **Calendar day switch**: ~200ms (filter existing events)

### 9.2 Data Size

- **Total games**: ~173 (from live sheet)
- **Total players**: ~400+ unique names
- **Cache size**: <1MB in memory

### 9.3 Scalability Limits

- Calendar view starts slowing at 500+ games per day
- Player list rendering ~instant up to 1000 players
- WebDriver timeouts set to 15 seconds for page load

---

## 10. Known Limitations

### 10.1 Data Freshness

- Data cached for 1 hour
- Immediate updates require manual refresh via API
- No real-time push notifications

### 10.2 Column Structure Dependency

- Hardcoded column indices (0, 1, 2, 11-14, 19-20, 23-31)
- If Google Sheet structure changes, app breaks
- No validation that columns match expectations

### 10.3 Convention Structure

- Fixed 4-day convention (Thursday-Sunday)
- Hard-coded in config.py
- Cannot be changed without code modification

### 10.4 Storage and Persistence

- No database - all data in memory
- Restarting app clears cache
- No player preference persistence

### 10.5 Player Names

- Player names extracted from signup form email entries
- Assumes format: `Name <email@example.com>`
- No validation of player name uniqueness
- URL encoding required for names with spaces

---

## 11. Technical Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Web Framework | Flask | 3.0.0 |
| HTTP Server | Gunicorn | 21.2.0 |
| HTTP Library | Requests | 2.31.0 |
| Calendar UI | FullCalendar | 6.1.10 |
| Deployment | Docker + Google Cloud Run | - |
| Data Source | Google Sheets | - |
| Testing | pytest, Selenium | 7.4.0, 4.10.0 |

---

## 12. API Response Examples

### 12.1 Refresh Cache Response

**Success**:
```json
{
  "success": true,
  "message": "Schedule data refreshed successfully"
}
```

**Failure**:
```json
{
  "success": false,
  "message": "Error refreshing: Connection timeout"
}
```

---

## 13. Browser Compatibility

**Tested and Supported**:
- Firefox (primary testing browser)
- Chrome/Chromium
- Safari (likely works, not extensively tested)

**Requirements**:
- JavaScript enabled
- ES6 support for calendar rendering
- Cookies enabled for session management

---

## 14. Accessibility and Usability

### 14.1 Navigation

- Home page lists all players alphabetically
- Clear breadcrumb navigation
- Player name URL encoding handled by framework

### 14.2 Display Options

- List view for detailed game information
- Calendar view for visual scheduling
- Print-friendly layouts

### 14.3 Information Density

- Game cards show: ID, name, time, duration, table, status, player count
- Hover tooltips (in calendar view) show: full player list, status details

---

## 15. Future Enhancements (Potential)

- [ ] Real-time data updates (WebSockets)
- [ ] Database persistence
- [ ] Search/filter games
- [ ] Player calendar export (iCalendar format)
- [ ] Mobile app
- [ ] Conflict detection (overlapping game times)
- [ ] Preference storage (favorite games, watch lists)
- [ ] Admin dashboard for organizers
- [ ] Automated test data generation
- [ ] API for external integrations

---

## 16. Testing

### 16.1 Test Coverage

- **Unit Tests**: 13 (CSV parsing, data extraction)
- **Integration Tests**: 14 (calendar rendering, ISO 8601 timestamps)
- **End-to-End Tests**: 8 (browser-based, real app instances)
- **Total**: 35 tests, all passing

### 16.2 Critical Paths Tested

- Game 167 "New Cold War" presence in all views
- Time format handling (HH:MM and HH:MM:SS)
- ISO 8601 timestamp generation for FullCalendar
- Game count consistency
- Calendar endpoint responses

### 16.3 Test Environments

- Local Flask test client
- Local Flask app with Selenium
- Deployed Google Cloud Run app with Selenium

---

## 17. Deployment

### 17.1 Container

**Image**: Docker container (see Dockerfile)

**Base**: Python runtime

**Port**: 8080 (configurable via PORT env var)

### 17.2 Cloud Run

**URL**: https://bottoscon-app-686572802163.northamerica-northeast1.run.app/

**Region**: northamerica-northeast1

**Scaling**: Automatic (Cloud Run default)

### 17.3 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | 8080 | Server port |
| `FLASK_ENV` | production | Environment mode |

---

## 18. Notable Bug Fixes

### 18.1 Game 167 Missing from Calendar Views (Fixed)

**Bug**: Game 167 "New Cold War" appeared in list views but not in calendar views.

**Root Cause**: Time format inconsistency. Game had `start_time='09:00:00'` (with seconds) while code appended `:00`, creating invalid ISO 8601 timestamp `09:00:00:00`.

**Impact**: FullCalendar silently discards events with invalid timestamps.

**Fix**: Add `formatTime()` function to normalize time formats:
- `HH:MM` ’ `HH:MM:00`
- `HH:MM:SS` ’ `HH:MM:SS` (unchanged)

**Files Modified**:
- `templates/all_games_calendar.html`
- `templates/calendar.html`

---

## 19. Documentation

- `TEST_SPEC.md`: Detailed test specifications and test cases
- `TESTING.md`: How to run the test suite
- `README.md`: General project information
- `SPECIFICATION.md`: This document

---

## 20. Contact and Support

For questions about the implementation or to report issues, see the project README.

---

**Document Status**: Current as of November 5, 2025

**Last Verified**: All features tested and working with 35 passing automated tests
