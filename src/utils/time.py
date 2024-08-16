from datetime import datetime, timezone, timedelta
import pytz

from datetime import datetime
import pytz

# Adelaide timezone (UTC+9:30)
tz = pytz.timezone("Australia/Adelaide")


def get_current_day():
    """Generates a numerical value for each day"""
    now = datetime.now(tz)
    epoch = datetime(1970, 1, 1, tzinfo=tz)
    days_since_epoch = (now - epoch).days
    return days_since_epoch


def get_day_from_timestamp(timestamp: datetime):
    """Generates the numerical value of a day given a timestamp"""
    if timestamp.tzinfo is None:
        timestamp = tz.localize(timestamp)
    else:
        timestamp = timestamp.astimezone(tz)
    epoch = datetime(1970, 1, 1, tzinfo=tz)
    days_since_epoch = (timestamp - epoch).days
    return days_since_epoch


def get_timestamp_str(timestamp: datetime = datetime.now()):
    """Generates a string representing the timestamp, in Australian time"""
    if timestamp.tzinfo is None:
        timestamp = tz.localize(timestamp)
    else:
        timestamp = timestamp.astimezone(tz)

    # Return the string representation of the timestamp
    return timestamp.strftime("%Y-%m-%d %H:%M:%S %Z%z")