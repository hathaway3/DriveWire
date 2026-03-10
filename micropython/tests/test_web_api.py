import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# CRITICAL: Mock EVERYTHING before web_server is even considered for import
mock_microdot_app = MagicMock()
mock_microdot_app.route.return_value = lambda f: f
mock_microdot_app.errorhandler.return_value = lambda f: f

class MockMicrodot:
    def __init__(self):
        pass
    def route(self, *args, **kwargs):
        return lambda f: f
    def errorhandler(self, *args, **kwargs):
        return lambda f: f

# Mock modules
sys.modules['micropython'] = MagicMock()
sys.modules['uasyncio'] = MagicMock()
sys.modules['microdot_asyncio'] = MagicMock()
sys.modules['microdot_asyncio'].Microdot = MockMicrodot
sys.modules['microdot'] = sys.modules['microdot_asyncio']
sys.modules['machine'] = MagicMock()
sys.modules['utime'] = MagicMock()
sys.modules['activity_led'] = MagicMock()
sys.modules['resilience'] = MagicMock()
sys.modules['time_sync'] = MagicMock()
sys.modules['sd_card'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['gc'] = MagicMock()

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import web_server
import web_server

class TestWebAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Reset global states
        web_server._creating_disk = False
        web_server._disk_creation_progress = {'state': 'idle', 'written': 0, 'total': 0, 'filename': '', 'error': None}
        web_server.app.dw_server = MagicMock()
        web_server.app.dw_server.drives = [None, None, None, None]

    @patch('web_server.os.statvfs')
    @patch('web_server.os.stat')
    @patch('web_server.asyncio.create_task')
    async def test_create_blank_disk_accepted(self, mock_create_task, mock_stat, mock_statvfs):
        """Test that the endpoint returns 202 Accepted and starts a task."""
        mock_statvfs.return_value = (4096, 4096, 1000, 1000, 1000, 0, 0, 0, 0, 255) # Plenty of space
        mock_stat.side_effect = OSError() # File does not exist

        request = MagicMock()
        request.json = {'filename': 'test.dsk', 'size': 1024}
        
        # Call the endpoint directly
        response, status = await web_server.create_blank_dsk_endpoint(request)
        
        self.assertEqual(status, 202)
        self.assertEqual(response['status'], 'accepted')
        self.assertTrue(web_server._creating_disk)
        self.assertEqual(web_server._disk_creation_progress['state'], 'creating')
        mock_create_task.assert_called_once()

    async def test_create_status_endpoint(self):
        """Test the status endpoint returns current progress."""
        web_server._disk_creation_progress = {'state': 'creating', 'written': 512, 'total': 1024, 'filename': 'test.dsk', 'error': None}
        
        response = await web_server.create_disk_status_endpoint(None)
        self.assertEqual(response['state'], 'creating')
        self.assertEqual(response['written'], 512)

if __name__ == "__main__":
    unittest.main()
