"""
Tests for table availability (tables.py and the /tables, /table/<id> routes).

All data here is synthetic. Never point these tests at the real organizer
workbook: its URLs must not appear in the repo.
"""
from datetime import datetime

import pytest

import app as app_module
import tables as t

USAGE_ROWS = [
    ['', '', '', 'Table Components'],
    ['Table', 'Type', 'Placed', 'L', 'M', 'C'],
    ['A01-BR', 'C', 'Y'],
    ['NW01', '2M', 'Y'],
    ['SE09', '2L', 'Y'],
    ['NE05', 'C', 'Y'],
    ['ASL1', '1L', 'Y'],      # first non-general table: excluded, and everything after it
    ['REC', '1M', ''],
    ['', '', ''],
    ['Prefix', '', ''],
]

GAME_HEADER = ['Game ID', 'Organizer', 'Game name', 'Format', 'To Do', 'Game Description / Notes',
               'Game Type', 'Min Players', 'Max Players', 'Play Surface Desired', 'Assigned Table',
               'Pre-Game Set-Up Time Needed (m)', 'Start Day', 'Start Time (24 hour clock)',
               'End Day', 'End Time (24 hour clock)']


def game(gid, organizer, name, table, start_day, start, end_day, end):
    return [gid, organizer, name, '', '', '', '', '', '', '', table, '0',
            start_day, start, end_day, end]


GAME_ROWS = [
    ['', '', 'GAME ORGANIZERS: add games below'],
    GAME_HEADER,
    game('1', 'Aldo Santolla <aldo@example.com>', 'Endeavor', 'NW01', 'Friday', '10:00', 'Friday', '12:00'),
    game('2', 'Bea B <bea@example.com>', 'Late Game', 'NW01', 'Friday', '23:00:00', 'Friday', '23:30'),
    game('3', 'Cy C <cy@example.com>', 'Open Gaming', 'A01-BR', 'Thursday', '10:00', 'Sunday', '15:00'),
    game('4', 'Di D <di@example.com>', 'Overnight', 'SE09', 'Friday', '22:00', 'Saturday', '09:00'),
    game('5', 'Ed E <ed@example.com>', 'Cancelled', '', 'Friday', '10:00', 'Friday', '12:00'),
    game('6', 'Flo F <flo@example.com>', 'Staff table', 'ASL1', 'Friday', '10:00', 'Friday', '12:00'),
    game('7', 'Gus G <gus@example.com>', 'Template row', 'NE05', '', '', '', ''),
    game('8', 'Hal H <hal@example.com>', 'Backwards', 'NE05', 'Friday', '12:00', 'Friday', '10:00'),
    game('9', 'Ivy I <ivy@example.com>', 'Lowercase id', 'ne05', 'Saturday', '14:00', 'Saturday', '16:00'),
]


@pytest.fixture
def data():
    tables = t.parse_tables(USAGE_ROWS)
    return t.TableData(tables=tables, bookings=t.parse_bookings(GAME_ROWS, tables), fetched_at=0)


class TestParsing:
    def test_table_list_stops_at_first_non_general_table(self, data):
        assert [x.id for x in data.tables] == ['A01-BR', 'NW01', 'SE09', 'NE05']
        assert data.types == ['2L', '2M', 'C']

    def test_unassigned_excluded_and_invalid_rows_skipped(self, data):
        assert [b.game_name for b in data.bookings['NW01']] == ['Endeavor', 'Late Game']
        assert [b.game_name for b in data.bookings['NE05']] == ['Lowercase id']
        assert 'ASL1' not in data.bookings

    def test_seconds_in_times_are_accepted(self, data):
        late = data.bookings['NW01'][1]
        assert (late.start.hour, late.start.minute) == (23, 0)

    def test_organizer_email_is_stripped(self, data):
        assert data.bookings['NW01'][0].organizer == 'Aldo Santolla'
        assert all('@' not in b.organizer for lst in data.bookings.values() for b in lst)

    def test_missing_header_raises_without_leaking_anything(self):
        with pytest.raises(t.TableDataError):
            t.parse_bookings([['<html>sign in</html>']], [])


class TestSegments:
    def test_single_day_segments_cover_open_hours(self, data):
        segs = t.day_segments(data.bookings['NW01'], 'Friday')
        assert [(s['kind'], s['start_min'], s['end_min']) for s in segs] == [
            ('free', 8 * 60, 10 * 60), ('busy', 10 * 60, 12 * 60),
            ('free', 12 * 60, 23 * 60), ('busy', 23 * 60, 23 * 60 + 30),
            ('free', 23 * 60 + 30, 24 * 60)]

    def test_multi_day_game_is_busy_all_day_in_between(self, data):
        thursday, saturday, sunday = (t.day_segments(data.bookings['A01-BR'], d)
                                      for d in ('Thursday', 'Saturday', 'Sunday'))
        assert [(s['kind'], s['start_min']) for s in thursday] == [('busy', 10 * 60)] or \
            [s['kind'] for s in thursday] == ['free', 'busy']
        assert [s['kind'] for s in saturday] == ['busy']
        assert [s['kind'] for s in sunday] == ['busy', 'free']
        assert sunday[1]['end_min'] == 19 * 60   # Sunday closes at 19:00

    def test_overnight_game_splits_across_days(self, data):
        friday = t.day_segments(data.bookings['SE09'], 'Friday')
        saturday = t.day_segments(data.bookings['SE09'], 'Saturday')
        assert friday[-1]['kind'] == 'busy' and friday[-1]['end_min'] == 24 * 60
        assert saturday[0]['kind'] == 'busy' and saturday[0]['end_min'] == 9 * 60


class TestSearchAndStatus:
    def ids(self, results):
        return [r['table'].id for r in results]

    def test_window_must_be_entirely_free(self, data):
        # Friday 11:00-13:00 overlaps Endeavor on NW01 and Open Gaming on A01-BR
        assert self.ids(t.find_open_tables(data, 'Friday', 11 * 60, 13 * 60)) == ['SE09', 'NE05']

    def test_adjacent_booking_does_not_conflict(self, data):
        assert 'NW01' in self.ids(t.find_open_tables(data, 'Friday', 12 * 60, 14 * 60))
        assert 'NW01' in self.ids(t.find_open_tables(data, 'Friday', 8 * 60, 10 * 60))

    def test_type_filter_and_free_until(self, data):
        results = t.find_open_tables(data, 'Friday', 12 * 60, 14 * 60, table_type='2M')
        assert self.ids(results) == ['NW01']
        assert results[0]['free_until_min'] == 23 * 60

    def test_window_up_to_midnight(self, data):
        assert self.ids(t.find_open_tables(data, 'Saturday', 22 * 60, 24 * 60)) == ['SE09', 'NW01', 'NE05'] \
            or 'NW01' in self.ids(t.find_open_tables(data, 'Saturday', 22 * 60, 24 * 60))

    def test_current_status(self, data):
        nw01 = data.bookings['NW01']
        assert t.current_status(nw01, datetime(2026, 11, 6, 11, 0))[0] == 'busy'
        status, until = t.current_status(nw01, datetime(2026, 11, 6, 12, 0))
        assert (status, until) == ('free', datetime(2026, 11, 6, 23, 0))
        assert t.current_status(nw01, datetime(2026, 11, 6, 3, 0)) == ('closed', datetime(2026, 11, 6, 8, 0))

    def test_default_day(self):
        assert t.default_day(datetime(2026, 11, 7, 15, 0)) == 'Saturday'
        assert t.default_day(datetime(2026, 11, 1, 15, 0)) == 'Thursday'
        assert t.default_day(datetime(2026, 12, 1, 15, 0)) == 'Sunday'


@pytest.fixture
def client(monkeypatch, data):
    app_module.app.config['TESTING'] = True
    monkeypatch.setattr(t, 'is_configured', lambda: True)
    monkeypatch.setattr(t, 'get_table_data', lambda force=False: data)
    monkeypatch.setattr(t, 'convention_now', lambda: datetime(2026, 11, 6, 11, 15))
    monkeypatch.setattr(app_module, 'get_favourites', lambda: [])
    return app_module.app.test_client()


class TestRoutes:
    def test_table_page_defaults_to_today_and_shows_current_use(self, client):
        html = client.get('/table/NW01').data.decode()
        assert 'In use: Endeavor' in html and 'Aldo Santolla' in html
        assert 'aldo@example.com' not in html
        assert 'Friday (today)' in html

    def test_table_id_is_case_insensitive_and_unknown_is_404(self, client):
        assert client.get('/table/nw01').status_code == 200
        assert client.get('/table/ASL1').status_code == 404

    def test_before_the_convention_nothing_is_labelled_today(self, client, monkeypatch):
        monkeypatch.setattr(t, 'convention_now', lambda: datetime(2026, 11, 2, 9, 0))
        html = client.get('/table/NW01').data.decode()
        assert '(today)' not in html
        assert 'class="status-banner' not in html
        assert 'class="active">Thursday' in html  # first day is still the selected tab

    def test_other_day_has_no_status_banner(self, client):
        html = client.get('/table/NW01?day=Saturday').data.decode()
        assert 'class="status-banner' not in html

    def test_search_defaults_to_two_hours_from_next_half_hour(self, client):
        html = client.get('/tables').data.decode()
        assert 'Friday 11:30-13:30' in html

    def test_search_results(self, client):
        html = client.get('/tables?day=Friday&from=11:00&to=13:00&type=2L').data.decode()
        assert 'SE09' in html and 'NW01' not in html.split('result-grid')[-1]

    def test_bad_window_gets_a_notice(self, client):
        html = client.get('/tables?day=Friday&from=14:00&to=13:00').data.decode()
        assert 'end time must be after' in html

    def test_pages_are_not_cached_or_indexed(self, client):
        response = client.get('/table/NW01')
        assert response.headers['Cache-Control'] == 'no-store'
        assert 'noindex' in response.headers['X-Robots-Tag']


class TestExportUrl:
    BASE = 'https://docs.google.com/spreadsheets/d/FAKE_ID_123'

    def test_browser_edit_link_becomes_export_link(self):
        url = f'{self.BASE}/edit?gid=1082874450#gid=1082874450'
        assert t.csv_export_url(url) == f'{self.BASE}/export?format=csv&gid=1082874450'

    def test_export_link_is_unchanged(self):
        url = f'{self.BASE}/export?format=csv&gid=7'
        assert t.csv_export_url(url) == url

    def test_edit_link_without_gid_exports_first_tab(self):
        assert t.csv_export_url(f'{self.BASE}/edit') == f'{self.BASE}/export?format=csv'

    def test_other_urls_pass_through(self):
        assert t.csv_export_url('https://example.test/x.csv') == 'https://example.test/x.csv'


class TestFailureModes:
    def test_unconfigured_site_returns_generic_503(self, monkeypatch):
        monkeypatch.setattr(app_module, 'get_favourites', lambda: [])
        monkeypatch.delenv(t.TABLE_USAGE_URL_ENV, raising=False)
        monkeypatch.delenv(t.GAMES_URL_ENV, raising=False)
        response = app_module.app.test_client().get('/tables')
        assert response.status_code == 503

    def test_fetch_failure_does_not_leak_url(self, monkeypatch, caplog):
        secret = 'https://docs.google.com/spreadsheets/d/SECRET_ID/export?format=csv'
        monkeypatch.setenv(t.TABLE_USAGE_URL_ENV, secret)
        monkeypatch.setenv(t.GAMES_URL_ENV, secret)
        monkeypatch.setattr(app_module, 'get_favourites', lambda: [])
        t.clear_cache()
        t._cache['data'] = None

        def boom(url):
            raise RuntimeError(f'failed to fetch {url}')
        monkeypatch.setattr(t, '_download_csv', boom)
        response = app_module.app.test_client().get('/table/NW01')
        assert response.status_code == 503
        assert 'SECRET_ID' not in response.data.decode()
        assert 'SECRET_ID' not in caplog.text
