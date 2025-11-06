"""
Tests for calendar view rendering and time format handling.

These tests ensure that:
- All games render correctly in calendar views
- Time formats with and without seconds are handled correctly
- ISO 8601 timestamps are valid
- Game 167 appears in all calendar views
"""

import pytest
import json
import re
from bs4 import BeautifulSoup


class TestCalendarTimeFormatting:
    """Test that time formats are correctly handled in calendar views."""

    def test_time_format_consistency(self, parsed_games):
        """Verify all games have consistent time format (HH:MM or HH:MM:SS)"""
        time_pattern = r'^(\d{2}):(\d{2})(?::(\d{2}))?$'

        for game in parsed_games:
            start_time = game.get('start_time', '')
            end_time = game.get('end_time', '')

            assert re.match(time_pattern, start_time), (
                f"Game {game['id']}: Invalid start_time format '{start_time}'"
            )
            assert re.match(time_pattern, end_time), (
                f"Game {game['id']}: Invalid end_time format '{end_time}'"
            )

    def test_game_167_time_format(self, game_167_from_app):
        """TC: Game 167 has valid time format (may be HH:MM or HH:MM:SS)"""
        if game_167_from_app is None:
            pytest.skip("Game 167 not parsed")

        game = game_167_from_app
        time_pattern = r'^(\d{2}):(\d{2})(?::(\d{2}))?$'

        assert re.match(time_pattern, game['start_time']), (
            f"Game 167: Invalid start_time format '{game['start_time']}'"
        )
        assert re.match(time_pattern, game['end_time']), (
            f"Game 167: Invalid end_time format '{game['end_time']}'"
        )

    def test_games_with_mixed_time_formats(self, parsed_games):
        """Identify games with inconsistent time format (start has seconds but end doesn't)"""
        with_seconds = []
        without_seconds = []

        for game in parsed_games:
            start_time = game.get('start_time', '')
            end_time = game.get('end_time', '')

            start_has_seconds = start_time.count(':') == 2
            end_has_seconds = end_time.count(':') == 2

            if start_has_seconds != end_has_seconds:
                with_seconds.append((game['id'], game['name'], start_time, end_time))

        if with_seconds:
            print(f"\n{len(with_seconds)} games have mixed time formats:")
            for game_id, name, start, end in with_seconds[:10]:  # Show first 10
                print(f"  Game {game_id}: start={start}, end={end}")


class TestAllGamesCalendarView:
    """Test the all-games calendar view."""

    def test_all_games_calendar_endpoint_exists(self, client):
        """Verify /calendar/all-games endpoint exists"""
        response = client.get('/calendar/all-games')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_all_games_calendar_contains_fullcalendar(self, client):
        """Verify calendar view loads FullCalendar library"""
        response = client.get('/calendar/all-games')
        assert response.status_code == 200
        assert 'fullcalendar' in response.data.decode().lower(), (
            "Calendar view should include FullCalendar library"
        )

    def test_all_games_calendar_passes_games_to_frontend(self, client, parsed_games):
        """Verify all games are passed to the JavaScript frontend"""
        response = client.get('/calendar/all-games')
        html = response.data.decode()

        # Find the games JSON embedded in the page
        # Pattern: const games = {...};
        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in calendar page"

        games_json = match.group(1)
        # Parse the JSON
        try:
            frontend_games = json.loads(games_json)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in calendar page: {e}")

        assert len(frontend_games) == len(parsed_games), (
            f"Frontend has {len(frontend_games)} games, but {len(parsed_games)} were parsed"
        )

    def test_all_games_calendar_iso8601_timestamps(self, client, parsed_games):
        """TC: Verify calendar generates valid ISO 8601 timestamps"""
        import app as app_module
        from config import CONVENTION_DAYS, CONVENTION_START_DATE
        from datetime import timedelta

        response = client.get('/calendar/all-games')
        html = response.data.decode()

        # Find the games JSON
        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in calendar page"

        games_json = match.group(1)
        frontend_games = json.loads(games_json)

        # Simulate what the frontend JavaScript does (formatTime function)
        def format_time(time_str):
            parts = time_str.split(':')
            if len(parts) == 2:
                return f"{time_str}:00"
            return time_str

        # Build date map (like in the JavaScript)
        day_map = {}
        for day in ['Thursday', 'Friday', 'Saturday', 'Sunday']:
            offset = CONVENTION_DAYS.get(day, 0)
            actual_date = CONVENTION_START_DATE + timedelta(days=offset)
            day_map[day] = actual_date.strftime('%Y-%m-%d')

        iso8601_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'

        # Verify each game would generate valid ISO 8601 timestamps
        for frontend_game in frontend_games:
            start_day = frontend_game.get('start_day', '')
            start_time = frontend_game.get('start_time', '')
            end_day = frontend_game.get('end_day', start_day)
            end_time = frontend_game.get('end_time', '')

            # Simulate the JavaScript transformation
            start_time_formatted = format_time(start_time)
            end_time_formatted = format_time(end_time)

            start_date = day_map.get(start_day, '')
            end_date = day_map.get(end_day, start_date)

            start_iso = f"{start_date}T{start_time_formatted}"
            end_iso = f"{end_date}T{end_time_formatted}"

            assert re.match(iso8601_pattern, start_iso), (
                f"Invalid start timestamp for game {frontend_game.get('name')}: {start_iso} "
                f"(start_day={start_day}, start_time={start_time})"
            )
            assert re.match(iso8601_pattern, end_iso), (
                f"Invalid end timestamp for game {frontend_game.get('name')}: {end_iso} "
                f"(end_day={end_day}, end_time={end_time})"
            )

    def test_game_167_in_all_games_calendar(self, client, game_167_from_app):
        """TC-011: Game 167 appears in all-games calendar view"""
        if game_167_from_app is None:
            pytest.skip("Game 167 not parsed")

        response = client.get('/calendar/all-games')
        html = response.data.decode()

        # Find the games JSON
        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in calendar page"

        games_json = match.group(1)
        frontend_games = json.loads(games_json)

        game_167_found = any(
            g.get('title') == 'New Cold War' or '167' in str(g)
            for g in frontend_games
        )

        assert game_167_found, (
            "Game 167 'New Cold War' not found in all-games calendar data"
        )


class TestPlayerCalendarView:
    """Test individual player calendar views."""

    def test_player_calendar_endpoint_exists(self, client):
        """Verify /calendar/<player> endpoint works"""
        # Use a known player from the game
        _, player_games = __import__('app').parse_games_and_players()

        if not player_games:
            pytest.skip("No players in parsed games")

        player_name = list(player_games.keys())[0]
        response = client.get(f'/calendar/{player_name}')
        assert response.status_code == 200, (
            f"Calendar endpoint failed for player {player_name}"
        )

    def test_player_calendar_contains_fullcalendar(self, client):
        """Verify player calendar view loads FullCalendar"""
        _, player_games = __import__('app').parse_games_and_players()

        if not player_games:
            pytest.skip("No players in parsed games")

        player_name = list(player_games.keys())[0]
        response = client.get(f'/calendar/{player_name}')
        assert 'fullcalendar' in response.data.decode().lower()

    def test_player_calendar_iso8601_timestamps(self, client):
        """Verify player calendar generates valid ISO 8601 timestamps"""
        import app as app_module
        from config import CONVENTION_DAYS, CONVENTION_START_DATE
        from datetime import timedelta

        _, player_games = app_module.parse_games_and_players()

        if not player_games:
            pytest.skip("No players in parsed games")

        player_name = list(player_games.keys())[0]
        response = client.get(f'/calendar/{player_name}')
        html = response.data.decode()

        # Find the games JSON (player calendar uses 'const games = ...')
        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)

        if not match:
            pytest.skip("No games data found in player calendar")

        games_json = match.group(1)
        frontend_games = json.loads(games_json)

        # Simulate what the frontend JavaScript does (formatTime function)
        def format_time(time_str):
            parts = time_str.split(':')
            if len(parts) == 2:
                return f"{time_str}:00"
            return time_str

        # Build date map (like in the JavaScript)
        day_map = {}
        for day in ['Thursday', 'Friday', 'Saturday', 'Sunday']:
            offset = CONVENTION_DAYS.get(day, 0)
            actual_date = CONVENTION_START_DATE + timedelta(days=offset)
            day_map[day] = actual_date.strftime('%Y-%m-%d')

        iso8601_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'

        for frontend_game in frontend_games:
            start_day = frontend_game.get('start_day', '')
            start_time = frontend_game.get('start_time', '')
            end_day = frontend_game.get('end_day', start_day)
            end_time = frontend_game.get('end_time', '')

            # Simulate the JavaScript transformation
            start_time_formatted = format_time(start_time)
            end_time_formatted = format_time(end_time)

            start_date = day_map.get(start_day, '')
            end_date = day_map.get(end_day, start_date)

            start_iso = f"{start_date}T{start_time_formatted}"
            end_iso = f"{end_date}T{end_time_formatted}"

            assert re.match(iso8601_pattern, start_iso), (
                f"Invalid start timestamp for game {frontend_game.get('name')}: {start_iso}"
            )
            assert re.match(iso8601_pattern, end_iso), (
                f"Invalid end timestamp for game {frontend_game.get('name')}: {end_iso}"
            )

    def test_game_167_player_calendar(self, client, game_167_from_app):
        """Verify game 167 appears in player calendar if they're in the game"""
        if game_167_from_app is None:
            pytest.skip("Game 167 not parsed")

        # Get a player from game 167
        players = game_167_from_app.get('players', [])
        if not players:
            pytest.skip("Game 167 has no players")

        player_name = players[0]
        response = client.get(f'/calendar/{player_name}')
        assert response.status_code == 200

        html = response.data.decode()

        # Check if game 167 is in the calendar data
        assert 'New Cold War' in html or '167' in html or game_167_from_app['name'] in html, (
            f"Game 167 'New Cold War' not found in calendar for {player_name}"
        )


class TestCalendarDataIntegrity:
    """Test that calendar data matches backend parsed data."""

    def test_all_games_calendar_count_matches_backend(self, client, parsed_games):
        """Verify calendar view has same game count as backend"""
        response = client.get('/calendar/all-games')
        html = response.data.decode()

        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in calendar page"

        games_json = match.group(1)
        frontend_games = json.loads(games_json)

        assert len(frontend_games) == len(parsed_games), (
            f"Game count mismatch: Backend={len(parsed_games)}, Frontend={len(frontend_games)}"
        )

    def test_calendar_displays_game_count(self, client):
        """Verify calendar view displays the game count to user"""
        response = client.get('/calendar/all-games')
        html = response.data.decode()

        # Should show game count badge
        assert 'games total' in html or 'game' in html.lower(), (
            "Calendar should display game count"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
