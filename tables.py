"""
Table availability for BottosCon.

Reads two tabs of the organizers' "Organize a Game" workbook:
  - Table Usage: column A lists every table (rows from NON_GENERAL_TABLES_START,
    e.g. ASL1, downwards are excluded) and column B is the table type
    (e.g. "2M" = two medium tables joined).
  - Games: the "Assigned Table" column is authoritative for who has which
    table, and the start/end day+time columns give the booked interval.

SECURITY: that workbook may be editable by anyone holding its link, and the
CSV export URL contains the same document id as the edit link. The URLs come
only from environment variables, are never rendered into a page, and are
never logged (requests' exception messages embed the URL, so only the
exception class name is logged).
"""
import csv
import io
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from config import (
    CONVENTION_START_DATE,
    CONVENTION_DAYS,
    CONVENTION_HOURS,
    CONVENTION_TZ,
    NON_GENERAL_TABLES_START,
    TABLE_CACHE_SECONDS,
)

logger = logging.getLogger(__name__)

TABLE_USAGE_URL_ENV = 'TABLE_USAGE_CSV_URL'
GAMES_URL_ENV = 'ORGANIZER_GAMES_CSV_URL'


class TableDataError(Exception):
    """Raised when table data is missing or unparseable. Messages never contain URLs."""


@dataclass(frozen=True)
class Table:
    id: str
    type: str


@dataclass(frozen=True)
class Booking:
    table_id: str
    game_id: str
    game_name: str
    organizer: str
    start: datetime
    end: datetime

    @property
    def start_label(self):
        return self.start.strftime('%a %H:%M')

    @property
    def end_label(self):
        return self.end.strftime('%a %H:%M')

    @property
    def multi_day(self):
        return self.start.date() != self.end.date()


@dataclass
class TableData:
    tables: list
    bookings: dict = field(default_factory=dict)  # table id -> [Booking] sorted by start
    fetched_at: float = 0.0

    def table(self, table_id):
        wanted = (table_id or '').strip().upper()
        for t in self.tables:
            if t.id.upper() == wanted:
                return t
        return None

    def bookings_for(self, table):
        return self.bookings.get(table.id, [])

    @property
    def types(self):
        return sorted({t.type for t in self.tables if t.type})


# ----------------------------------------------------------------- parsing

def _col_map(header_row):
    cols = {}
    for i, name in enumerate(header_row):
        name = (name or '').replace('\n', ' ').strip()
        if name and name not in cols:  # first occurrence wins (Start/End repeat per day)
            cols[name] = i
    return cols


def _get(row, cols, name):
    idx = cols.get(name)
    if idx is None or idx >= len(row):
        return ''
    return row[idx].strip()


_TIME_RE = re.compile(r'^(\d{1,2}):(\d{2})(?::\d{2})?$')


def parse_clock(text):
    """'09:30' or '09:30:00' -> (9, 30), else None."""
    m = _TIME_RE.match((text or '').strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def day_date(day_name):
    return (CONVENTION_START_DATE + timedelta(days=CONVENTION_DAYS[day_name])).replace(
        hour=0, minute=0, second=0, microsecond=0)


def _at(day_name, clock):
    return day_date(day_name).replace(hour=clock[0], minute=clock[1])


def clean_organizer(text):
    """'Jane Doe <jane@example.com>' -> 'Jane Doe'. Emails must never be displayed."""
    return re.sub(r'\s*<[^>]*>', '', text or '').strip()


def parse_tables(rows):
    """Table list from the Table Usage tab. Stops at the first non-general table or blank."""
    header_idx = None
    for i, row in enumerate(rows[:10]):
        if row and row[0].strip().lower() == 'table':
            header_idx = i
            break
    if header_idx is None:
        raise TableDataError("Table Usage: no row with 'Table' in column A (wrong tab/gid?)")

    stop = NON_GENERAL_TABLES_START.strip().upper()
    tables = []
    for row in rows[header_idx + 1:]:
        name = row[0].strip() if row else ''
        if not name or name.upper() == stop:
            break
        tables.append(Table(id=name, type=row[1].strip() if len(row) > 1 else ''))
    if not tables:
        raise TableDataError('Table Usage: header found but no tables listed under it')
    return tables


def parse_bookings(rows, tables):
    """Bookings (keyed by table id) from the Games tab, using 'Assigned Table'."""
    known = {t.id.upper(): t.id for t in tables}

    header_idx, cols = None, None
    for i, row in enumerate(rows[:10]):
        candidate = _col_map(row)
        if 'Game ID' in candidate and 'Assigned Table' in candidate:
            header_idx, cols = i, candidate
            break
    if cols is None:
        raise TableDataError("Games: no header row with 'Game ID' and 'Assigned Table' (wrong tab/gid?)")
    required = ['Game name', 'Organizer', 'Start Day', 'Start Time (24 hour clock)',
                'End Time (24 hour clock)']
    missing = [name for name in required if name not in cols]
    if missing:
        raise TableDataError(f'Games sheet is missing expected columns: {missing}')

    bookings = {}
    skipped = 0
    for row in rows[header_idx + 1:]:
        table_id = known.get(_get(row, cols, 'Assigned Table').upper())
        if table_id is None:
            continue  # unassigned, cancelled, or a table not open for general gaming
        start_day = _get(row, cols, 'Start Day')
        end_day = _get(row, cols, 'End Day') or start_day
        start_clock = parse_clock(_get(row, cols, 'Start Time (24 hour clock)'))
        end_clock = parse_clock(_get(row, cols, 'End Time (24 hour clock)'))
        if (start_day not in CONVENTION_DAYS or end_day not in CONVENTION_DAYS
                or start_clock is None or end_clock is None):
            skipped += 1
            continue
        start, end = _at(start_day, start_clock), _at(end_day, end_clock)
        if end <= start:
            skipped += 1
            continue
        bookings.setdefault(table_id, []).append(Booking(
            table_id=table_id,
            game_id=_get(row, cols, 'Game ID'),
            game_name=_get(row, cols, 'Game name') or '(unnamed game)',
            organizer=clean_organizer(_get(row, cols, 'Organizer')),
            start=start,
            end=end,
        ))
    if skipped:
        logger.warning('%d table assignment(s) skipped: unreadable day/time', skipped)
    for lst in bookings.values():
        lst.sort(key=lambda b: (b.start, b.end))
    return bookings


# ----------------------------------------------------------------- fetching

_cache = {'data': None, 'timestamp': None}
_lock = threading.Lock()


_SHEET_LINK_RE = re.compile(r'^https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)')


def csv_export_url(url):
    """
    Accept either a CSV export link or the link copied from the browser's
    address bar (".../edit?gid=123#gid=123", which returns the Sheets web page,
    not data) and return the CSV export URL for that document and tab.
    """
    url = url.strip()
    doc = _SHEET_LINK_RE.match(url)
    if not doc or 'format=csv' in url:
        return url
    gid = re.search(r'gid=(\d+)', url)
    export = f'https://docs.google.com/spreadsheets/d/{doc.group(1)}/export?format=csv'
    return f'{export}&gid={gid.group(1)}' if gid else export


def _download_csv(url, label='sheet'):
    response = requests.get(csv_export_url(url), timeout=10)
    response.raise_for_status()
    response.encoding = 'utf-8'
    text = response.text
    if 'html' in response.headers.get('Content-Type', '').lower() or text.lstrip().startswith('<'):
        # Google serves a sign-in/error web page (HTTP 200) when the sheet isn't
        # shared for link access, or the URL isn't an /export?format=csv URL.
        raise TableDataError(f'{label}: got a web page instead of CSV '
                             '(sheet not shared for link access, or URL is not a CSV export link)')
    return list(csv.reader(io.StringIO(text)))


def is_configured():
    return bool(os.environ.get(TABLE_USAGE_URL_ENV) and os.environ.get(GAMES_URL_ENV))


def clear_cache():
    with _lock:
        _cache['timestamp'] = None


def get_table_data(force=False):
    """
    Cached table data. Refreshed after TABLE_CACHE_SECONDS (short, because
    attendees reserve tables by editing the sheet). If a refresh fails, the
    last good data is served; if there is none, TableDataError is raised.
    """
    with _lock:
        now = time.time()
        fresh = (_cache['data'] is not None and _cache['timestamp'] is not None
                 and now - _cache['timestamp'] < TABLE_CACHE_SECONDS)
        if fresh and not force:
            return _cache['data']

        usage_url = os.environ.get(TABLE_USAGE_URL_ENV)
        games_url = os.environ.get(GAMES_URL_ENV)
        if not usage_url or not games_url:
            raise TableDataError('Table sheet URLs are not configured')
        try:
            tables = parse_tables(_download_csv(usage_url, 'Table Usage'))
            data = TableData(tables=tables,
                             bookings=parse_bookings(_download_csv(games_url, 'Games'), tables),
                             fetched_at=now)
        except Exception as e:
            # TableDataError messages are written by this module and never contain
            # a URL, so they are safe to log. Anything else (e.g. requests errors)
            # embeds the sheet URL, so only the class name is logged.
            detail = f': {e}' if isinstance(e, TableDataError) else ''
            logger.error('Table data refresh failed: %s%s', type(e).__name__, detail)
            if _cache['data'] is not None:
                return _cache['data']
            raise TableDataError('Table data is unavailable') from None
        _cache['data'], _cache['timestamp'] = data, now
        return data


# ----------------------------------------------------------------- availability

def convention_now():
    """Current wall-clock time in the convention's time zone, as a naive datetime."""
    return datetime.now(ZoneInfo(CONVENTION_TZ)).replace(tzinfo=None, microsecond=0)


def as_of_label(timestamp):
    """HH:MM in the convention's time zone for a time.time() value."""
    return datetime.fromtimestamp(timestamp, ZoneInfo(CONVENTION_TZ)).strftime('%H:%M')


def day_names():
    return list(CONVENTION_DAYS)


def todays_convention_day(now):
    """The convention day name if `now` falls on one, else None."""
    for name in day_names():
        if day_date(name).date() == now.date():
            return name
    return None


def default_day(now):
    """Today if it's a convention day; otherwise the nearest end of the convention."""
    names = day_names()
    today = todays_convention_day(now)
    if today:
        return today
    return names[0] if now < day_date(names[0]) else names[-1]


def fmt_min(minutes):
    """Minutes after midnight -> 'HH:MM' (1440 -> '24:00')."""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def fmt_duration(minutes):
    h, m = divmod(minutes, 60)
    if h and m:
        return f'{h}h {m:02d}m'
    return f'{h}h' if h else f'{m}m'


def parse_minutes(text):
    """'14:30' -> 870; '24:00' allowed. None if invalid."""
    m = re.match(r'^(\d{1,2}):(\d{2})$', (text or '').strip())
    if not m:
        return None
    total = int(m.group(1)) * 60 + int(m.group(2))
    return total if total <= 24 * 60 and int(m.group(2)) < 60 else None


def day_window_minutes(day_name):
    """(open, close) as minutes after midnight, e.g. (480, 1140)."""
    open_h, close_h = CONVENTION_HOURS[day_name]
    return open_h * 60, close_h * 60


def _window(day_name):
    open_min, close_min = day_window_minutes(day_name)
    base = day_date(day_name)
    return base, base + timedelta(minutes=open_min), base + timedelta(minutes=close_min)


def day_segments(bookings, day_name):
    """
    Cover the day's open hours with alternating free/busy segments. A booking
    spanning several days (or overnight) is clipped to this day's hours, so a
    multi-day game shows the table busy for the whole of each day it covers.
    """
    base, open_dt, close_dt = _window(day_name)

    def mins(dt):
        return int((dt - base).total_seconds() // 60)

    segments, cursor = [], open_dt

    def add(kind, s, e, booking=None):
        segments.append({'kind': kind, 'start_min': mins(s), 'end_min': mins(e),
                         'minutes': mins(e) - mins(s), 'booking': booking})

    for b in bookings:
        if b.end <= cursor or b.start >= close_dt:
            continue
        if b.start > cursor:
            add('free', cursor, b.start)
        seg_end = min(b.end, close_dt)
        add('busy', max(b.start, cursor), seg_end, b)
        cursor = seg_end
    if cursor < close_dt:
        add('free', cursor, close_dt)
    return segments


def current_status(bookings, now):
    """
    Status at `now`: ('busy', booking), ('free', free_until_datetime), or
    ('closed', next_open_datetime_or_None) outside the convention's open hours.
    """
    for name in day_names():
        _, open_dt, close_dt = _window(name)
        if open_dt <= now < close_dt:
            for b in bookings:
                if b.start <= now < b.end:
                    return 'busy', b
            upcoming = [b.start for b in bookings if now < b.start < close_dt]
            return 'free', min([close_dt] + upcoming)
    opens = [_window(n)[1] for n in day_names() if _window(n)[1] > now]
    return 'closed', (min(opens) if opens else None)


def find_open_tables(data, day_name, from_min, to_min, table_type=''):
    """
    Tables with no booking overlapping [from_min, to_min) on day_name, in sheet
    order, each with how long it stays free after the window ends.
    """
    base, _, close_dt = _window(day_name)
    w_start = base + timedelta(minutes=from_min)
    w_end = base + timedelta(minutes=to_min)
    results = []
    for table in data.tables:
        if table_type and table.type != table_type:
            continue
        bookings = data.bookings_for(table)
        if any(b.start < w_end and b.end > w_start for b in bookings):
            continue
        later = [b.start for b in bookings if w_end <= b.start < close_dt]
        free_until = min([close_dt] + later)
        results.append({
            'table': table,
            'free_until_min': int((free_until - base).total_seconds() // 60),
        })
    return results
