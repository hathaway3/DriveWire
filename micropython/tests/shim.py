import sys
import asyncio
from unittest.mock import MagicMock

# Define all MicroPython specific modules to mock
MOCK_MODULES = [
    'machine', 
    'network', 
    'utime', 
    'uhashlib', 
    'ubinascii', 
    'uasyncio', 
    'micropython',
    'activity_led',
    'syslog',
    'microdot',
    'time_sync',
    'config'
]

def setup_all_mocks():
    # 1. Config Mock
    if 'config' not in sys.modules or getattr(sys.modules['config'], '__is_shim__', False) == False:
        mock_config = MagicMock()
        mock_config.__is_shim__ = True
        
        class MockSharedConfig:
            def __init__(self):
                self.config = {
                    "baud_rate": 115200,
                    "wifi_ssid": "",
                    "wifi_pass": "",
                    "remote_servers": [],
                    "drives": ["", "", "", ""]
                }
            def get(self, key, default=None):
                return self.config.get(key, default)
            def update(self, changes):
                self.config.update(changes)
        
        mock_config.shared_config = MockSharedConfig()
        sys.modules['config'] = mock_config

    # 2. Universal Mocks
    for m in MOCK_MODULES:
        if m == 'config': continue
        if m not in sys.modules or isinstance(sys.modules[m], MagicMock):
            mock = MagicMock()
            
            if m == 'micropython':
                mock.const = lambda x: x
            
            if m == 'uasyncio':
                # CRITICAL: uasyncio.sleep must be awaitable
                async def real_sleep(delay=0):
                    await asyncio.sleep(0)
                mock.sleep = real_sleep
                mock.create_task = asyncio.create_task
                mock.Event = asyncio.Event
                mock.Lock = asyncio.Lock
            
            if m == 'utime':
                import time
                mock.ticks_us = lambda: int(time.time() * 1000000)
                mock.ticks_ms = lambda: int(time.time() * 1000)
                mock.ticks_diff = lambda a, b: a - b
                mock.sleep = time.sleep
                mock.sleep_ms = lambda ms: time.sleep(ms / 1000.0)

            if m == 'microdot':
                def mock_decorator(*args, **kwargs):
                    def wrapper(f):
                        return f
                    return wrapper
                class MockMicrodot:
                    def __init__(self):
                        self.post = mock_decorator
                        self.get = mock_decorator
                        self.put = mock_decorator
                        self.delete = mock_decorator
                        self.route = mock_decorator
                        self.errorhandler = mock_decorator
                        self.dw_server = MagicMock()
                mock.Microdot = MockMicrodot
                
            sys.modules[m] = mock

setup_all_mocks()
