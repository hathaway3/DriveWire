import json
import os

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    "wifi_ssid": "YOUR_SSID",
    "wifi_password": "YOUR_PASSWORD",
    "baud_rate": 115200,
    "drives": [None] * 4,  # 4 Virtual Drives
    "ntp_server": "pool.ntp.org",
    "timezone_offset": 0, # Hours from UTC
    "serial_map": {} # { "0": {"host": "towel.blinkenlights.nl", "port": 23} }
}

class Config:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                stored_config = json.load(f)
                # Update default config with stored values (handling missing keys)
                for key, value in stored_config.items():
                    self.config[key] = value
        except (OSError, ValueError):
            print("Config file not found or invalid, using defaults.")
            self.save()

    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.save()

shared_config = Config()
