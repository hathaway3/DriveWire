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

if __name__ == '__main__':
    unittest.main()
