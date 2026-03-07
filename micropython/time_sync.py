import ntptime
import time
import uasyncio as asyncio
import resilience
from config import shared_config

try:
    from typing import Tuple
except ImportError:
    pass

def sync_time(max_retries: int = 3) -> bool:
    """
    Synchronizes the system time with the configured NTP server.
    Returns True on success, False on failure.
    """
    ntp_server = shared_config.get("ntp_server")
    if not ntp_server:
        resilience.log("No NTP server configured.", level=2)
        return False
    
    for attempt in range(max_retries):
        try:
            ntptime.host = ntp_server
            resilience.log(f"Syncing time with {ntp_server} (attempt {attempt + 1}/{max_retries})...")
            ntptime.settime()  # Sets RTC to UTC
            resilience.log(f"Time synced: {time.localtime()}")
            return True
        except Exception as e:
            resilience.log(f"Failed to sync time (attempt {attempt + 1}): {e}", level=2)
            if attempt < max_retries - 1:
                resilience.feed_wdt()
                time.sleep(1)  # Wait before retry
    
    resilience.log("Time sync failed after all retries", level=3)
    return False

def get_local_time() -> Tuple:
    """
    Returns the local time tuple (year, month, day, hour, minute, second, weekday, yearday)
    applying the configured timezone offset.
    """
    try:
        utc = time.time()
        offset_hours = shared_config.get("timezone_offset", 0)
        local_timestamp = utc + (int(offset_hours) * 3600)
        return time.localtime(local_timestamp)
    except Exception as e:
        resilience.log(f"get_local_time error: {e}", level=2)
        return (2000, 1, 1, 0, 0, 0, 0, 1)

async def keep_time_synced(interval_hours: int = 12) -> None:
    """
    Background task that periodically resyncs the system clock via NTP.
    """
    interval_seconds = interval_hours * 3600
    while True:
        await asyncio.sleep(interval_seconds)
        resilience.log(f"Periodic time sync ({interval_hours}h interval)...")
        sync_time()
        resilience.feed_wdt()
