import uos
import usocket
import time
from config import shared_config

class Syslog:
    """
    A MicroPython class for sending syslog messages over UDP.
    """

    def __init__(self, app_name="DriveWire", syslog_server=None, syslog_port=None):
        """
        Initializes the Syslog object.

        Args:
            app_name (str, optional): The name of the application. Defaults to "DriveWire".
            syslog_server (str, optional): The syslog server address. Reads from config if None.
            syslog_port (int, optional): The syslog server port. Reads from config if None.
        """
        self.app_name = app_name
        
        # Pull from config if not provided explicitly
        self.syslog_server = syslog_server if syslog_server is not None else shared_config.get("syslog_server")
        
        # Default to port 514 if not in config
        config_port = shared_config.get("syslog_port")
        if syslog_port is not None:
            self.syslog_port = syslog_port
        elif config_port is not None:
            self.syslog_port = int(config_port)
        else:
            self.syslog_port = 514
            
        self.facility = 1  # user-level messages
        self.severity = 6  # informational

    def format_time(self, time_tuple):
        """
        Formats the time tuple into a string.

        Args:
            time_tuple (tuple): A tuple containing time information (year, month, day, hour, minute, second, weekday, yearday).

        Returns:
            str: The formatted time string.
        """
        if not time_tuple or len(time_tuple) < 6:
            return "1900-01-01 00:00:00"
            
        year, month, day, hour, minute, second = time_tuple[:6]
        return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(
            year, month, day, hour, minute, second
        )

    def log(self, message, severity=6):
        """
        Sends a syslog message to the server via UDP socket.

        Args:
            message (str): The message to send.
            severity (int): Syslog severity level (default 6: informational).
                            Use 0-3 for error/critical/alert/emerge conditions.
        """
        if not self.syslog_server:
            # Silently drop if no server is configured
            return
            
        try:
            # We import time_sync right before logging so we get the freshest timestamp
            # and avoid circular dependencies at boot.
            import time_sync
            current_time = self.format_time(time_sync.get_local_time())
        except Exception:
            current_time = "1900-01-01 00:00:00"
            
        try:
            sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
            sock.settimeout(2.0)  # 2 second timeout to prevent blocking thread
            
            # Format: <PRI>TIMESTAMP HOSTNAME APP-NAME: MESSAGE
            # PRI = Facility * 8 + Severity
            pri = (self.facility * 8) + severity
            data = "<{}>{} {}: {}".format(pri, current_time, self.app_name, message)
            
            # resolve domain name if necessary, though usocket.getaddrinfo usually handles it
            sock.sendto(data.encode('utf-8'), (self.syslog_server, self.syslog_port))
        except Exception as e:
            uos.print("Syslog UDP dispatch error:", e)
        finally:
            if 'sock' in locals():
                sock.close()

# Create a shared global logger instance
logger = Syslog()
