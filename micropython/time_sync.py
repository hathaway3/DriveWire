import ntptime
import time
from config import shared_config

def sync_time():
    """
    Synchronizes the system time with the configured NTP server.
    """
    ntp_server = shared_config.get("ntp_server")
    if ntp_server:
        try:
            ntptime.host = ntp_server
            print(f"Syncing time with {ntp_server}...")
            ntptime.settime() # Sets RTC to UTC
            print(f"Time synced: {time.localtime()}")
            return True
        except Exception as e:
            print(f"Failed to sync time: {e}")
            return False
    else:
        print("No NTP server configured.")
        return False

def get_local_time():
    """
    Returns the local time tuple (year, month, day, hour, minute, second, weekday, yearday)
    applying the configured timezone offset.
    """
    utc = time.time()
    offset_hours = shared_config.get("timezone_offset") or 0
    local_timestamp = utc + (int(offset_hours) * 3600)
    return time.localtime(local_timestamp)
