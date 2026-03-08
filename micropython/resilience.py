import machine
import os
import time
import gc

try:
    from typing import Optional, List, Union
except ImportError:
    # Dummy types for runtime
    pass

# Resilience constants
LOG_FILE = "system.log"
MAX_LOG_SIZE = 4096  # 4KB circular buffer style

def get_reset_cause() -> str:
    """Return a human-readable string for the last reset cause."""
    cause = machine.reset_cause()
    # Use getattr with unique sentinel defaults for cross-platform
    # compatibility (Pico 2 W / RP2350 may not define all constants)
    if cause == getattr(machine, 'PWRON_RESET', -1):
        return "Power-On"
    elif cause == getattr(machine, 'HARD_RESET', -2):
        return "Hard Reset"
    elif cause == getattr(machine, 'WDT_RESET', -3):
        return "Watchdog Reset"
    elif cause == getattr(machine, 'DEEPSLEEP_RESET', -4):
        return "Deep Sleep Wakeup"
    elif cause == getattr(machine, 'SOFT_RESET', -5):
        return "Soft Reset"
    return f"Unknown ({cause})"

def log(message: str, level: int = 1, _from_syslog: bool = False) -> None:
    """
    Centralized logging function.
    Level: 0=Debug, 1=Info, 2=Warning, 3=Error, 4=Critical
    """
    levels = ["DEBUG", "INFO", "WARN", "ERROR", "CRIT"]
    lvl_str = levels[level] if 0 <= level < len(levels) else "LOG"
    
    timestamp = time.localtime()
    ts_str = "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(*timestamp[:6])
    
    log_line = f"[{ts_str}] [{lvl_str}] {message}\n"
    print(log_line, end='')
    
    # Persistent logging with circular buffer logic
    try:
        stats = os.stat(LOG_FILE)
        if stats[6] > MAX_LOG_SIZE:
            # Simple "clear if full" strategy for flash safety
            os.rename(LOG_FILE, LOG_FILE + ".old")
    except OSError:
        pass
    
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_line)
            os.sync()
    except OSError:
        pass

    # Forward to Syslog Remote Server
    if not _from_syslog:
        try:
            import syslog
            # Map resilience levels to syslog severities
            sev = [7, 6, 4, 3, 2][level] if 0 <= level <= 4 else 6
            syslog.logger.log(message, severity=sev)
        except Exception:
            pass

def is_rp2350() -> bool:
    """Detect if running on RP2350 (Pico 2) based on default CPU frequency."""
    try:
        # RP2350 default is 150MHz, RP2040 is 125MHz
        return machine.freq() > 130_000_000
    except Exception:
        return False

def blink_state(state: str) -> None:
    """
    Signal system state using the onboard LED.
    States: 'boot', 'wifi_wait', 'error', 'running'
    """
    try:
        import activity_led
        if state == 'boot':
            # 3 quick flashes
            for _ in range(3):
                activity_led.on(); time.sleep(0.1); activity_led.off(); time.sleep(0.1)
        elif state == 'wifi_wait':
            # Slow blink
            activity_led.on(); time.sleep(0.5); activity_led.off(); time.sleep(0.5)
        elif state == 'error':
            # Rapid blink
            for _ in range(10):
                activity_led.on(); time.sleep(0.05); activity_led.off(); time.sleep(0.05)
        elif state == 'running':
            # One long blink
            activity_led.on(); time.sleep(1.0); activity_led.off()
    except Exception:
        # Silently fail if LED hardware is not available
        pass

class SafeWatchdog:
    """Wrapper for machine.WDT to provide safer lifecycle management."""
    def __init__(self, timeout_ms: int = 8000):
        self.wdt = None
        self.timeout = timeout_ms
        try:
            self.wdt = machine.WDT(timeout=self.timeout)
            log(f"Watchdog initialized (timeout={self.timeout}ms)")
        except Exception as e:
            log(f"Failed to init Watchdog: {e}", level=3)

    def feed(self):
        if self.wdt:
            self.wdt.feed()

# Global watchdog instance
wdt = None

def init_wdt(timeout_ms: int = 8000):
    global wdt
    if wdt is None:
        wdt = SafeWatchdog(timeout_ms)
    return wdt

def feed_wdt():
    """Feed the global watchdog timer if initialized."""
    if wdt:
        wdt.feed()

def collect_garbage(reason: str = "general"):
    """Explicitly trigger GC and log status."""
    try:
        before = gc.mem_free() if hasattr(gc, 'mem_free') else 0
        gc.collect()
        after = gc.mem_free() if hasattr(gc, 'mem_free') else 0
        log(f"GC ({reason}): {before} -> {after} free", level=0)
    except Exception:
        pass

def log_mem_info(label: str = "Status"):
    """Log current heap usage."""
    try:
        free = gc.mem_free()
        alloc = gc.mem_alloc()
        total = free + alloc
        log(f"Memory ({label}): {free/1024:.1f}KB free, {alloc/1024:.1f}KB alloc (Total: {total/1024:.1f}KB)", level=0)
    except Exception:
        pass
