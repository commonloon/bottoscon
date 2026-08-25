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

# Convention schedule
CONVENTION_START_HOUR = 9  # 9am
CONVENTION_END_HOUR = 24  # Midnight

# Special case: Sunday ends at 6pm instead of midnight
SUNDAY_END_HOUR = 18  # 6pm
