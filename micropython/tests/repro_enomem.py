import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock

# Define MockMicrodot FIRST
class MockMicrodot:
    def __init__(self):
        self.dw_server = MagicMock()
    def route(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator
    def errorhandler(self, *args, **kwargs):
        return lambda f: f

# Mock modules
mock_microdot_asyncio = MagicMock()
mock_microdot_asyncio.Microdot = MockMicrodot
mock_microdot_asyncio.Response = MagicMock

sys.modules['microdot_asyncio'] = mock_microdot_asyncio
sys.modules['microdot'] = mock_microdot_asyncio
sys.modules['micropython'] = MagicMock()
sys.modules['uasyncio'] = MagicMock()
sys.modules['machine'] = MagicMock()
sys.modules['utime'] = MagicMock()
sys.modules['activity_led'] = MagicMock()
sys.modules['resilience'] = MagicMock()
sys.modules['time_sync'] = MagicMock()
sys.modules['sd_card'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['gc'] = MagicMock()
sys.modules['usocket'] = MagicMock()
sys.modules['drivewire'] = MagicMock()

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web_server

class MockSocket:
    def __init__(self, data):
        self.data = data
        self.pos = 0
    def recv(self, n):
        chunk = self.data[self.pos:self.pos+n]
        self.pos += n
        return chunk
    def close(self):
        pass

class TestStreamingInfo(unittest.IsolatedAsyncioTestCase):
    def test_stream_remote_info_large_payload(self):
        """Test that stream_remote_info yields disks from a large JSON payload."""
        disks = []
        for i in range(100):
            disks.append({"name": f"disk_{i}.dsk", "size": 1024, "total_sectors": 4})
        
        info_json = json.dumps({
            "name": "Test Server",
            "version": "1.0",
            "disk_count": 100,
            "disks": disks
        }).encode()
        
        mock_sock = MockSocket(info_json)
        
        with patch('web_server.resilience.open_remote_stream', return_value=mock_sock):
            yielded_disks = list(web_server.stream_remote_info("http://mock"))
            
            self.assertEqual(len(yielded_disks), 100)
            self.assertEqual(yielded_disks[0]['name'], "disk_0.dsk")
            self.assertEqual(yielded_disks[-1]['name'], "disk_99.dsk")

    @patch('web_server.resilience.open_remote_stream')
    async def test_remote_clone_endpoint_uses_streaming(self, mock_open_stream):
        """Test that remote_clone_endpoint uses the streaming parser to find total_sectors."""
        # Setup mock info
        disks = [{"name": "target.dsk", "total_sectors": 1234}]
        info_json = json.dumps({"disks": disks}).encode()
        
        mock_sock = MockSocket(info_json)
        mock_open_stream.return_value = mock_sock
        
        # Mock request
        request = MagicMock()
        request.json = {
            'remote_url': 'http://remote',
            'disk_name': 'target.dsk',
            'drive_num': 0
        }
        
        # Mock os.statvfs and other globals
        with patch('web_server.os.statvfs', return_value=(4096, 4096, 1000, 1000, 1000, 0, 0, 0, 0, 255)), \
             patch('web_server.asyncio.create_task'), \
             patch('web_server.os.stat', side_effect=OSError()): # target does not exist
            
            web_server.app.dw_server = MagicMock()
            web_server.app.dw_server.swap_drive = AsyncMock()
            
            result = await web_server.remote_clone_endpoint(request)
            
            # Verify the progress was set correctly
            self.assertEqual(web_server._clone_progress['total'], 1234)

if __name__ == "__main__":
    unittest.main()
