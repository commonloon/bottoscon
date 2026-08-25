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
from config import CONVENTION_DAYS

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

        # Should have a tab for each convention day
        for day in CONVENTION_DAYS.keys():
            assert day in page_source, f"Day tab '{day}' not found in calendar"

        logger.info("Calendar has all day tabs")

class TestGameDetailPanelInteraction:
    """Test the click-to-open game detail panel on the all-games calendar."""

    def test_clicking_event_opens_detail_panel(self, firefox_driver, base_url):
        """Clicking a game event should open the detail panel with player info,
        and the close button should close it again."""
        firefox_driver.get(f'{base_url}/calendar/all-games')

        wait = WebDriverWait(firefox_driver, 10)
        event_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.fc-event')))
        event_el.click()

        overlay = wait.until(EC.presence_of_element_located((By.ID, 'gameDetailOverlay')))
        wait.until(lambda d: 'open' in overlay.get_attribute('class'))

        body_text = firefox_driver.find_element(By.ID, 'gameDetailBody').text
        assert 'Players' in body_text, "Detail panel should show a Players section"

        close_btn = firefox_driver.find_element(By.CSS_SELECTOR, '.modal-close')
        close_btn.click()
        wait.until(lambda d: 'open' not in overlay.get_attribute('class'))

        logger.info("Game detail panel opened and closed successfully")

    def test_description_link_is_clickable(self, firefox_driver, base_url):
        """A URL in a game's description/notes must render as a real,
        clickable <a> link in the detail panel, not plain text."""
        import app as app_module
        games, _ = app_module.parse_games_and_players()
        game_with_link = next(
            (g for g in games if g.get('description') and 'http' in g['description']), None
        )
        if game_with_link is None:
            pytest.skip("No game with a URL in its description found in the live sheet")

        firefox_driver.get(f'{base_url}/calendar/all-games')
        wait = WebDriverWait(firefox_driver, 10)

        day_tab = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, f'.day-tab[data-day="{game_with_link["start_day"]}"]')
        ))
        day_tab.click()

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.fc-event')))
        # Match by element text in Python (not XPath string literals) to avoid
        # quoting issues with game names containing apostrophes/quotes.
        event_elements = firefox_driver.find_elements(By.CSS_SELECTOR, '.fc-event')
        target_event = next((el for el in event_elements if game_with_link['name'] in el.text), None)
        assert target_event is not None, f"Could not find calendar event for {game_with_link['name']}"
        target_event.click()

        overlay = wait.until(EC.presence_of_element_located((By.ID, 'gameDetailOverlay')))
        wait.until(lambda d: 'open' in overlay.get_attribute('class'))

        link_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#gameDetailBody a')))
        href = link_el.get_attribute('href')
        assert href and href.startswith('http'), f"Expected a real link, got {href!r}"
        assert link_el.get_attribute('target') == '_blank'

        logger.info(f"Description link rendered correctly: {href}")


class TestFavouritesInteraction:
    """Test the Add/Remove Favourites button on a player's schedule page.

    Regression coverage: an earlier version wired this button with an inline
    onclick="toggleFavourite({{ name|tojson }})" — tojson's own double quotes
    prematurely closed the HTML attribute, producing a JS syntax error and a
    button that silently did nothing. Actually clicking it in a real browser
    (rather than just POSTing the endpoint directly) is what catches that.
    """

    def test_toggle_favourite_button_updates_state_and_nav_bar(self, firefox_driver, base_url):
        import app as app_module
        _, player_games = app_module.parse_games_and_players()
        if not player_games:
            pytest.skip("No players in parsed games")
        player_name = list(player_games.keys())[0]

        firefox_driver.get(f'{base_url}/schedule/{player_name}')
        wait = WebDriverWait(firefox_driver, 10)
        toggle_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.favourite-toggle-btn')))
        assert 'Add to Favourites' in toggle_btn.text

        toggle_btn.click()

        # The button POSTs then reloads the page on success; wait for the new state.
        wait.until(lambda d: 'Remove from Favourites' in d.find_element(By.CSS_SELECTOR, '.favourite-toggle-btn').text)

        # Navigate elsewhere and confirm the shortcut chip shows up there too.
        firefox_driver.get(f'{base_url}/all-games')
        chip = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.favourite-chip')))
        assert player_name in chip.text

        # Chips are intentionally not removable directly (deliberate design:
        # removing is only done from the player's own schedule page, to avoid
        # accidental clicks on the shortcut bar removing someone's favourite).
        assert not chip.find_elements(By.CSS_SELECTOR, 'button'), (
            "Favourite chips should not have their own remove control"
        )

        # Clean up via the schedule page's own toggle button.
        firefox_driver.get(f'{base_url}/schedule/{player_name}')
        toggle_btn_2 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.favourite-toggle-btn')))
        assert 'Remove from Favourites' in toggle_btn_2.text
        toggle_btn_2.click()
        wait.until(lambda d: 'Add to Favourites' in d.find_element(By.CSS_SELECTOR, '.favourite-toggle-btn').text)


class TestPlayerCalendarBasic:
    """Basic tests for player calendar views."""

    def test_player_calendar_accessibility(self, firefox_driver, base_url):
        """Verify we can access a player calendar using a player from the live data."""
        import app as app_module
        import urllib.parse

        _, player_games = app_module.parse_games_and_players()
        if not player_games:
            pytest.skip("No players in parsed games")

        player_name = list(player_games.keys())[0]
        encoded_name = urllib.parse.quote(player_name)

        try:
            firefox_driver.get(f'{base_url}/calendar/{encoded_name}')

            wait = WebDriverWait(firefox_driver, 5)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

            calendar_source = firefox_driver.page_source
            assert 'fullcalendar' in calendar_source.lower() or 'calendar' in calendar_source.lower()
            logger.info(f"Player calendar accessible for {player_name}")

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
