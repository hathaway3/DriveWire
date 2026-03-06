"""
Activity LED indicator for DriveWire MicroPython server.

Blinks the Pico 2 W onboard LED during disk I/O (flash and SD card).
On the Pico W / Pico 2 W, the LED is connected to the CYW43 WiFi chip
and is accessed via Pin("LED").
"""

import machine
try:
    from machine import Pin
except ImportError:
    pass

_led = None
_available = False


def _init() -> None:
    """Lazy-init the LED pin. Safe to call multiple times."""
    global _led, _available
    if _led is not None:
        return
    try:
        # Pico W / Pico 2 W: LED is on the CYW43 wireless chip
        _led = Pin("LED", Pin.OUT)
        _led.off()
        _available = True
    except (ValueError, NameError, AttributeError):
        # Not on a Pico W, or Pin("LED") not supported
        _available = False
    except Exception:
        _available = False


def blink() -> None:
    """Quick LED pulse for a single I/O operation."""
    _init()
    if not _available:
        return
    try:
        _led.on()
        _led.off()
    except Exception:
        pass


def on() -> None:
    """Turn LED on."""
    _init()
    if _available:
        try:
            _led.on()
        except Exception:
            pass


def off() -> None:
    """Turn LED off."""
    _init()
    if _available:
        try:
            _led.off()
        except Exception:
            pass

def toggle() -> None:
    """Toggle LED state."""
    _init()
    if _available:
        try:
            _led.value(not _led.value())
        except Exception:
            pass


class activity:
    """Context manager: LED stays on for the duration of the block."""
    def __enter__(self):
        on()
        return self
    def __exit__(self, *args):
        off()
