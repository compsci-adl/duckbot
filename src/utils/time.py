from datetime import datetime, timezone, timedelta


# Adelaide timezone (UTC+9:30)
tz = timezone(timedelta(hours=9.5))


def get_current_day():
    """Generates a numerical value for each day"""
    now = datetime.now(tz)
    epoch = datetime(1970, 1, 1, tzinfo=tz)
    days_since_epoch = (now - epoch).days
    return days_since_epoch


def get_day_from_timestamp(timestamp: datetime):
    """Generates the numerical value of a day given a timestamp"""
    epoch = datetime(1970, 1, 1, tzinfo=tz)
    days_since_epoch = (timestamp - epoch).days
    return days_since_epoch
