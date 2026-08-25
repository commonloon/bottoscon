"""
Tests for the favourites cookie system: add/remove toggling, and pruning
stale (no-longer-registered) names against the current convention's roster.
"""

from urllib.parse import quote

import pytest
from bs4 import BeautifulSoup
import app as app_module


def favourites_bar_names(html):
    """Parse the rendered favourites chips out of the page (decodes HTML
    entities, e.g. an apostrophe rendered as &#39;, unlike a raw substring check)."""
    soup = BeautifulSoup(html, 'html.parser')
    bar = soup.select_one('div.favourites-bar')
    if bar is None:
        return []
    return [a.get_text(strip=True) for a in bar.select('.favourite-chip a')]


class TestFavouritesToggle:
    """Test adding/removing a player via the toggle endpoint."""

    def test_no_cookie_means_no_favourites(self, client):
        response = client.get('/')
        assert response.status_code == 200
        assert favourites_bar_names(response.data.decode()) == []

    def test_toggle_adds_then_removes(self, client):
        _, player_games = app_module.parse_games_and_players()
        if not player_games:
            pytest.skip("No players in parsed games")
        player_name = list(player_games.keys())[0]

        add_response = client.post(f'/api/favourites/toggle/{player_name}')
        assert add_response.status_code == 200
        add_data = add_response.get_json()
        assert add_data['success'] is True
        assert add_data['favourited'] is True
        assert 'bottoscon_favourites' in add_response.headers.get('Set-Cookie', '')

        index_response = client.get('/')
        assert player_name in favourites_bar_names(index_response.data.decode())

        remove_response = client.post(f'/api/favourites/toggle/{player_name}')
        assert remove_response.status_code == 200
        remove_data = remove_response.get_json()
        assert remove_data['favourited'] is False

        index_response_2 = client.get('/')
        assert favourites_bar_names(index_response_2.data.decode()) == []

    def test_favourite_name_with_apostrophe_round_trips(self, client):
        """Names like "Conor O'Sullivan" must survive cookie quoting/unquoting
        (and Jinja's HTML-entity escaping of the apostrophe) intact."""
        _, player_games = app_module.parse_games_and_players()
        apostrophe_names = [name for name in player_games if "'" in name]
        if not apostrophe_names:
            pytest.skip("No player with an apostrophe in their name in the live sheet")
        player_name = apostrophe_names[0]

        response = client.post(f'/api/favourites/toggle/{player_name}')
        assert response.status_code == 200
        assert response.get_json()['favourited'] is True

        index_html = client.get('/').data.decode()
        assert player_name in favourites_bar_names(index_html)


class TestFavouritesPruning:
    """Test that favourites not in the current convention's roster get dropped."""

    def test_stale_favourite_is_pruned(self, client):
        _, player_games = app_module.parse_games_and_players()
        if not player_games:
            pytest.skip("No players in parsed games")
        real_player = list(player_games.keys())[0]
        fake_player = 'Definitely Not A Real Player Zzz'

        cookie_value = f"{quote(real_player)},{quote(fake_player)}"
        client.set_cookie('bottoscon_favourites', cookie_value)

        response = client.get('/')
        chip_names = favourites_bar_names(response.data.decode())
        assert real_player in chip_names
        assert fake_player not in chip_names

        set_cookie_header = response.headers.get('Set-Cookie', '')
        assert quote(real_player) in set_cookie_header
        assert quote(fake_player) not in set_cookie_header

    def test_all_valid_favourites_not_rewritten_unnecessarily(self, client):
        """If nothing needs pruning, the response shouldn't set a new cookie."""
        _, player_games = app_module.parse_games_and_players()
        if not player_games:
            pytest.skip("No players in parsed games")
        real_player = list(player_games.keys())[0]

        client.set_cookie('bottoscon_favourites', quote(real_player))
        response = client.get('/')
        assert 'Set-Cookie' not in response.headers


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
