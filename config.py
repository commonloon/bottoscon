"""
BottosCon Configuration
Updated by Claude AI at 2025-11-04 14:30:00

Modify these settings for each convention year.
"""

from datetime import datetime

# Convention dates and times for 2025
# Start date should be a Thursday
CONVENTION_START_DATE = datetime(2025, 11, 6)  # Thursday, November 6, 2025

# Convention days in order (day name -> date offset from start)
CONVENTION_DAYS = {
    'Thursday': 0,
    'Friday': 1,
    'Saturday': 2,
    'Sunday': 3
}

# Convention schedule
CONVENTION_START_HOUR = 9  # 9am
CONVENTION_END_HOUR = 24  # Midnight (11pm + 1 hour)

# Special case: Sunday ends at 4pm instead of midnight
SUNDAY_END_HOUR = 16  # 4pm
