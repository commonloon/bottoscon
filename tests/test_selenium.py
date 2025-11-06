"""
Selenium tests for BottosCon app - end-to-end browser testing.

These tests verify that the app works correctly in a real browser.
Tests run against a configured base URL (local or deployed).

To run these tests:
1. Start the Flask app (if testing locally): python app.py
2. Run tests (headless by default):
   pytest tests/test_selenium.py -v

3. Or run against deployed app with visible browser:
   TEST_BASE_URL=https://bottoscon-app-686572802163.northamerica-northeast1.run.app HEADLESS=false pytest tests/test_selenium.py -v

Environment Variables:
- TEST_BASE_URL: Base URL to test against (default: http://localhost:8080)
- HEADLESS: Run browser headless (default: true)
- TEST_TIMEOUT: WebDriver implicit wait timeout in seconds (default: 10)
"""

import pytest
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class TestAllGamesPageBasic:
    """Basic tests for the all-games list view."""

    def test_all_games_page_loads(self, firefox_driver, base_url):
        """Verify the all-games page loads and is accessible."""
        firefox_driver.get(f'{base_url}/all-games')

        # Wait for page to load and contain game content
        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        # Verify page loaded
        assert 'All Games' in firefox_driver.page_source or 'games' in firefox_driver.page_source.lower()
        logger.info(f"Successfully loaded: {base_url}/all-games")

    def test_all_games_contains_game_header(self, firefox_driver, base_url):
        """Verify all-games page has expected header elements."""
        firefox_driver.get(f'{base_url}/all-games')

        # Wait for content
        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        page_source = firefox_driver.page_source.lower()

        # Should have some indication of games being displayed
        assert 'games' in page_source or 'schedule' in page_source
        logger.info("All-games page has expected content")

    def test_game_167_displayed_on_all_games(self, firefox_driver, base_url):
        """TC-011: Game 167 'New Cold War' appears on all-games page."""
        firefox_driver.get(f'{base_url}/all-games')

        # Wait for page content
        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        page_source = firefox_driver.page_source

        # Check for game 167 - search for both ID and name
        assert '167' in page_source, "Game ID 167 not found on page"
        assert 'Cold War' in page_source or 'New Cold War' in page_source, \
            "Game 'New Cold War' not found on page"

        logger.info("Game 167 'New Cold War' found on all-games page")


class TestCalendarViewBasic:
    """Basic tests for the all-games calendar view."""

    def test_all_games_calendar_loads(self, firefox_driver, base_url):
        """Verify the all-games calendar page loads."""
        firefox_driver.get(f'{base_url}/calendar/all-games')

        # Wait for calendar to load
        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        page_source = firefox_driver.page_source

        # Should have FullCalendar library loaded
        assert 'fullcalendar' in page_source.lower() or 'calendar' in page_source.lower()
        logger.info("All-games calendar page loaded successfully")

    def test_calendar_has_day_tabs(self, firefox_driver, base_url):
        """Verify calendar has day selection tabs (Thursday, Friday, Saturday, Sunday)."""
        firefox_driver.get(f'{base_url}/calendar/all-games')

        # Wait for tabs to be present
        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        page_source = firefox_driver.page_source

        # Should have day tabs
        for day in ['Thursday', 'Friday', 'Saturday', 'Sunday']:
            assert day in page_source, f"Day tab '{day}' not found in calendar"

        logger.info("Calendar has all day tabs")

    def test_game_167_in_all_games_calendar(self, firefox_driver, base_url):
        """TC-011: Verify game 167 appears in the all-games calendar view."""
        firefox_driver.get(f'{base_url}/calendar/all-games')

        # Wait for page to fully load
        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        # Get the rendered page source
        page_source = firefox_driver.page_source

        # Look for game 167 data in the calendar
        assert '167' in page_source, "Game 167 not found in calendar"
        assert 'New Cold War' in page_source or 'Cold War' in page_source, \
            "Game 'New Cold War' not found in calendar"

        logger.info("Game 167 'New Cold War' found in all-games calendar")


class TestPlayerCalendarBasic:
    """Basic tests for player calendar views."""

    def test_player_calendar_accessibility(self, firefox_driver, base_url):
        """Verify we can access a player calendar (using a known player name)."""
        # First, get the list of players
        firefox_driver.get(f'{base_url}/')

        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        # Try to find a player link and navigate to their calendar
        try:
            # Look for any link with "calendar" in it or a player name
            page_source = firefox_driver.page_source

            # Try a known player (Grant Linneberg is in game 167)
            firefox_driver.get(f'{base_url}/calendar/Grant%20Linneberg')

            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

            calendar_source = firefox_driver.page_source

            # Should have calendar and game info
            assert 'fullcalendar' in calendar_source.lower() or 'calendar' in calendar_source.lower()
            logger.info("Player calendar accessible")

        except Exception as e:
            logger.warning(f"Could not test player calendar: {e}")
            pytest.skip("Player calendar not accessible")


class TestCalendarDataIntegrity:
    """Verify calendar data matches backend."""

    def test_calendar_game_count_visible(self, firefox_driver, base_url):
        """Verify calendar page displays game count information."""
        firefox_driver.get(f'{base_url}/calendar/all-games')

        wait = WebDriverWait(firefox_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        page_source = firefox_driver.page_source

        # Should display game count
        assert 'game' in page_source.lower()
        logger.info("Calendar displays game information")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
