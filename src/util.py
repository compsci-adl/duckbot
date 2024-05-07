"""
Helpful utility functions
"""

def extract_time_from_secs(time_secs: int) -> tuple[int, int, int, int]:
    """Convert from seconds to days, hours, minutes and seconds"""

    days = int(time_secs // (3600 * 24))
    time_secs %= 3600 * 24
    hours = int(time_secs // 3600)
    time_secs %= 3600
    mins = int(time_secs // 60)
    time_secs %= 60
    return days, hours, mins, int(time_secs)
