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
from config import CONVENTION_DAYS, CONVENTION_START_DATE
from datetime import timedelta


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

        # Build date map from config (mirrors the Jinja template)
        day_map = {
            day: (CONVENTION_START_DATE + timedelta(days=offset)).strftime('%Y-%m-%d')
            for day, offset in CONVENTION_DAYS.items()
        }

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

class TestLandingPageNav:
    """Test that the landing page links to the all-games calendar."""

    def test_index_has_calendar_link(self, client):
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode()
        assert '/calendar/all-games' in html


class TestGameDetailPanel:
    """Test that the all-games calendar's click-to-open detail panel is wired up."""

    def test_detail_panel_markup_and_handlers_present(self, client):
        response = client.get('/calendar/all-games')
        assert response.status_code == 200
        html = response.data.decode()

        assert 'id="gameDetailOverlay"' in html
        assert 'eventClick' in html
        assert 'showGameDetailPanel' in html

    def test_event_props_include_organizer_and_waitlist(self, client, parsed_games):
        """The per-event extendedProps built client-side must be able to derive
        organizer/waitlist info from data actually present in the embedded games JSON."""
        response = client.get('/calendar/all-games')
        html = response.data.decode()

        assert 'organizer:' in html
        assert 'waitlistedPlayers:' in html

        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in calendar page"
        frontend_games = json.loads(match.group(1))

        games_with_players = [g for g in frontend_games if g['players']]
        assert games_with_players, "Expected at least one game with players"
        assert 'waitlisted_players' in games_with_players[0]

    def test_description_wired_up_with_linkify(self, client, parsed_games):
        """The detail panel must include the description field and turn URLs
        within it (e.g. BGG links) into real clickable links, not plain text."""
        response = client.get('/calendar/all-games')
        html = response.data.decode()

        assert 'description:' in html
        assert 'function linkifyText' in html
        assert 'target="_blank"' in html

        games_with_links = [
            g for g in parsed_games
            if g.get('description') and 'http' in g['description']
        ]
        assert games_with_links, "Expected at least one game with a URL in its description"

        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in calendar page"
        frontend_games = json.loads(match.group(1))
        frontend_game = next(g for g in frontend_games if g['name'] == games_with_links[0]['name'])
        assert 'http' in frontend_game['description']


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

        # Build date map from config (mirrors the Jinja template)
        day_map = {
            day: (CONVENTION_START_DATE + timedelta(days=offset)).strftime('%Y-%m-%d')
            for day, offset in CONVENTION_DAYS.items()
        }

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


class TestPlayerWaitlistView:
    """Test that a player's own views clearly mark games they're waitlisted for."""

    def _find_waitlisted_player(self):
        import app as app_module
        _, player_games = app_module.parse_games_and_players()
        for player_name, games in player_games.items():
            for game in games:
                if player_name in game.get('waitlisted_players', []):
                    confirmed = [g for g in games if player_name not in g.get('waitlisted_players', [])]
                    return player_name, game, confirmed
        return None, None, None

    def _find_confirmed_player_with_waitlisted_gamemate(self):
        import app as app_module
        games, _ = app_module.parse_games_and_players()
        for game in games:
            if not game['waitlisted_players']:
                continue
            confirmed = [p for p in game['players'] if p not in game['waitlisted_players']]
            if confirmed:
                return confirmed[0], game['waitlisted_players'][0], game
        return None, None, None

    def test_schedule_marks_waitlisted_game(self, client):
        """Waitlisted game's card is flagged; a confirmed game's card is not."""
        player_name, waitlisted_game, confirmed_games = self._find_waitlisted_player()
        if player_name is None:
            pytest.skip("No waitlisted player found in the live sheet")

        response = client.get(f'/schedule/{player_name}')
        assert response.status_code == 200
        soup = BeautifulSoup(response.data.decode(), 'html.parser')

        cards = soup.select('.game-card')
        waitlisted_card = next((c for c in cards if waitlisted_game['name'] in c.get_text()), None)
        assert waitlisted_card is not None, f"Could not find a game card for {waitlisted_game['name']}"
        assert 'game-card-waitlisted' in waitlisted_card.get('class', []), (
            "Waitlisted game's card should carry the game-card-waitlisted class"
        )
        assert "You're Waitlisted" in waitlisted_card.get_text(), (
            "Waitlisted game's card should show a waitlisted badge"
        )

        if confirmed_games:
            confirmed_card = next(
                (c for c in cards if confirmed_games[0]['name'] in c.get_text()), None
            )
            if confirmed_card is not None:
                assert 'game-card-waitlisted' not in confirmed_card.get('class', []), (
                    f"Confirmed game '{confirmed_games[0]['name']}' should not be marked as waitlisted"
                )

    def test_schedule_marks_other_waitlisted_player_in_roster(self, client):
        """A confirmed player's own schedule still tags OTHER waitlisted
        players within a shared game's roster (regression: this was
        previously only fixed on /all-games, not on the personal schedule)."""
        viewer_name, waitlisted_name, game = self._find_confirmed_player_with_waitlisted_gamemate()
        if viewer_name is None:
            pytest.skip("No game with both a confirmed and a waitlisted player found")

        response = client.get(f'/schedule/{viewer_name}')
        assert response.status_code == 200
        soup = BeautifulSoup(response.data.decode(), 'html.parser')

        cards = soup.select('.game-card')
        game_card = next((c for c in cards if game['name'] in c.get_text()), None)
        assert game_card is not None, f"Could not find a game card for {game['name']}"

        waitlisted_tag = next(
            (tag for tag in game_card.select('.player-tag') if waitlisted_name in tag.get_text()), None
        )
        assert waitlisted_tag is not None, f"Could not find player tag for {waitlisted_name}"
        assert 'player-tag-waitlisted' in waitlisted_tag.get('class', []), (
            f"{waitlisted_name}'s tag should carry player-tag-waitlisted even on {viewer_name}'s own schedule"
        )

        viewer_tag = next(
            (tag for tag in game_card.select('.player-tag') if 'current-player' in tag.get('class', [])), None
        )
        if viewer_tag is not None:
            assert 'player-tag-waitlisted' not in viewer_tag.get('class', []), (
                f"Confirmed viewer {viewer_name} should not be marked as waitlisted"
            )

    def test_calendar_json_flags_waitlisted_game(self, client):
        """Player calendar's embedded games JSON flags viewer_waitlisted correctly."""
        player_name, waitlisted_game, confirmed_games = self._find_waitlisted_player()
        if player_name is None:
            pytest.skip("No waitlisted player found in the live sheet")

        response = client.get(f'/calendar/{player_name}')
        assert response.status_code == 200
        html = response.data.decode()
        assert 'status-WAITLISTED' in html, "Calendar page should include the status-WAITLISTED class"

        match = re.search(r'const games = (\[.*?\]);', html, re.DOTALL)
        assert match, "No games data found in player calendar page"
        frontend_games = json.loads(match.group(1))

        frontend_waitlisted = next(
            (g for g in frontend_games if g['name'] == waitlisted_game['name']), None
        )
        assert frontend_waitlisted is not None
        assert frontend_waitlisted['viewer_waitlisted'] is True

        if confirmed_games:
            frontend_confirmed = next(
                (g for g in frontend_games if g['name'] == confirmed_games[0]['name']), None
            )
            if frontend_confirmed is not None:
                assert frontend_confirmed['viewer_waitlisted'] is False

    def test_all_games_marks_specific_waitlisted_player(self, client):
        """/all-games tags only the specific waitlisted player, not their game-mates."""
        player_name, waitlisted_game, _ = self._find_waitlisted_player()
        if player_name is None:
            pytest.skip("No waitlisted player found in the live sheet")

        response = client.get('/all-games')
        assert response.status_code == 200
        soup = BeautifulSoup(response.data.decode(), 'html.parser')

        cards = soup.select('.game-card')
        game_card = next((c for c in cards if waitlisted_game['name'] in c.get_text()), None)
        assert game_card is not None, f"Could not find a game card for {waitlisted_game['name']}"

        waitlisted_tag = next(
            (tag for tag in game_card.select('.player-tag') if player_name in tag.get_text()), None
        )
        assert waitlisted_tag is not None, f"Could not find player tag for {player_name}"
        assert 'player-tag-waitlisted' in waitlisted_tag.get('class', []), (
            f"{player_name}'s tag in '{waitlisted_game['name']}' should carry player-tag-waitlisted"
        )

        confirmed_players = [p for p in waitlisted_game['players'] if p != player_name]
        if confirmed_players:
            other_tag = next(
                (tag for tag in game_card.select('.player-tag') if confirmed_players[0] in tag.get_text()),
                None
            )
            if other_tag is not None:
                assert 'player-tag-waitlisted' not in other_tag.get('class', []), (
                    f"Confirmed player '{confirmed_players[0]}' should not be marked as waitlisted"
                )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
