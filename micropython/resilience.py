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
    if cause == machine.PWRON_RESET:
        return "Power-On"
    elif cause == machine.HARD_RESET:
        return "Hard Reset"
    elif cause == machine.WDT_RESET:
        return "Watchdog Reset"
    elif cause == machine.DEEPSLEEP_RESET:
        return "Deep Sleep Wakeup"
    elif cause == machine.SOFT_RESET:
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

def blink_state(state: str) -> None:
    """
    Signal system state using the onboard LED.
    States: 'boot', 'wifi_wait', 'error', 'running'
    """
    try:
        from activity_led import on, off
        if state == 'boot':
            # 3 quick flashes
            for _ in range(3):
                on(); time.sleep(0.1); off(); time.sleep(0.1)
        elif state == 'wifi_wait':
            # Slow blink
            on(); time.sleep(0.5); off(); time.sleep(0.5)
        elif state == 'error':
            # Rapid blink
            for _ in range(10):
                on(); time.sleep(0.05); off(); time.sleep(0.05)
        elif state == 'running':
            # One long blink
            on(); time.sleep(1.0); off()
    except Exception:
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

def collect_garbage(reason: str = "general"):
    """Explicitly trigger GC and log status."""
    try:
        before = gc.mem_free() if hasattr(gc, 'mem_free') else 0
        gc.collect()
        after = gc.mem_free() if hasattr(gc, 'mem_free') else 0
        log(f"GC ({reason}): {before} -> {after} free", level=0)
    except Exception:
        pass
