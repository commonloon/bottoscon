"""
BottosCon Personal Schedule Viewer
Reads game signups from Google Sheets and generates personalized schedules for each player.
"""
import csv
import io
import re
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
from flask import Flask, render_template, request, redirect, url_for, jsonify, g
import requests
from config import CONVENTION_START_DATE, CONVENTION_DAYS

app = Flask(__name__)

# Crawlers to block regardless of robots.txt compliance.
# Matched case-insensitively as substrings of the User-Agent header.
BLOCKED_AGENTS = [
    # OpenAI
    'gptbot', 'chatgpt-user', 'oai-searchbot',
    # Anthropic
    'anthropic-ai', 'claudebot', 'claude-web',
    # Other AI training crawlers
    'ccbot',            # Common Crawl (primary AI training corpus)
    'cohere-ai',
    'bytespider',       # ByteDance
    'diffbot',
    'perplexitybot',
    'amazonbot',
    'meta-externalagent',
    'facebookbot',
    'applebot-extended',
    # Aggressive SEO / index crawlers that ignore robots.txt
    'yandexbot',
    'yandex.com/bots',
    'semrushbot',
    'ahrefsbot',
    'mj12bot',
    'dotbot',
    'blexbot',
    'petalbot',
    'dataforseobot',
]


@app.before_request
def block_crawlers():
    ua = request.headers.get('User-Agent', '').lower()
    if any(agent in ua for agent in BLOCKED_AGENTS):
        return 'Forbidden', 403


@app.route('/robots.txt')
def robots_txt():
    # Disallow all crawlers. Well-behaved crawlers will respect this;
    # the before_request hook above handles those that don't.
    return 'User-agent: *\nDisallow: /\n', 200, {'Content-Type': 'text/plain'}


# Google Sheets CSV export URL
SIGNUP_SHEET_URL = "https://docs.google.com/spreadsheets/d/1ixN-vWncVfetlDLyX5aNPPc7PFpr0412gXTr2EvQBgM/export?format=csv"

# Cache for sheet data (refresh every hour)
_cache = {
    'data': None,
    'timestamp': None
}
CACHE_DURATION = 3600  # 1 hour


def get_convention_date(day_name):
    """
    Convert a day name (e.g., 'Thursday') to an actual date based on CONVENTION_START_DATE.
    Returns ISO format date string (YYYY-MM-DD).
    """
    offset = CONVENTION_DAYS.get(day_name, 0)
    actual_date = CONVENTION_START_DATE + timedelta(days=offset)
    return actual_date.strftime('%Y-%m-%d')


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

    # Google's CSV export doesn't declare a charset, so requests falls back
    # to ISO-8859-1 and mangles non-ASCII characters (curly quotes, em
    # dashes, etc.) in game names. The export is always UTF-8.
    response.encoding = 'utf-8'

    # Parse CSV
    csv_data = response.text
    reader = csv.reader(io.StringIO(csv_data))
    rows = list(reader)

    # Cache it
    _cache['data'] = rows
    _cache['timestamp'] = now

    return rows


REQUIRED_COLUMNS = [
    'Game Name',
    'Start Day',
    'Start Time (24 hour clock)',
    'End Time (24 hour clock)',
    '1 / Organizer',
    'Condensed Players List',
]


def build_column_map(header_row):
    """
    Map header name -> index of its first occurrence in the row.
    The signup sheet reuses some header names (e.g. multiple 'Start'/'End'
    columns for per-day time ranges), so later duplicates are ignored;
    callers that need those columns use positional ranges instead.
    """
    col_map = {}
    for i, name in enumerate(header_row):
        name = (name or '').strip()
        if name and name not in col_map:
            col_map[name] = i
    return col_map


def get_col(row, col_map, name, default=''):
    """Look up a column by header name, tolerating short/missing rows."""
    idx = col_map.get(name)
    if idx is None or idx >= len(row):
        return default
    return row[idx].strip()


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


def find_header_row(rows):
    """
    Locate the header row within the first few rows of the sheet.
    Organizers prefix the header with a title/instructions row, so the
    header isn't reliably at a fixed index - find the first row that looks
    like one instead.
    """
    for row in rows[:5]:
        col_map = build_column_map(row)
        if 'Game Name' in col_map and '1 / Organizer' in col_map:
            return col_map
    return None


def parse_games_and_players():
    """
    Parse the sheet and return:
    - games: list of game dicts
    - player_games: dict mapping player name to list of their games
    """
    rows = fetch_sheet_data()

    col_map = find_header_row(rows)
    if col_map is None:
        raise ValueError("Could not find the signup sheet's header row (expected 'Game Name' and '1 / Organizer' columns)")

    missing = [name for name in REQUIRED_COLUMNS if name not in col_map]
    if missing:
        raise ValueError(f"Signup sheet is missing expected columns: {missing}")

    player_start = col_map['1 / Organizer']
    player_end = col_map['Condensed Players List']

    games = []
    player_games = defaultdict(list)
    game_counter = 1

    for row in rows:
        start_day = get_col(row, col_map, 'Start Day')
        if start_day not in set(CONVENTION_DAYS.keys()):
            continue

        game_name = get_col(row, col_map, 'Game Name')
        if not game_name:
            continue

        status = get_col(row, col_map, 'Status')
        if not status:
            slots_open = get_col(row, col_map, 'Player Slots Still Open')
            status = 'FULL' if slots_open == '0' else 'OPEN'

        game = {
            'id': get_col(row, col_map, 'Game ID', default=str(game_counter)),
            'name': game_name,
            'status': status,
            'status_class': status.split()[0].upper() if status else 'UNKNOWN',
            'start_day': start_day,
            'start_time': get_col(row, col_map, 'Start Time (24 hour clock)'),
            'end_day': get_col(row, col_map, 'End Day') or start_day,
            'end_time': get_col(row, col_map, 'End Time (24 hour clock)'),
            'duration': get_col(row, col_map, 'Duration (h:m)'),
            'table': get_col(row, col_map, 'Table'),
            'description': get_col(row, col_map, 'Game Description / Notes'),
            'players': [],
            'waitlisted_players': []
        }

        max_players_text = get_col(row, col_map, 'Max Players')
        max_players = int(max_players_text) if max_players_text.isdigit() else None

        filled_slots = 0
        for i in range(player_start, min(player_end, len(row))):
            player_name = extract_player_name(row[i])
            if player_name:
                filled_slots += 1
                game['players'].append(player_name)
                player_games[player_name].append(game)
                if max_players is not None and filled_slots > max_players:
                    game['waitlisted_players'].append(player_name)

        games.append(game)
        game_counter += 1

    return games, dict(player_games)


def annotate_viewer_waitlist(games, player_name):
    """Shallow-copy each game dict, tagging whether player_name is waitlisted for it."""
    return [
        {**game, 'viewer_waitlisted': player_name in game.get('waitlisted_players', [])}
        for game in games
    ]


def sort_games_chronologically(games):
    """Sort games by day and time"""
    day_order = {day: i + 1 for i, day in enumerate(CONVENTION_DAYS.keys())}

    def sort_key(game):
        day = day_order.get(game['start_day'], 99)
        # Parse time (handle formats like "09:00" or "09:00:00")
        time_str = game['start_time'].split(':')
        hour = int(time_str[0]) if time_str and time_str[0].isdigit() else 0
        minute = int(time_str[1]) if len(time_str) > 1 and time_str[1].isdigit() else 0
        return (day, hour, minute)

    return sorted(games, key=sort_key)


FAVOURITES_COOKIE = 'bottoscon_favourites'
FAVOURITES_MAX_AGE = 60 * 60 * 24 * 180  # ~6 months


def set_favourites_cookie(response, names):
    """Cookie values can't contain spaces/commas, and player names have both."""
    response.set_cookie(
        FAVOURITES_COOKIE,
        ','.join(quote(name) for name in names),
        max_age=FAVOURITES_MAX_AGE
    )


def get_favourites():
    """
    Read the favourites cookie, pruned against the current convention's
    roster. A 6-month cookie can outlive a convention (BottosCon swaps
    signup sheets between conventions), so a favourited name with no
    current signups is dropped - that's the only "still relevant" signal
    this app has, since it has no attendee roster independent of game
    signups. Memoized on `g` so the context processor and any route reading
    favourites in the same request see (and agree on) the same result.
    """
    if not hasattr(g, 'favourites'):
        raw = request.cookies.get(FAVOURITES_COOKIE, '')
        raw_names = [unquote(name) for name in raw.split(',') if name]
        try:
            _, player_games = parse_games_and_players()
            valid_players = set(player_games.keys())
            g.favourites = [name for name in raw_names if name in valid_players]
        except Exception:
            # Don't wipe favourites over a transient sheet-fetch failure.
            g.favourites = raw_names
        g.favourites_dirty = (g.favourites != raw_names)
    return g.favourites


@app.context_processor
def inject_favourites():
    return {'favourites': get_favourites()}


@app.after_request
def persist_favourites_cookie(response):
    if getattr(g, 'favourites_dirty', False):
        set_favourites_cookie(response, g.favourites)
    return response


@app.route('/api/favourites/toggle/<player_name>', methods=['POST'])
def toggle_favourite(player_name):
    """Toggle player_name's favourited status. Cookie write happens in after_request."""
    favourites = get_favourites()
    if player_name in favourites:
        favourites.remove(player_name)
        favourited = False
    else:
        favourites.append(player_name)
        favourited = True
    g.favourites_dirty = True
    return jsonify({'success': True, 'favourited': favourited})


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
        games = annotate_viewer_waitlist(games, player_name)
        return render_template('schedule.html', player_name=player_name, games=games)
    except Exception as e:
        return f"Error loading schedule: {str(e)}", 500


@app.route('/calendar/<player_name>')
def player_calendar(player_name):
    """Show calendar view for a specific player"""
    try:
        _, player_games = parse_games_and_players()

        if player_name not in player_games:
            return f"Player '{player_name}' not found", 404

        games = sort_games_chronologically(player_games[player_name])
        games = annotate_viewer_waitlist(games, player_name)
        return render_template('calendar.html',
                             player_name=player_name,
                             games=games,
                             get_convention_date=get_convention_date,
                             convention_days=list(CONVENTION_DAYS.keys()))
    except Exception as e:
        return f"Error loading calendar: {str(e)}", 500


@app.route('/all-games')
def all_games():
    """Show all games"""
    try:
        games, _ = parse_games_and_players()
        games = sort_games_chronologically(games)
        return render_template('all_games.html', games=games)
    except Exception as e:
        return f"Error loading games: {str(e)}", 500


@app.route('/calendar/all-games')
def all_games_calendar():
    """Show calendar view for all games"""
    try:
        games, _ = parse_games_and_players()
        games = sort_games_chronologically(games)
        return render_template('all_games_calendar.html',
                             games=games,
                             get_convention_date=get_convention_date,
                             convention_days=list(CONVENTION_DAYS.keys()))
    except Exception as e:
        return f"Error loading calendar: {str(e)}", 500


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
