# BottosCon App - Testing Guide

**Updated by Claude AI at 2025-11-05 15:30:00**

This guide explains how to run the BottosCon test suite, which includes unit tests, integration tests, and end-to-end Selenium tests.

## Quick Start

### 1. Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

This installs pytest, Selenium, and webdriver-manager without adding them to production dependencies.

### 2. Run All Core Tests (Unit + Integration)

```bash
pytest tests/test_parsing.py tests/test_calendar.py -v
```

**Expected Result:** 27 tests pass ✅

### 3. Run Selenium Tests (Against Local App)

**Terminal 1 - Start Flask app:**
```bash
python app.py
```

**Terminal 2 - Run Selenium tests:**
```bash
pytest tests/test_selenium.py -v
```

---

## Test Suites

### Unit & Integration Tests (27 tests)

These tests validate the backend data pipeline and calendar rendering logic. **They do NOT require a running Flask server** - they use Flask's test client.

#### Run Parsing Tests (13 tests)
Tests CSV parsing, game extraction, data validation, and caching.

```bash
pytest tests/test_parsing.py -v
```

**What it tests:**
- CSV data is fetched and cached
- Games are parsed correctly from Google Sheets
- Game 167 "New Cold War" is present and valid
- All games have required fields
- Sorting is chronological
- Player game mappings are correct

#### Run Calendar Tests (14 tests)
Tests calendar view rendering logic and ISO 8601 timestamp generation.

```bash
pytest tests/test_calendar.py -v
```

**What it tests:**
- Time format consistency (HH:MM vs HH:MM:SS)
- ISO 8601 timestamp generation is valid
- Game 167 appears in calendar data
- Calendar endpoints return correct data
- Game count matches between backend and frontend

#### Run All Core Tests
```bash
pytest tests/test_parsing.py tests/test_calendar.py -v
```

---

### End-to-End Selenium Tests (8 tests)

These tests verify the app works in a real browser. They can test against:
- **Local Flask app** (default)
- **Deployed app** (via environment variable)

#### Prerequisites

- Firefox browser must be installed
- geckodriver in system PATH, OR
- webdriver-manager will auto-download it

#### Test Against Local App

**Terminal 1 - Start the Flask app:**
```bash
python app.py
```

This starts the app at `http://localhost:8080`

**Terminal 2 - Run Selenium tests:**
```bash
pytest tests/test_selenium.py -v
```

#### Test Against Deployed App (Headless)

```bash
set TEST_BASE_URL=https://bottoscon-app-686572802163.northamerica-northeast1.run.app
pytest tests/test_selenium.py -v
```

#### Test Against Deployed App (With Visible Browser)

```bash
set TEST_BASE_URL=https://bottoscon-app-686572802163.northamerica-northeast1.run.app
set HEADLESS=false
pytest tests/test_selenium.py -v
```

**What it tests:**
- All-games page loads and displays games
- All-games calendar page loads
- Calendar has day selection tabs (Thursday, Friday, Saturday, Sunday)
- Game 167 "New Cold War" appears on all-games page
- Game 167 appears in all-games calendar
- Player calendar is accessible
- Calendar displays game count information

---

## Environment Variables

Control test behavior with environment variables:

| Variable | Default | Values | Purpose |
|----------|---------|--------|---------|
| `TEST_BASE_URL` | `http://localhost:8080` | URL string | Which app instance to test against |
| `HEADLESS` | `true` | `true` / `false` | Run browser headless or visible |
| `TEST_TIMEOUT` | `10` | seconds (integer) | WebDriver implicit wait timeout |

### Examples

```bash
# Test against deployed app, headless (fast)
set TEST_BASE_URL=https://bottoscon-app-686572802163.northamerica-northeast1.run.app
pytest tests/test_selenium.py -v

# Test against deployed app, with visible browser
set TEST_BASE_URL=https://bottoscon-app-686572802163.northamerica-northeast1.run.app
set HEADLESS=false
pytest tests/test_selenium.py -v

# Test against local app with longer timeout
set TEST_BASE_URL=http://localhost:8080
set TEST_TIMEOUT=15
pytest tests/test_selenium.py -v
```

---

## Running Specific Tests

### Run a Single Test Class

```bash
pytest tests/test_calendar.py::TestAllGamesCalendarView -v
```

### Run a Single Test Method

```bash
pytest tests/test_calendar.py::TestAllGamesCalendarView::test_game_167_in_all_games_calendar -v
```

### Run Tests Matching a Pattern

```bash
pytest tests/ -k "game_167" -v
```

### Run with More Output Detail

```bash
pytest tests/test_calendar.py -vv --tb=short
```

---

## Test Results Interpretation

### All Tests Pass ✅

```
============================= 27 passed in 3.17s ==============================
```

Success! The app is working correctly.

### Some Tests Fail ❌

```
FAILED tests/test_parsing.py::TestCSVParsing::test_game_count_matches_csv
```

Check the error message:
```
AssertionError: Game count mismatch: CSV has 171 games, but parser only returned 150
```

This typically means:
- CSV data changed
- Google Sheets connection is down
- Parsing logic has a bug

### Timeout Errors (Selenium Tests)

```
selenium.common.exceptions.TimeoutException
```

**Causes:**
- Flask app isn't running (local tests)
- URL is unreachable (deployed tests)
- Element didn't load within timeout

**Solution:**
- Verify Flask is running: `python app.py`
- Verify URL is correct and accessible
- Increase timeout: `set TEST_TIMEOUT=20`

---

## Testing Workflow

### 1. During Development

```bash
# Run fast core tests frequently
pytest tests/test_parsing.py tests/test_calendar.py -v

# Run Selenium tests before committing
pytest tests/test_selenium.py -v
```

### 2. Before Deploying

```bash
# Run all tests against local app
python app.py &  # Run in background
pytest tests/test_parsing.py tests/test_calendar.py tests/test_selenium.py -v

# Run all tests against deployed app
set TEST_BASE_URL=https://bottoscon-app-686572802163.northamerica-northeast1.run.app
pytest tests/ -v
```

### 3. Continuous Integration

See `.github/workflows/` for automated test runs on every commit.

---

## Critical Tests for Game 167 Bug

These tests specifically verify that game 167 "New Cold War" is handled correctly:

**Backend parsing:**
```bash
pytest tests/test_parsing.py::TestCSVParsing::test_game_167_is_parsed -v
pytest tests/test_parsing.py::TestCSVParsing::test_game_167_has_correct_data -v
```

**Calendar rendering (ISO 8601 fix):**
```bash
pytest tests/test_calendar.py::TestCalendarTimeFormatting::test_game_167_time_format -v
pytest tests/test_calendar.py::TestAllGamesCalendarView::test_all_games_calendar_iso8601_timestamps -v
pytest tests/test_calendar.py::TestAllGamesCalendarView::test_game_167_in_all_games_calendar -v
```

**Browser rendering:**
```bash
pytest tests/test_selenium.py::TestAllGamesPageBasic::test_game_167_displayed_on_all_games -v
pytest tests/test_selenium.py::TestCalendarViewBasic::test_game_167_in_all_games_calendar -v
```

---

## Troubleshooting

### Problem: `ModuleNotFoundError: No module named 'selenium'`

**Solution:**
```bash
pip install -r requirements-test.txt
```

### Problem: Firefox driver not found

**Solution 1 - Install Firefox:**
```bash
# Windows
choco install firefox

# macOS
brew install firefox

# Linux
sudo apt-get install firefox-geckodriver
```

**Solution 2 - Let webdriver-manager download it:**
Already handled! It will auto-download on first run.

### Problem: Local Flask app not accessible from tests

**Check:**
1. Flask is running: `python app.py` in another terminal
2. It shows `Running on http://127.0.0.1:8080`
3. You can access it in browser: `http://localhost:8080`

### Problem: Test timeout when accessing deployed app

**Solution:**
Increase timeout:
```bash
set TEST_TIMEOUT=20
pytest tests/test_selenium.py -v
```

### Problem: Calendar tests fail with time format errors

**Check:**
1. Google Sheets data has consistent time format (HH:MM or HH:MM:SS)
2. No games have invalid times like "25:00" or "09:00:00:00"

**Verify:**
```bash
pytest tests/test_calendar.py::TestCalendarTimeFormatting -v
```

---

## Test Files Overview

| File | Tests | Purpose |
|------|-------|---------|
| `tests/conftest.py` | - | Shared fixtures and configuration |
| `tests/test_parsing.py` | 13 | CSV parsing and data extraction |
| `tests/test_calendar.py` | 14 | Calendar rendering and ISO 8601 validation |
| `tests/test_selenium.py` | 8 | End-to-end browser testing |
| `requirements-test.txt` | - | Test-only dependencies |

---

## CI/CD Integration

Tests are automatically run on every commit via GitHub Actions (if configured).

To run tests locally exactly as CI does:
```bash
pytest tests/test_parsing.py tests/test_calendar.py -v
```

(Selenium tests in CI require special setup for headless Chrome/Firefox)

---

## Performance Notes

- **Parsing tests:** ~3 seconds
- **Calendar tests:** ~2 seconds
- **Selenium tests:** ~30-60 seconds (depends on browser and network)

Total runtime:
- Core tests only: ~5 seconds
- All tests (with Selenium): ~60 seconds
- All tests (against deployed app): ~90 seconds

---

## Questions or Issues?

See `TEST_SPEC.md` for detailed test specifications and expected outcomes.

Contact: [Your name/email]
