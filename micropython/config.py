import json
import os
import resilience

try:
    from typing import Optional, List, Dict, Any, Union
except ImportError:
    pass

CONFIG_FILE = 'config.json'

# Valid baud rates for UART
VALID_BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

DEFAULT_CONFIG: Dict[str, Any] = {
    "wifi_ssid": "YOUR_SSID",
    "wifi_password": "YOUR_PASSWORD",
    "baud_rate": 115200,
    "drives": [None] * 4,  # 4 Virtual Drives
    "ntp_server": "pool.ntp.org",
    "timezone_offset": 0,  # Hours from UTC (-12 to +14)
    "serial_map": {},  # { "0": {"host": "towel.blinkenlights.nl", "port": 23} }
    "sd_spi_id": 1,        # SPI bus (0 or 1)
    "sd_sck": 10,          # GP10
    "sd_mosi": 11,         # GP11
    "sd_miso": 12,         # GP12
    "sd_cs": 13,           # GP13
    "sd_spi_baudrate": 10_000_000,
    "sd_mount_point": "/sd",
    "syslog_server": "",
    "syslog_port": 514,
    "remote_servers": []  # [{"name": "Dev", "url": "http://192.168.1.100:8080"}, ...]
}

class Config:
    """Configuration manager with validation and persistence."""
    
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from file, merging with defaults."""
        try:
            if CONFIG_FILE in os.listdir('/'):
                with open(CONFIG_FILE, 'r') as f:
                    stored_config = json.load(f)
                    # Update default config with stored values
                    for key, value in stored_config.items():
                        self.config[key] = value
                    # Validate after loading
                    self.validate()
        except (OSError, ValueError) as e:
            resilience.log(f"Config file error: {e}. Using defaults.", level=2)
            self.save()

    def save(self) -> bool:
        """Save configuration to flash and sync filesystem."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f)
            try:
                os.sync()
            except AttributeError:
                pass
            return True
        except OSError as e:
            resilience.log(f"Config save error: {e}", level=3)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULT_CONFIG:
            resilience.log(f"Warning: Unknown config key '{key}'", level=2)
            return
        self.config[key] = value
        self.save()

    def update(self, changes_dict: Dict[str, Any]) -> None:
        """Update multiple configuration keys and save once."""
        changed = False
        for key, value in changes_dict.items():
            if key not in DEFAULT_CONFIG:
                resilience.log(f"Warning: Unknown config key '{key}'", level=1)
                continue
            if self.config.get(key) != value:
                self.config[key] = value
                changed = True
        
        if changed:
            self.save()
    
    def validate(self) -> None:
        """Validate configuration values."""
        # Validate baud rate
        baud = self.config.get('baud_rate')
        if baud not in VALID_BAUD_RATES:
            resilience.log(f"Warning: Invalid baud rate {baud}, using 115200", level=2)
            self.config['baud_rate'] = 115200
        
        # Validate timezone offset
        tz_offset = self.config.get('timezone_offset', 0)
        if not isinstance(tz_offset, (int, float)) or tz_offset < -12 or tz_offset > 14:
            resilience.log(f"Warning: Invalid timezone offset {tz_offset}, using 0", level=2)
            self.config['timezone_offset'] = 0
        
        # Validate drives is a list of 4 items
        drives = self.config.get('drives')
        if not isinstance(drives, list) or len(drives) != 4:
            resilience.log("Warning: Invalid drives config, using defaults", level=2)
            self.config['drives'] = [None] * 4

        # Validate remote_servers is a list of dicts
        rs = self.config.get('remote_servers')
        if not isinstance(rs, list):
            resilience.log("Warning: Invalid remote_servers config, using defaults", level=2)
            self.config['remote_servers'] = []

shared_config = Config()
