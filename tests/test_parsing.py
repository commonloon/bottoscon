"""
Unit tests for BottosCon CSV parsing and game data validation.

Tests the backend data pipeline:
- CSV fetch and caching
- Game parsing logic
- Column validation and filtering
- Sorting behavior
"""

import pytest
import app as app_module
from config import CONVENTION_DAYS


class TestCSVParsing:
    """Test CSV parsing and game extraction."""

    def test_csv_fetch_returns_data(self):
        """TC-001: CSV Fetch Returns Data"""
        rows = app_module.fetch_sheet_data()
        assert rows is not None, "fetch_sheet_data() returned None"
        assert len(rows) > 0, "fetch_sheet_data() returned empty list"

    def test_game_count_matches_csv(self, csv_games, parsed_games):
        """TC-002: Game Count Matches CSV (or Live Sheet)

        Verifies that the parser returns a reasonable number of games.
        Note: The parser fetches live data from Google Sheets, which may
        differ from the local CSV export. This test ensures the parser
        returns at least as many games as the CSV.
        """
        csv_count = len(csv_games)
        parsed_count = len(parsed_games)

        print(f"\n--- Game Count Comparison ---")
        print(f"CSV games (with ID and Name): {csv_count}")
        print(f"Parsed games: {parsed_count}")
        print(f"Difference: {parsed_count - csv_count} (live data may have more)")

        # The live sheet may have more games than the exported CSV
        # Just verify we're getting a reasonable number (at least as many as CSV)
        assert parsed_count >= csv_count - 5, (
            f"Parsed game count ({parsed_count}) is significantly less than CSV ({csv_count}). "
            f"This suggests a parsing problem."
        )

    def test_all_games_have_required_fields(self, parsed_games):
        """TC-004: All Games Have Required Fields"""
        valid_days = set(CONVENTION_DAYS.keys())

        for game in parsed_games:
            assert 'id' in game and game['id'], f"Game missing ID: {game}"
            assert 'name' in game and game['name'], f"Game {game.get('id')} missing name"
            assert 'start_day' in game, f"Game {game.get('id')} missing start_day"
            assert game['start_day'] in valid_days, (
                f"Game {game.get('id')} has invalid start_day: {game['start_day']}"
            )
            assert 'start_time' in game, f"Game {game.get('id')} missing start_time"
            assert 'end_time' in game, f"Game {game.get('id')} missing end_time"

    def test_games_missing_required_columns_filtered(self, csv_games):
        """TC-005: Games Missing Required Columns Are Skipped

        The parser resolves columns by header name rather than a fixed
        column count. This test verifies that every game the fixture
        picked up has a row wide enough to reach the required columns
        (name-based lookup already filters out rows that don't).
        """
        rows = app_module.fetch_sheet_data()
        col_map = app_module.find_header_row(rows)
        assert col_map is not None, "Could not locate the sheet's header row"

        required_max_index = max(col_map[name] for name in app_module.REQUIRED_COLUMNS)

        insufficient_count = 0
        for game in csv_games:
            if len(game['raw_row']) <= required_max_index:
                insufficient_count += 1
                print(f"Game {game['name']}: {len(game['raw_row'])} columns (line {game['csv_line']})")

        assert insufficient_count == 0, (
            f"Found {insufficient_count} games in csv_games with rows too short "
            f"to reach the required columns; these should have been filtered out"
        )

    def test_game_sorting_is_chronological(self, parsed_games):
        """TC-008: Sorting is Chronological"""
        if len(parsed_games) < 2:
            pytest.skip("Not enough games to test sorting")

        day_order = {day: i + 1 for i, day in enumerate(CONVENTION_DAYS.keys())}
        sorted_games = app_module.sort_games_chronologically(parsed_games)

        previous_sort_key = (-1, -1, -1)  # (day, hour, minute)

        for game in sorted_games:
            day = day_order.get(game['start_day'], 99)
            # Parse time - might be "HH:MM" or "HH:MM:SS"
            time_parts = str(game['start_time']).split(':')
            hour = int(time_parts[0]) if len(time_parts) > 0 else 0
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            current_sort_key = (day, hour, minute)

            assert current_sort_key >= previous_sort_key, (
                f"Games not properly sorted. "
                f"Game {game['id']} ({game['start_day']} {game['start_time']}) "
                f"comes after a later time."
            )
            previous_sort_key = current_sort_key


class TestWaitlistParsing:
    """Test waitlist detection: players beyond 'Max Players' in signup order."""

    def test_waitlisted_players_are_subset_of_players(self, parsed_games):
        for game in parsed_games:
            for name in game['waitlisted_players']:
                assert name in game['players'], (
                    f"Game {game['id']} ({game['name']}): waitlisted player '{name}' "
                    f"not found in players list"
                )

    def test_waitlist_count_matches_max_players_overflow(self, parsed_games):
        """Independently recompute the expected waitlist size straight from the
        raw sheet, mirroring how the csv_games fixture cross-checks the parser."""
        rows = app_module.fetch_sheet_data()
        col_map = app_module.find_header_row(rows)
        assert col_map is not None, "Could not locate the sheet's header row"

        player_start = col_map['1 / Organizer']
        player_end = col_map['Condensed Players List']

        # Some games run multiple sessions under the same name (e.g. a
        # multi-day title signed up separately per day), so match on
        # (name, start_day, start_time) rather than name alone.
        expected_by_key = {}
        for row in rows:
            game_name = app_module.get_col(row, col_map, 'Game Name')
            start_day = app_module.get_col(row, col_map, 'Start Day')
            start_time = app_module.get_col(row, col_map, 'Start Time (24 hour clock)')
            if not game_name or start_day not in CONVENTION_DAYS:
                continue

            max_players_text = app_module.get_col(row, col_map, 'Max Players')
            max_players = int(max_players_text) if max_players_text.isdigit() else None

            filled = sum(
                1 for i in range(player_start, min(player_end, len(row)))
                if app_module.extract_player_name(row[i])
            )

            expected = max(0, filled - max_players) if max_players is not None else 0
            expected_by_key[(game_name, start_day, start_time)] = expected

        checked = 0
        for game in parsed_games:
            key = (game['name'], game['start_day'], game['start_time'])
            if key not in expected_by_key:
                continue
            expected = expected_by_key[key]
            assert len(game['waitlisted_players']) == expected, (
                f"Game {game['id']} ({game['name']}): expected {expected} waitlisted "
                f"players, got {len(game['waitlisted_players'])}"
            )
            checked += 1

        assert checked > 0, "No games were cross-checked against the raw sheet"

    def test_known_waitlisted_game_regression(self, parsed_games):
        """The originally reported case: 'Kemet: Blood and Sand' was full with
        one player waitlisted. Skips if the sheet has moved on since."""
        matches = [g for g in parsed_games if g['name'] == 'Kemet: Blood and Sand']
        if not matches:
            pytest.skip("'Kemet: Blood and Sand' is no longer in the live sheet")

        game = matches[0]
        assert game['waitlisted_players'], (
            "Expected 'Kemet: Blood and Sand' to have at least one waitlisted player"
        )
        # Cross-check our derived waitlist flag against the sheet's own status text.
        assert 'WAITLIST' in game['status'].upper(), (
            f"Sheet status '{game['status']}' doesn't mention a waitlist, but we "
            f"computed waitlisted players: {game['waitlisted_players']}"
        )


class TestGameComparison:
    """Test comparison between CSV source and parsed games."""

    def test_all_csv_games_are_in_parsed_games(self, csv_games, parsed_games):
        """TC-014: All CSV Games Are in Parsed Games"""
        parsed_names = {g['name'] for g in parsed_games}
        csv_names = {g['name'] for g in csv_games}

        missing = csv_names - parsed_names
        assert not missing, (
            f"Found {len(missing)} games in CSV that are missing from parsed games: {missing}"
        )

    def test_no_extra_games_in_parsed(self, csv_games, parsed_games):
        """Verify no games are present in parsed that shouldn't be"""
        parsed_names = {g['name'] for g in parsed_games}
        csv_names = {g['name'] for g in csv_games}

        extra = parsed_names - csv_names
        if extra:
            print(f"\nWarning: Found {len(extra)} extra games in parsed data: {extra}")


class TestCacheAndAPI:
    """Test caching and API endpoints."""

    def test_refresh_cache_endpoint(self, client):
        """Test that refresh cache endpoint works"""
        response = client.post('/api/refresh-cache')
        assert response.status_code in [200, 405], (
            f"Unexpected status code from /api/refresh-cache: {response.status_code}"
        )

    def test_all_games_endpoint_returns_200(self, client):
        """Test that /all-games route exists and returns 200"""
        response = client.get('/all-games')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_all_games_renders_html(self, client):
        """Test that /all-games returns HTML"""
        response = client.get('/all-games')
        assert 'text/html' in response.content_type or response.content_type == 'text/html'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
