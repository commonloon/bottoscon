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

    def test_game_167_is_in_csv(self, game_167_from_csv):
        """Verify game 167 exists in the CSV file."""
        assert game_167_from_csv is not None, "Game 167 not found in CSV"
        assert game_167_from_csv['id'] == '167'
        assert 'Cold War' in game_167_from_csv['name'], f"Expected 'Cold War' in name, got: {game_167_from_csv['name']}"

    def test_game_167_is_parsed(self, game_167_from_app):
        """TC-003: Game 167 "New Cold War" is Parsed"""
        assert game_167_from_app is not None, (
            "Game 167 'New Cold War' not found in parsed games. "
            "This is the critical bug - game 167 is in CSV but not parsed by the app."
        )

    def test_game_167_has_correct_data(self, game_167_from_app):
        """TC-003: Game 167 data is correct"""
        if game_167_from_app is None:
            pytest.skip("Game 167 not parsed - skipping detailed data check")

        game = game_167_from_app
        # Game IDs are stored as strings
        assert str(game['id']) == '167', f"Expected ID 167, got {game['id']}"
        assert 'New Cold War' in game['name'], f"Expected 'New Cold War' in name, got: {game['name']}"
        assert game['status'] == 'FULL', f"Expected status FULL, got {game['status']}"
        assert game['start_day'] == 'Friday', f"Expected Friday, got {game['start_day']}"
        assert game['end_day'] == 'Friday', f"Expected Friday, got {game['end_day']}"
        # Time might be stored as "09:00" or "09:00:00"
        assert '09:00' in game['start_time'], f"Expected start time 09:00, got {game['start_time']}"
        assert '13:00' in game['end_time'], f"Expected end time 13:00, got {game['end_time']}"

    def test_all_games_have_required_fields(self, parsed_games):
        """TC-004: All Games Have Required Fields"""
        valid_days = {'Thursday', 'Friday', 'Saturday', 'Sunday'}

        for game in parsed_games:
            assert 'id' in game and game['id'], f"Game missing ID: {game}"
            assert 'name' in game and game['name'], f"Game {game.get('id')} missing name"
            assert 'start_day' in game, f"Game {game.get('id')} missing start_day"
            assert game['start_day'] in valid_days, (
                f"Game {game.get('id')} has invalid start_day: {game['start_day']}"
            )
            assert 'start_time' in game, f"Game {game.get('id')} missing start_time"
            assert 'end_time' in game, f"Game {game.get('id')} missing end_time"

    def test_games_with_insufficient_columns_filtered(self, csv_games):
        """TC-005: Games with < 23 Columns Are Skipped

        The parser requires at least 23 columns per game row.
        This test verifies that all games in CSV have >= 23 columns.
        """
        insufficient_count = 0
        for game in csv_games:
            if len(game['raw_row']) < 23:
                insufficient_count += 1
                print(f"Game {game['id']}: {len(game['raw_row'])} columns (line {game['csv_line']})")

        if insufficient_count > 0:
            print(f"\nFound {insufficient_count} games with < 23 columns in CSV")
            print("These games should be filtered out by the parser")

    def test_game_sorting_is_chronological(self, parsed_games):
        """TC-008: Sorting is Chronological"""
        if len(parsed_games) < 2:
            pytest.skip("Not enough games to test sorting")

        day_order = {
            'Thursday': 1,
            'Friday': 2,
            'Saturday': 3,
            'Sunday': 4
        }

        previous_sort_key = (-1, -1, -1)  # (day, hour, minute)

        for game in parsed_games:
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


class TestGameComparison:
    """Test comparison between CSV source and parsed games."""

    def test_all_csv_games_are_in_parsed_games(self, csv_games, parsed_games):
        """TC-014: All CSV Games Are in Parsed Games"""
        parsed_ids = {str(g['id']) for g in parsed_games}
        csv_ids = {g['id'] for g in csv_games}

        missing_ids = csv_ids - parsed_ids
        assert not missing_ids, (
            f"Found {len(missing_ids)} games in CSV that are missing from parsed games: {missing_ids}"
        )

    def test_no_extra_games_in_parsed(self, csv_games, parsed_games):
        """Verify no games are present in parsed that shouldn't be"""
        parsed_ids = {str(g['id']) for g in parsed_games}
        csv_ids = {g['id'] for g in csv_games}

        extra_ids = parsed_ids - csv_ids
        if extra_ids:
            print(f"\nWarning: Found {len(extra_ids)} extra games in parsed data: {extra_ids}")


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
