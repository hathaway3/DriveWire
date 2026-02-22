"""
SD Card support for DriveWire MicroPython server.

Uses the standard MicroPython sdcard.py SPI driver and os.mount()
for FAT/FAT32 filesystem access. Configurable SPI pins via config.json.
"""

import os
import asyncio
from config import shared_config

# Module-level state
_sd = None
_mounted = False
_mount_point = '/sd'
_lock = asyncio.Lock()


def get_lock():
    """Return the global SD card lock."""
    return _lock


def init_sd():
    """
    Initialize and mount the SD card using configured SPI pins.
    Returns True on success, False on failure.
    Safe to call if no SD card is present — will not crash.
    """
    global _sd, _mounted, _mount_point

    if _mounted:
        print("SD card already mounted")
        return True

    _mount_point = shared_config.get('sd_mount_point') or '/sd'
    spi_id = shared_config.get('sd_spi_id')
    sck_pin = shared_config.get('sd_sck')
    mosi_pin = shared_config.get('sd_mosi')
    miso_pin = shared_config.get('sd_miso')
    cs_pin = shared_config.get('sd_cs')

    if spi_id is None or sck_pin is None or mosi_pin is None or miso_pin is None or cs_pin is None:
        print("SD card: SPI pins not configured, skipping")
        return False

    try:
        from machine import SPI, Pin
        import sdcard

        print(f"SD card: Init SPI{spi_id} SCK={sck_pin} MOSI={mosi_pin} MISO={miso_pin} CS={cs_pin}")

        spi = SPI(spi_id,
                   baudrate=1_000_000,
                   polarity=0,
                   phase=0,
                   sck=Pin(sck_pin),
                   mosi=Pin(mosi_pin),
                   miso=Pin(miso_pin))

        cs = Pin(cs_pin, Pin.OUT, value=1)
        _sd = sdcard.SDCard(spi, cs)

        # Create mount point if needed
        # os.listdir('/') returns names WITHOUT leading slash (e.g. 'sd' not '/sd')
        mount_name = _mount_point.strip('/')
        if mount_name not in os.listdir('/'):
            try:
                os.mkdir(_mount_point)
                print(f"SD card: Created mount point {_mount_point}")
            except OSError as e:
                print(f"SD card: Error creating mount point: {e}")
        
        os.mount(_sd, _mount_point)
        _mounted = True

        # Try to read directory to verify
        entries = os.listdir(_mount_point)
        print(f"SD card mounted at {_mount_point} ({len(entries)} entries)")
        return True

    except ImportError as e:
        print(f"SD card: Missing driver ({e})")
        print("  Install: copy sdcard.py to device or use mip.install('sdcard')")
        return False
    except OSError as e:
        print(f"SD card: Mount failed ({e})")
        print("  Check: card inserted? FAT/FAT32 formatted?")
        _cleanup()
        return False
    except Exception as e:
        print(f"SD card: Unexpected error ({e})")
        _cleanup()
        return False


def deinit_sd():
    """Unmount SD card and release SPI resources."""
    global _sd, _mounted

    if not _mounted:
        return

    try:
        os.umount(_mount_point)
        print(f"SD card unmounted from {_mount_point}")
    except OSError as e:
        print(f"SD card unmount error: {e}")

    _cleanup()


def _cleanup():
    """Reset module state."""
    global _sd, _mounted
    _sd = None
    _mounted = False


def is_mounted():
    """Check if SD card is currently mounted and accessible."""
    global _mounted

    if not _mounted:
        return False

    # Verify mount is still valid (card may have been removed)
    try:
        os.listdir(_mount_point)
        return True
    except OSError:
        print("SD card: Mount point inaccessible, marking as unmounted")
        _mounted = False
        return False


async def get_info():
    """
    Return SD card status information.
    Returns dict with: mounted, mount_point, and optionally free/total bytes.
    """
    async with _lock:
        info = {
            'mounted': is_mounted(),
            'mount_point': _mount_point,
        }

        if info['mounted']:
            try:
                stat = os.statvfs(_mount_point)
                # statvfs returns: (f_bsize, f_frsize, f_blocks, f_bfree, f_bavail,
                #                   f_files, f_ffree, f_favail, f_flag, f_namemax)
                block_size = stat[0]
                total_blocks = stat[2]
                free_blocks = stat[3]
                info['total_bytes'] = block_size * total_blocks
                info['free_bytes'] = block_size * free_blocks
                info['total_mb'] = round(info['total_bytes'] / (1024 * 1024), 1)
                info['free_mb'] = round(info['free_bytes'] / (1024 * 1024), 1)
            except OSError:
                pass  # statvfs may not be supported on all platforms

        return info
