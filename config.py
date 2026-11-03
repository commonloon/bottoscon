"""
BottosCon Configuration

Modify these settings for each convention year.
"""

from datetime import datetime

# Convention dates and times for 2026
# Start date is a Thursday
CONVENTION_START_DATE = datetime(2026, 11, 5)  # Thursday, November 5, 2026

# Convention days in order (day name -> date offset from start)
CONVENTION_DAYS = {
    'Thursday': 0,
    'Friday': 1,
    'Saturday': 2,
    'Sunday': 3
}

# --- Table availability (see tables.py) ---

# Time zone the convention runs in; "today"/"now" are evaluated here, not in
# the server's zone (Cloud Run is UTC).
CONVENTION_TZ = 'America/Vancouver'

# Open hours per day as (first hour, end hour) on a 24h clock. The slot
# labelled 23:00 in the organizers' sheet runs 23:00-24:00, so a day that
# ends at midnight is 24; Sunday's last slot (16:00) ends at 17:00.
# This is the single source of truth for the table schedule pages and for the
# game calendars (which grey out the closed hours).
CONVENTION_HOURS = {
    'Thursday': (10, 24),
    'Friday': (9, 24),
    'Saturday': (9, 24),
    'Sunday': (9, 17),
}

# In the Table Usage sheet's table column, this table and everything below it
# are not available for general gaming and are not shown.
NON_GENERAL_TABLES_START = 'ASL1'

# Attendees reserve tables by editing the sheet, so keep this short.
TABLE_CACHE_SECONDS = 60
