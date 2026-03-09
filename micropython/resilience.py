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

# Global logging state
MIN_LOG_LEVEL = 1  # 0=Debug, 1=Info, 2=Warn, 3=Error, 4=Crit
_log_callback = None

def set_log_callback(callback):
    """Set a callback function to receive every log line (e.g. for Web UI dashboard)."""
    global _log_callback
    _log_callback = callback

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
    global MIN_LOG_LEVEL, _log_callback
    
    if level < MIN_LOG_LEVEL:
        return

    levels = ["DEBUG", "INFO", "WARN", "ERROR", "CRIT"]
    lvl_str = levels[level] if 0 <= level < len(levels) else "LOG"
    
    timestamp = time.localtime()
    ts_str = "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(*timestamp[:6])
    
    log_line = f"[{ts_str}] [{lvl_str}] {message}"
    print(log_line) # MicroPython print automatically adds newline
    
    # Notify dashboard/active listeners
    if _log_callback:
        try:
            _log_callback(log_line)
        except Exception:
            pass

    log_line += "\n"
    
    # Persistent logging with circular buffer logic
    try:
        stats = os.stat(LOG_FILE)
        if stats[6] > MAX_LOG_SIZE:
            # Simple "clear if full" strategy for flash safety
            os.rename(LOG_FILE, LOG_FILE + ".old")
    except (OSError, KeyboardInterrupt):
        pass
    
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_line)
            os.sync()
    except (OSError, KeyboardInterrupt):
        pass

    # Forward to Syslog Remote Server
    if not _from_syslog:
        try:
            import syslog
            # Map resilience levels to syslog severities
            sev = [7, 6, 4, 3, 2][level] if 0 <= level <= 4 else 6
            syslog.logger.log(message, severity=sev)
        except (Exception, KeyboardInterrupt):
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

def open_remote_stream(url: str):
    """Open a raw socket HTTP GET and return the socket after consuming headers.
    
    This avoids urequests/Response objects which buffer entire payloads into RAM.
    Returns the socket object for incremental reading, or None on failure.
    Important: Caller MUST close the socket when finished.
    """
    import usocket
    try:
        # Parse URL: http://host:port/path
        url_no_proto = url.split('://', 1)[1] if '://' in url else url
        slash_pos = url_no_proto.find('/')
        if slash_pos >= 0:
            hostport = url_no_proto[:slash_pos]
            path = url_no_proto[slash_pos:]
        else:
            hostport = url_no_proto
            path = '/'
        
        if ':' in hostport:
            host, port_str = hostport.rsplit(':', 1)
            port = int(port_str)
        else:
            host = hostport
            port = 80
        
        addr = usocket.getaddrinfo(host, port)[0][-1]
        sock = usocket.socket()
        sock.settimeout(5)
        sock.connect(addr)
        feed_wdt()
        
        # Send minimal HTTP/1.0 request (Connection: close implied)
        sock.send(b'GET ')
        sock.send(path.encode())
        sock.send(b' HTTP/1.0\r\nHost: ')
        sock.send(host.encode())
        sock.send(b'\r\n\r\n')
        
        # Read headers byte-by-byte looking for \r\n\r\n end marker
        # Use a 4-byte ring buffer to detect the boundary without large allocs
        hdr_end = bytearray(4)
        status_line = bytearray(16)  # First few bytes to check status
        status_pos = 0
        
        while True:
            b = sock.recv(1)
            if not b:
                sock.close()
                return None
            
            # Capture first 16 bytes for status code check
            if status_pos < 16:
                status_line[status_pos] = b[0]
                status_pos += 1
            
            # Shift ring buffer
            hdr_end[0] = hdr_end[1]
            hdr_end[1] = hdr_end[2]
            hdr_end[2] = hdr_end[3]
            hdr_end[3] = b[0]
            
            if hdr_end == b'\r\n\r\n':
                break
        
        feed_wdt()
        
        # Check for 200 status
        if b'200' not in bytes(status_line):
            sock.close()
            return None
        
        return sock
    except Exception as e:
        log(f"Remote stream error ({url}): {e}", level=2)
        return None
