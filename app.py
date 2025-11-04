"""
BottosCon Personal Schedule Viewer
Reads game signups from Google Sheets and generates personalized schedules for each player.
"""
import csv
import io
import re
from collections import defaultdict
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests

app = Flask(__name__)

# Google Sheets CSV export URL
SIGNUP_SHEET_URL = "https://docs.google.com/spreadsheets/d/1GZX_Nxs-eWcV9JRYwVO4jH8jEnMJvGDlwKevCtyAkjg/export?format=csv&gid=1882561680"

# Cache for sheet data (refresh every hour)
_cache = {
    'data': None,
    'timestamp': None
}
CACHE_DURATION = 3600  # 1 hour


def fetch_sheet_data(force_refresh=False):
    """Fetch and cache the signup sheet data"""
    import time
    now = time.time()

    # Return cached data if still fresh (unless force refresh)
    if not force_refresh and _cache['data'] and _cache['timestamp'] and (now - _cache['timestamp']) < CACHE_DURATION:
        return _cache['data']

    # Fetch fresh data
    response = requests.get(SIGNUP_SHEET_URL, timeout=10)
    response.raise_for_status()

    # Parse CSV
    csv_data = response.text
    reader = csv.reader(io.StringIO(csv_data))
    rows = list(reader)

    # Cache it
    _cache['data'] = rows
    _cache['timestamp'] = now

    return rows


def extract_player_name(player_text):
    """
    Extract clean player name from text like 'Rob Bottos <bottosconpayments@gmail.com>'
    Returns just 'Rob Bottos'
    """
    if not player_text or player_text in ['N/A', '']:
        return None

    # Remove email in angle brackets
    player_text = re.sub(r'\s*<[^>]+>', '', player_text).strip()
    return player_text if player_text else None


def parse_games_and_players():
    """
    Parse the sheet and return:
    - games: list of game dicts
    - player_games: dict mapping player name to list of their games
    """
    rows = fetch_sheet_data()

    # Skip first 2 header rows
    data_rows = rows[2:]

    games = []
    player_games = defaultdict(list)

    for row in data_rows:
        if len(row) < 23:  # Skip incomplete rows
            continue

        game_id = row[0].strip() if len(row) > 0 else ''
        if not game_id:  # Skip rows without game ID
            continue

        game = {
            'id': game_id,
            'name': row[1].strip() if len(row) > 1 else '',
            'status': row[2].strip() if len(row) > 2 else '',
            'start_day': row[11].strip() if len(row) > 11 else '',
            'start_time': row[12].strip() if len(row) > 12 else '',
            'end_day': row[13].strip() if len(row) > 13 else '',
            'end_time': row[14].strip() if len(row) > 14 else '',
            'duration': row[19].strip() if len(row) > 19 else '',
            'table': row[20].strip() if len(row) > 20 else '',
            'players': []
        }

        # Extract players from columns 23-31 (player slot columns)
        for i in range(23, min(32, len(row))):
            player_name = extract_player_name(row[i])
            if player_name:
                game['players'].append(player_name)
                player_games[player_name].append(game)

        if game['name']:  # Only add games with names
            games.append(game)

    return games, dict(player_games)


def sort_games_chronologically(games):
    """Sort games by day and time"""
    day_order = {
        'Thursday': 1,
        'Friday': 2,
        'Saturday': 3,
        'Sunday': 4
    }

    def sort_key(game):
        day = day_order.get(game['start_day'], 99)
        # Parse time (handle formats like "09:00" or "09:00:00")
        time_str = game['start_time'].split(':')
        hour = int(time_str[0]) if time_str and time_str[0].isdigit() else 0
        minute = int(time_str[1]) if len(time_str) > 1 and time_str[1].isdigit() else 0
        return (day, hour, minute)

    return sorted(games, key=sort_key)


@app.route('/')
def index():
    """Home page showing all players"""
    try:
        _, player_games = parse_games_and_players()
        players = sorted(player_games.keys())
        return render_template('index.html', players=players, player_count=len(players))
    except Exception as e:
        return f"Error loading data: {str(e)}", 500


@app.route('/schedule/<player_name>')
def player_schedule(player_name):
    """Show schedule for a specific player"""
    try:
        _, player_games = parse_games_and_players()

        if player_name not in player_games:
            return f"Player '{player_name}' not found", 404

        games = sort_games_chronologically(player_games[player_name])
        return render_template('schedule.html', player_name=player_name, games=games)
    except Exception as e:
        return f"Error loading schedule: {str(e)}", 500


@app.route('/all-games')
def all_games():
    """Show all games"""
    try:
        games, _ = parse_games_and_players()
        games = sort_games_chronologically(games)
        return render_template('all_games.html', games=games)
    except Exception as e:
        return f"Error loading games: {str(e)}", 500


@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache():
    """Force refresh the cache"""
    try:
        fetch_sheet_data(force_refresh=True)
        return jsonify({'success': True, 'message': 'Schedule data refreshed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error refreshing: {str(e)}'}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
