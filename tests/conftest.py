"""
Pytest configuration and fixtures for BottosCon app tests.
"""

import sys
import os
import csv
import pytest
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

# Add parent directory to path so we can import app.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import app
from app import Flask

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test Configuration
TEST_CONFIG = {
    'base_url': os.environ.get('TEST_BASE_URL', 'http://localhost:8080'),
    'headless': os.environ.get('HEADLESS', 'true').lower() == 'true',
    'timeout': int(os.environ.get('TEST_TIMEOUT', 10))
}

logger.info(f"BottosCon Test Configuration: {TEST_CONFIG}")


@pytest.fixture
def flask_app():
    """Create and configure a test instance of the Flask app."""
    app.app.config['TESTING'] = True
    app.app.config['ENV'] = 'testing'
    return app.app


@pytest.fixture
def client(flask_app):
    """A test client for the app."""
    return flask_app.test_client()


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG


@pytest.fixture
def base_url():
    """Provide base URL for the test environment."""
    url = TEST_CONFIG['base_url']
    logger.info(f"Using base URL: {url}")
    return url


@pytest.fixture
def firefox_driver():
    """Create Firefox WebDriver for Selenium tests.

    Tests can run against:
    - Deployed app: set TEST_BASE_URL env var to deployed URL
    - Local Flask app: run 'python app.py' in another terminal first
    """
    options = FirefoxOptions()

    if TEST_CONFIG['headless']:
        options.add_argument('--headless')

    # Firefox preferences for stability
    options.set_preference('dom.webdriver.enabled', False)
    options.set_preference('useAutomationExtension', False)
    options.set_preference('toolkit.cosmeticAnimations.enabled', False)

    driver = None
    try:
        # Try system-installed geckodriver first
        try:
            driver_service = FirefoxService()
            driver = webdriver.Firefox(service=driver_service, options=options)
            logger.info("Firefox created using system geckodriver")
        except Exception as system_error:
            # Fall back to webdriver-manager
            logger.info(f"System geckodriver not found: {system_error}")
            try:
                from webdriver_manager.firefox import GeckoDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                cache_manager = DriverCacheManager(valid_range=30)
                driver_service = FirefoxService(GeckoDriverManager(cache_manager=cache_manager).install())
                driver = webdriver.Firefox(service=driver_service, options=options)
                logger.info("Firefox created using webdriver-manager")
            except ImportError:
                logger.error("webdriver-manager not installed. Install with: pip install webdriver-manager")
                raise

        driver.implicitly_wait(TEST_CONFIG['timeout'])
        driver.set_page_load_timeout(15)
        yield driver

    except Exception as e:
        logger.error(f"Failed to create Firefox driver: {e}")
        pytest.fail(f"Cannot run Selenium tests: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Firefox driver closed")
            except Exception as e:
                logger.warning(f"Error closing Firefox: {e}")


@pytest.fixture
def csv_file_path():
    """Return path to the local CSV file."""
    return Path(__file__).parent.parent / "bottoscon2025.csv"


@pytest.fixture
def csv_games(csv_file_path):
    """Load all games from the local CSV file and return as list of dicts."""
    games = []
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

        # Skip first 4 rows as headers (based on analysis)
        # Rows 0-3 are headers, data starts at row 4
        for i, row in enumerate(rows[4:], start=1):
            if len(row) < 2:
                continue

            game_id = row[0].strip() if len(row) > 0 else ""
            game_name = row[1].strip() if len(row) > 1 else ""

            # Skip rows without game ID or name
            if not game_id or not game_name:
                continue

            games.append({
                'csv_line': i + 4,
                'id': game_id,
                'name': game_name,
                'raw_row': row
            })

    return games


@pytest.fixture
def parsed_games(client):
    """Get games parsed by the app's parse_games_and_players() function."""
    games, _ = app.parse_games_and_players()
    return games


@pytest.fixture
def game_167_from_csv(csv_games):
    """Find and return game 167 from CSV."""
    for game in csv_games:
        if game['id'] == '167':
            return game
    return None


@pytest.fixture
def game_167_from_app(parsed_games):
    """Find and return game 167 from parsed games."""
    for game in parsed_games:
        if str(game['id']) == '167':
            return game
    return None
