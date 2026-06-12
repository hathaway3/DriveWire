import json
import os
import resilience

try:
    from typing import Optional, List, Dict, Any, Union
except ImportError:
    pass

CONFIG_FILE = 'config.json'
_CONFIG_TMP = 'config.tmp'

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
    "wdt_enabled": False,
    "log_level": 1,  # 0=Debug, 1=Info, 2=Warn, 3=Error, 4=Crit
    "remote_servers": []  # [{"name": "Dev", "url": "http://192.168.1.100:8080"}, ...]
}

class Config:
    """Configuration manager with validation and persistence."""
    
    def __init__(self):
        self.config = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in DEFAULT_CONFIG.items()}
        self.load()

    def load(self) -> None:
        """Load configuration from file, merging with defaults.
        
        Recovery: If config.json is corrupt but config.tmp exists and is valid,
        promote the temp file (it was a complete write that didn't get renamed).
        """
        # Try primary config file first
        loaded = self._try_load_file(CONFIG_FILE)
        if not loaded:
            # Primary is missing or corrupt — try recovering from temp
            loaded = self._try_load_file(_CONFIG_TMP)
            if loaded:
                resilience.log("Recovered config from temp file after crash", level=2)
                # Promote temp to primary
                try:
                    os.rename(_CONFIG_TMP, CONFIG_FILE)
                except OSError:
                    pass
            else:
                # Both missing or corrupt — save defaults
                resilience.log("No valid config found, saving defaults", level=2)
                self.save()

    def _try_load_file(self, filepath: str) -> bool:
        """Attempt to load and merge config from a specific file. Returns True on success."""
        try:
            try:
                os.stat(filepath)
            except OSError:
                return False
            with open(filepath, 'r') as f:
                stored_config = json.load(f)
                for key, value in stored_config.items():
                    self.config[key] = value
                self.validate()
                return True
        except (OSError, ValueError) as e:
            resilience.log(f"Config file error ({filepath}): {e}", level=2)
            return False

    def save(self) -> bool:
        """Save configuration to flash using atomic write (temp + rename)."""
        try:
            # Write to temp file first
            with open(_CONFIG_TMP, 'w') as f:
                json.dump(self.config, f)
            try:
                os.sync()
            except AttributeError:
                pass
            # Atomic rename: if this succeeds, config is guaranteed consistent
            try:
                os.remove(CONFIG_FILE)
            except OSError:
                pass  # File may not exist yet (first save)
            os.rename(_CONFIG_TMP, CONFIG_FILE)
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
        self.validate()
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
            self.validate()
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
            tz_offset = 0
        resilience.set_timezone_offset(int(tz_offset))
        
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

        # Validate log level and sync with resilience module
        ll = self.config.get('log_level', 1)
        if not isinstance(ll, int) or ll < 0 or ll > 4:
            resilience.log(f"Warning: Invalid log level {ll}, using 1 (INFO)", level=2)
            ll = 1
            self.config['log_level'] = 1
        resilience.MIN_LOG_LEVEL = ll

shared_config = Config()
