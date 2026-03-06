import usocket
import resilience
from config import shared_config

try:
    from typing import Optional, Tuple
except ImportError:
    pass

class Syslog:
    """
    A MicroPython class for sending syslog messages over UDP.
    """

    def __init__(self, app_name: str = "DriveWire", syslog_server: Optional[str] = None, syslog_port: Optional[int] = None):
        """
        Initializes the Syslog object.
        """
        self.app_name = app_name
        
        # Pull from config if not provided explicitly
        self.syslog_server = syslog_server if syslog_server is not None else shared_config.get("syslog_server")
        
        # Default to port 514 if not in config
        config_port = shared_config.get("syslog_port")
        if syslog_port is not None:
            self.syslog_port = syslog_port
        elif config_port is not None:
            try:
                self.syslog_port = int(config_port)
            except (ValueError, TypeError):
                self.syslog_port = 514
        else:
            self.syslog_port = 514
            
        self.facility = 1  # user-level messages

    def format_time(self, time_tuple: Optional[Tuple]) -> str:
        """
        Formats the time tuple into a string.
        """
        if not time_tuple or len(time_tuple) < 6:
            return "1970-01-01 00:00:00"
            
        year, month, day, hour, minute, second = time_tuple[:6]
        return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(
            year, month, day, hour, minute, second
        )

    def log(self, message: str, severity: int = 6) -> None:
        """
        Sends a syslog message to the server via UDP socket.
        """
        if not self.syslog_server:
            # Silently drop if no server is configured
            return
            
        try:
            import time_sync
            current_time = self.format_time(time_sync.get_local_time())
        except Exception:
            current_time = "1970-01-01 00:00:00"
            
        sock = None
        try:
            sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
            sock.settimeout(2.0)  # 2 second timeout
            
            # Format: <PRI>TIMESTAMP HOSTNAME APP-NAME: MESSAGE
            # PRI = Facility * 8 + Severity
            pri = (self.facility * 8) + severity
            data = "<{}>{} {}: {}".format(pri, current_time, self.app_name, message)
            
            sock.sendto(data.encode('utf-8'), (self.syslog_server, self.syslog_port))
        except Exception as e:
            # Use resilience log for local error reporting, but prevent recursion
            resilience.log(f"Syslog UDP dispatch error: {e}", level=2, _from_syslog=True)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

# Create a shared global logger instance
logger = Syslog()
