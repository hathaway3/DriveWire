import json
import os

CONFIG_FILE = 'config.json'

# Valid baud rates for UART
VALID_BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

DEFAULT_CONFIG = {
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
    "sd_mount_point": "/sd"
}

class Config:
    """Configuration manager with validation and persistence."""
    
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Load configuration from file, merging with defaults."""
        try:
            with open(CONFIG_FILE, 'r') as f:
                stored_config = json.load(f)
                # Update default config with stored values
                for key, value in stored_config.items():
                    self.config[key] = value
                # Validate after loading
                self.validate()
        except (OSError, ValueError) as e:
            print(f"Config file error: {e}. Using defaults.")
            self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f)
        except OSError as e:
            print(f"Config save error: {e}")

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        if key not in DEFAULT_CONFIG:
            print(f"Warning: Unknown config key '{key}'")
            return
        self.config[key] = value
        self.save()
    
    def validate(self):
        """Validate configuration values."""
        # Validate baud rate
        baud = self.config.get('baud_rate')
        if baud not in VALID_BAUD_RATES:
            print(f"Warning: Invalid baud rate {baud}, using 115200")
            self.config['baud_rate'] = 115200
        
        # Validate timezone offset
        tz_offset = self.config.get('timezone_offset', 0)
        if not isinstance(tz_offset, (int, float)) or tz_offset < -12 or tz_offset > 14:
            print(f"Warning: Invalid timezone offset {tz_offset}, using 0")
            self.config['timezone_offset'] = 0
        
        # Validate drives is a list of 4 items
        drives = self.config.get('drives')
        if not isinstance(drives, list) or len(drives) != 4:
            print("Warning: Invalid drives config, using defaults")
            self.config['drives'] = [None] * 4

shared_config = Config()
