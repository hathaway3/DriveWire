"""
Activity LED indicator for DriveWire MicroPython server.

Blinks the Pico 2 W onboard LED during disk I/O (flash and SD card).
On the Pico W / Pico 2 W, the LED is connected to the CYW43 WiFi chip
and is accessed via Pin("LED").

Usage:
    import activity_led
    activity_led.blink()      # Quick blink for read/write ops
    activity_led.on()         # LED on  (for flush start)
    activity_led.off()        # LED off (for flush end)
"""

_led = None
_available = False


def _init():
    """Lazy-init the LED pin. Safe to call multiple times."""
    global _led, _available
    if _led is not None:
        return
    try:
        from machine import Pin
        # Pico W / Pico 2 W: LED is on the CYW43 wireless chip
        _led = Pin("LED", Pin.OUT)
        _led.off()
        _available = True
    except Exception:
        # Not on a Pico W, or Pin("LED") not supported
        _available = False


def blink():
    """Quick LED pulse for a single I/O operation.
    
    Turns LED on then immediately off. Because sector reads/writes
    happen rapidly, the rapid on/off creates a visible flicker effect
    that indicates disk activity — similar to a classic hard drive LED.
    """
    _init()
    if not _available:
        return
    _led.on()
    _led.off()


def on():
    """Turn LED on (use for sustained operations like flush)."""
    _init()
    if _available:
        _led.on()


def off():
    """Turn LED off."""
    _init()
    if _available:
        _led.off()
