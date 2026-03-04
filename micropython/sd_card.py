"""
SD Card support for DriveWire MicroPython server.

Uses the standard MicroPython sdcard.py SPI driver and os.mount()
for FAT/FAT32 filesystem access. Configurable SPI pins via config.json.
"""

import os
import asyncio
from config import shared_config
import resilience

try:
    from typing import Optional, Dict, Any
except ImportError:
    pass

# Module-level state
_sd = None
_mounted = False
_mount_point = '/sd'
_lock = asyncio.Lock()


def get_lock() -> asyncio.Lock:
    """Return the global SD card lock."""
    return _lock


def init_sd() -> bool:
    """
    Initialize and mount the SD card using configured SPI pins.
    Returns True on success, False on failure.
    Safe to call if no SD card is present — will not crash.
    """
    global _sd, _mounted, _mount_point

    if _mounted:
        resilience.log("SD card already mounted")
        return True

    _mount_point = shared_config.get('sd_mount_point') or '/sd'
    spi_id = shared_config.get('sd_spi_id')
    sck_pin = shared_config.get('sd_sck')
    mosi_pin = shared_config.get('sd_mosi')
    miso_pin = shared_config.get('sd_miso')
    cs_pin = shared_config.get('sd_cs')
    baudrate = shared_config.get('sd_spi_baudrate') or 1_000_000

    if spi_id is None or sck_pin is None or mosi_pin is None or miso_pin is None or cs_pin is None:
        resilience.log("SD card: SPI pins not configured, skipping", level=0)
        return False

    try:
        from machine import SPI, Pin
        import sdcard

        resilience.log(f"SD card: Init SPI{spi_id} SCK={sck_pin} MOSI={mosi_pin} MISO={miso_pin} CS={cs_pin} Speed={baudrate}")

        spi = SPI(spi_id,
                   baudrate=baudrate,
                   polarity=0,
                   phase=0,
                   sck=Pin(sck_pin),
                   mosi=Pin(mosi_pin),
                   miso=Pin(miso_pin))

        cs = Pin(cs_pin, Pin.OUT, value=1)
        
        try:
            _sd = sdcard.SDCard(spi, cs)
        except (OSError, RuntimeError) as e:
            resilience.log(f"SD card: Hardware initialization failed: {e}", level=2)
            return False

        # Create mount point if needed
        mount_name = _mount_point.strip('/')
        if mount_name not in os.listdir('/'):
            try:
                os.mkdir(_mount_point)
                resilience.log(f"SD card: Created mount point {_mount_point}")
            except OSError as e:
                resilience.log(f"SD card: Error creating mount point: {e}", level=3)
        
        try:
            os.mount(_sd, _mount_point)
            _mounted = True
        except OSError as e:
            resilience.log(f"SD card: Mount failed: {e}", level=3)
            _cleanup()
            return False

        # Try to read directory to verify
        entries = os.listdir(_mount_point)
        resilience.log(f"SD card mounted at {_mount_point} ({len(entries)} entries)")
        return True

    except ImportError as e:
        resilience.log(f"SD card: Missing driver ({e})", level=3)
        return False
    except Exception as e:
        resilience.log(f"SD card: Unexpected error ({e})", level=3)
        _cleanup()
        return False


def deinit_sd() -> None:
    """Unmount SD card and release SPI resources."""
    global _sd, _mounted

    if not _mounted:
        return

    try:
        os.umount(_mount_point)
        resilience.log(f"SD card unmounted from {_mount_point}")
    except OSError as e:
        resilience.log(f"SD card unmount error: {e}", level=2)

    _cleanup()


def _cleanup() -> None:
    """Reset module state."""
    global _sd, _mounted
    _sd = None
    _mounted = False


def is_mounted() -> bool:
    """Check if SD card is currently mounted and accessible."""
    global _mounted

    if not _mounted:
        return False

    # Verify mount is still valid (card may have been removed)
    try:
        os.listdir(_mount_point)
        return True
    except OSError:
        resilience.log("SD card: Mount point inaccessible, marking as unmounted", level=2)
        _mounted = False
        return False


async def get_info() -> Dict[str, Any]:
    """
    Return SD card status information.
    """
    async with _lock:
        info = {
            'mounted': is_mounted(),
            'mount_point': _mount_point,
        }

        if info['mounted']:
            try:
                stat = os.statvfs(_mount_point)
                block_size = stat[0]
                total_blocks = stat[2]
                free_blocks = stat[3]
                info['total_bytes'] = block_size * total_blocks
                info['free_bytes'] = block_size * free_blocks
                info['total_mb'] = round(info['total_bytes'] / (1024 * 1024), 1)
                info['free_mb'] = round(info['free_bytes'] / (1024 * 1024), 1)
            except (OSError, AttributeError):
                pass

        return info
