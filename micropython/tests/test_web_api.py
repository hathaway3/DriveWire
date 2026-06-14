import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json

# Centralized MicroPython mocking shim
import tests.shim as shim
shim.setup_all_mocks()

# Ensure we have a mock for os.sync which Python 3 on Windows lacks
if not hasattr(os, 'sync'):
    os.sync = lambda: None

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web_server

class TestWebAPI(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Isolate sys.modules to prevent mock leakage during discovery
        cls.patcher = patch.dict('sys.modules', {
            'machine': MagicMock(),
            'network': MagicMock(),
            'time_sync': MagicMock(),
            'config': sys.modules['config'] # Keep our functional mock from shim
        })
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        # Reset global states in web_server
        web_server._creating_disk = False
        # Setup app and dw_server mocks
        web_server.app.dw_server = MagicMock()
        web_server.app.dw_server.drives = [None, None, None, None]

    @patch('web_server.os.statvfs', create=True)
    @patch('web_server.os.stat')
    @patch('web_server.asyncio.create_task')
    async def test_create_blank_disk_accepted(self, mock_create_task, mock_stat, mock_statvfs):
        # Mock free space (>1MB)
        mock_statvfs.return_value = (4096, 4096, 1000, 1000, 1000, 0, 0, 0, 0, 255)
        # Mock file not existing
        mock_stat.side_effect = OSError("File not found")
        
        request = MagicMock()
        request.json = {"filename": "test_new.dsk", "size": 161280}
        
        # Now use the real function directly
        response, status = await web_server.create_blank_dsk_endpoint(request)
        
        self.assertEqual(status, 202)
        self.assertIn("accepted", response["status"])
        mock_create_task.assert_called()

    async def test_create_blank_disk_duplicate(self):
        web_server._creating_disk = True
        request = MagicMock()
        request.json = {"filename": "test.dsk", "size": 161280}
        
        response, status = await web_server.create_blank_dsk_endpoint(request)
        self.assertEqual(status, 409)
        self.assertIn("already in progress", response["error"])

    async def test_remote_clone_invalid_input(self):
        request = MagicMock()
        request.json = {"source_url": "", "drive": 5}
        
        response, status = await web_server.remote_clone_endpoint(request)
        self.assertEqual(status, 400)
        self.assertIn("Missing remote_url", response["error"])

    async def test_config_get(self):
        from config import shared_config
        # Our shim provides a shared_config that is a dict/MagicMock combination
        shared_config.config["baud_rate"] = 115200
        
        response = await web_server.config_endpoint(MagicMock(method='GET'))
        self.assertEqual(response["baud_rate"], 115200)

    async def test_config_post_masked_password_ignored(self):
        from config import shared_config
        shared_config.config["wifi_password"] = "actual_secret"
        
        request = MagicMock(method='POST')
        request.json = {"wifi_password": "********", "baud_rate": 115200}
        
        await web_server.config_endpoint(request)
        self.assertEqual(shared_config.config["wifi_password"], "actual_secret")
        self.assertEqual(shared_config.config["baud_rate"], 115200)

    async def test_config_post_new_password_saved(self):
        from config import shared_config
        shared_config.config["wifi_password"] = "old_secret"
        
        request = MagicMock(method='POST')
        request.json = {"wifi_password": "new_secret"}
        
        await web_server.config_endpoint(request)
        self.assertEqual(shared_config.config["wifi_password"], "new_secret")

    async def test_stream_remote_info_handles_structural_chars_in_names(self):
        # Defect #9: the streaming /info parser counted '{','}','[',']' and ','
        # even inside string values, so a disk name containing any of them
        # miscounted depth and dropped or merged entries. A string-aware parser
        # must yield every disk verbatim regardless of chunk boundaries.
        payload = json.dumps({
            "version": "1.0",
            "disks": [
                {"name": "weird{name},[v2]", "size": 161280},
                {"name": "quote\"inside", "size": 100},
                {"name": "normal.dsk", "size": 200},
            ],
        }).encode()

        class _InfoSocket:
            def __init__(self, data, chunk=7):
                self._data, self._pos, self._chunk = data, 0, chunk
                self.closed = False
            def recv(self, n):
                end = min(self._pos + self._chunk, len(self._data))
                out = self._data[self._pos:end]
                self._pos = end
                return out
            def close(self):
                self.closed = True

        sock = _InfoSocket(payload)
        with patch('web_server.resilience.open_remote_stream', return_value=sock):
            disks = list(web_server.stream_remote_info("http://host:6809"))

        self.assertEqual(
            [d["name"] for d in disks],
            ["weird{name},[v2]", "quote\"inside", "normal.dsk"],
        )
        self.assertTrue(sock.closed)


if __name__ == '__main__':
    unittest.main()
