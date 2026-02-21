import ntptime
import time
from config import shared_config

def sync_time(max_retries=3):
    """
    Synchronizes the system time with the configured NTP server.
    Returns True on success, False on failure.
    """
    ntp_server = shared_config.get("ntp_server")
    if not ntp_server:
        print("No NTP server configured.")
        return False
    
    for attempt in range(max_retries):
        try:
            ntptime.host = ntp_server
            print(f"Syncing time with {ntp_server} (attempt {attempt + 1}/{max_retries})...")
            ntptime.settime()  # Sets RTC to UTC
            print(f"Time synced: {time.localtime()}")
            return True
        except Exception as e:
            print(f"Failed to sync time (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
    
    print("Time sync failed after all retries")
    return False

def get_local_time():
    """
    Returns the local time tuple (year, month, day, hour, minute, second, weekday, yearday)
    applying the configured timezone offset.
    """
    try:
        utc = time.time()
        offset_hours = shared_config.get("timezone_offset") or 0
        local_timestamp = utc + (int(offset_hours) * 3600)
        return time.localtime(local_timestamp)
    except Exception as e:
        print(f"get_local_time error: {e}")
        return (2000, 1, 1, 0, 0, 0, 0, 1)
