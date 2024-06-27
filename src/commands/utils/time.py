import datetime
import pytz

def get_adelaide_time():
    # Convert UTC timestamp to Adelaide time
    adelaide_tz = pytz.timezone('Australia/Adelaide')
    utc_now = datetime.datetime.now(pytz.utc)
    adelaide_time = utc_now.astimezone(adelaide_tz)
    return adelaide_time
