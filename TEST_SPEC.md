# BottosCon App - Test Specification

**Updated by Claude AI at 2025-11-05 15:00:00**

## Purpose
Verify that all games from the source Google Sheet are correctly loaded, parsed, and displayed on the all-games page. Diagnose why game 167 ("New Cold War") is missing from the deployed app.

## Scope
- CSV parsing from Google Sheets export
- In-memory cache validation
- All-games page rendering
- Game data completeness and accuracy

## Test Strategy

### Unit Tests (pytest)
Focus on the backend data pipeline:
1. CSV fetch and caching
2. Game parsing logic
3. Column validation and filtering
4. Sorting behavior

### Integration Tests (pytest + Selenium)
Focus on end-to-end data flow:
1. Start Flask app locally
2. Fetch all-games page
3. Parse rendered game list
4. Compare with CSV source file
5. Identify missing games

## Test Cases

### Test Suite 1: CSV Parsing & Data Integrity

#### TC-001: CSV Fetch Returns Data
- **Given**: App can reach Google Sheets export URL
- **When**: `fetch_sheet_data()` is called
- **Then**: Returns list of rows with > 0 entries

#### TC-002: Game Count Matches CSV
- **Given**: CSV file has N games (excluding headers)
- **When**: `parse_games_and_players()` is called
- **Then**: Returns list with exactly N games
- **Critical**: Should return 169 games based on current CSV file

#### TC-003: Game 167 "New Cold War" is Parsed
- **Given**: Game 167 exists in CSV at specific row
- **When**: `parse_games_and_players()` is called
- **Then**: Game 167 is included in results with:
  - ID: 167
  - Name: "New Cold War"
  - Status: "FULL"
  - Start Day: "Friday"
  - Start Time: "09:00:00" or "09:00"
  - End Day: "Friday"
  - End Time: "13:00"
  - Table: "H23"

#### TC-004: All Games Have Required Fields
- **Given**: Valid CSV data
- **When**: Each game is parsed
- **Then**: Every game has non-empty:
  - Game ID
  - Game Name
  - Start Day (one of: Thursday, Friday, Saturday, Sunday)
  - Start Time (format: HH:MM or HH:MM:SS)
  - End Time (format: HH:MM or HH:MM:SS)

#### TC-005: Games with < 23 Columns Are Skipped
- **Given**: CSV has rows with < 23 columns
- **When**: `parse_games_and_players()` is called
- **Then**: These rows are filtered out (not included in results)

#### TC-006: Games with Empty Game ID Are Skipped
- **Given**: CSV has rows with blank Game ID (column 0)
- **When**: `parse_games_and_players()` is called
- **Then**: These rows are filtered out

#### TC-007: Games with Empty Game Name Are Skipped
- **Given**: CSV has rows with blank Game Name (column 1)
- **When**: `parse_games_and_players()` is called
- **Then**: These rows are filtered out

#### TC-008: Sorting is Chronological
- **Given**: Games with different days and times
- **When**: `sort_games_chronologically()` is called
- **Then**: Games are ordered by:
  1. Day: Thursday → Friday → Saturday → Sunday
  2. Within same day: By start time (earliest first)

### Test Suite 2: All-Games Page Display

#### TC-009: All-Games Route Returns 200
- **Given**: Flask app is running
- **When**: GET request to `/all-games`
- **Then**: Response status is 200

#### TC-010: All-Games Page Shows All Games
- **Given**: Backend parsed N games
- **When**: Page loads with Selenium
- **Then**: Page displays all N games (compare rendered count with backend count)

#### TC-011: All-Games Page Displays Game 167
- **Given**: Game 167 exists in CSV and is parsed by backend
- **When**: `/all-games` page is loaded
- **Then**: Page contains:
  - Game name: "New Cold War"
  - Game ID: 167
  - Time: "09:00 - 13:00"
  - Table: "H23"
  - Day: "Friday"

#### TC-012: All Games Have Required Fields Visible
- **Given**: All-games page is loaded
- **When**: Each game entry is examined
- **Then**: Each game displays:
  - Game ID
  - Game Name
  - Start time and end time
  - Duration
  - Table number
  - Status badge

### Test Suite 3: Data Comparison (CSV vs Website)

#### TC-013: CSV Game Count Matches Website
- **Given**: Local CSV file has M games
- **When**: All-games page is loaded
- **Then**: Website displays exactly M games (no more, no less)

#### TC-014: All CSV Games Are on Website
- **Given**: CSV file contains specific games
- **When**: All-games page is rendered
- **Then**: Every game from CSV (with Game ID and Name) appears on page

#### TC-015: Game Data is Accurate
- **Given**: CSV has specific game data
- **When**: Game is rendered on all-games page
- **Then**: Displayed data matches CSV source:
  - Game ID
  - Game Name
  - Start/end times
  - Table number

## Expected Results

### CSV File Statistics
- File: `bottoscon2025.csv`
- Total lines: 509
- Header rows: 4 (rows 1-4 contain headers/instructions)
- Data rows: 505 (rows 5-509)
- Expected games: ~169 games (actual count TBD based on filtering rules)
- **Critical game**: Game 167 "New Cold War" at CSV line 67

### Deployment vs Local
- **Deployed**: https://bottoscon-app-686572802163.northamerica-northeast1.run.app/
- **Local**: `python app.py` on http://localhost:8080
- Both should display identical game lists if they use the same data source

## Potential Issues to Investigate

1. **CSV Structure Changed**: If Google Sheet structure changed, hardcoded column indices may be wrong
2. **Column Count Validation**: Game 167 may have fewer than 23 columns
3. **Empty Fields**: Game 167 might have empty Game ID or Game Name in the source sheet (different from CSV export)
4. **Cache Issues**: Deployment might be using stale cached data
5. **Live URL vs CSV Export**: If the deployed app uses a live Google Sheets API instead of CSV export
6. **Time Format Parsing**: Game 167's time might not parse correctly (e.g., "09:00:00" vs "09:00")
7. **Header Row Skipping**: If the app skips the wrong number of header rows
8. **Data Type Mismatches**: Game ID might be stored as text/number differently
9. **Filtering Logic**: Deployed app might have additional filtering not in the code
10. **Race Condition**: Data might be being modified during fetch

## Test Execution Steps

1. **Setup**: Install dependencies from requirements.txt
2. **Unit Tests**: Run `pytest tests/test_parsing.py -v`
3. **Integration Tests**: Run Flask app locally, then `pytest tests/test_selenium.py -v`
4. **Manual Verification**: View `/all-games` in browser, search for "New Cold War"
5. **CSV Validation**: Compare CSV file game count with website game count
6. **Debugging**: Enable logging in `parse_games_and_players()` to trace issue

## Success Criteria

✅ Game 167 "New Cold War" appears on all-games page
✅ All 169+ games from CSV are displayed
✅ No games are missing from the website
✅ Game data is accurate and complete
✅ Tests pass both locally and in deployment
