import asyncio
import struct
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Mock MicroPython modules
class MockUART:
    def __init__(self, *args, **kwargs):
        self.input_buffer = bytearray()
        self.output_buffer = bytearray()
        self.baudrate = kwargs.get('baudrate', 115200)

    def write(self, data):
        self.output_buffer.extend(data)
        return len(data)

    def read(self, n=None):
        if n is None:
            res = self.input_buffer
            self.input_buffer = bytearray()
            return res
        res = self.input_buffer[:n]
        self.input_buffer = self.input_buffer[n:]
        return res

    def any(self):
        return len(self.input_buffer) > 0

    def deinit(self):
        pass

# Mock micropython
mock_micropython = MagicMock()
mock_micropython.const = lambda x: x
sys.modules['micropython'] = mock_micropython

# Setup mocks before importing drivewire
sys.modules['machine'] = MagicMock()
sys.modules['machine'].UART = MockUART
sys.modules['uasyncio'] = asyncio

# Mock utime 
mock_utime = MagicMock()
mock_utime.ticks_us.return_value = 0
mock_utime.ticks_diff.return_value = 0
sys.modules['utime'] = mock_utime

# Mock time_sync
mock_time_sync = MagicMock()
mock_time_sync.get_local_time.return_value = (2026, 2, 12, 9, 0, 0, 3, 43)
sys.modules['time_sync'] = mock_time_sync

# Mock ntptime
sys.modules['ntptime'] = MagicMock()

# Mock resilience.open_remote_stream for RemoteDrive tests
sys.modules['resilience'] = MagicMock()
mock_resilience = sys.modules['resilience']
sys.modules['activity_led'] = MagicMock()

# Mock os.sync
if not hasattr(os, 'sync'):
    os.sync = lambda: None

# Mock config
import json
mock_config_data = {
    "baud_rate": 115200,
    "drives": [None, None, None, None],
    "serial_map": {}
}
if not os.path.exists("config.json"):
    with open("config.json", "w") as f:
        json.dump(mock_config_data, f)

# Now we can import DriveWireServer
sys.path.append(os.getcwd())
from drivewire import (
    DriveWireServer, RemoteDrive, VirtualDrive,
    OP_DWINIT, OP_READ, OP_WRITE, OP_TIME, OP_RESET,
    OP_PRINT, OP_PRINTFLUSH, OP_SERREAD, OP_SERWRITE, OP_SERINIT, OP_SERTERM,
    OP_NAMEOBJ_MOUNT, SECTOR_SIZE,
    E_NONE, E_UNIT, E_WP, E_READ, E_NOTRDY
)

class TestDriveWire(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Ensure dummy files exist
        with open("test_drive.dsk", "wb") as f:
            f.write(b"\x00" * 256 * 10)
        
        self.server = DriveWireServer()
        self.uart = self.server.uart
        self.server.running = True

    async def asyncTearDown(self):
        self.server.stop()
        if os.path.exists("test_drive.dsk"):
            try: os.remove("test_drive.dsk")
            except Exception: pass
        if os.path.exists("test_mount.dsk"):
            try: os.remove("test_mount.dsk")
            except Exception: pass

    def inject_input(self, data):
        self.uart.input_buffer.extend(data)

    def get_output(self):
        res = self.uart.output_buffer
        self.uart.output_buffer = bytearray()
        return res

    async def test_handshake_dwinit(self):
        self.inject_input(bytes([OP_DWINIT, 0]))
        task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertTrue(len(output) >= 1)
        self.assertEqual(output[0], 0)
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    async def test_time_sync(self):
        self.inject_input(bytes([OP_TIME]))
        task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertEqual(len(output), 6)
        self.assertEqual(output[0], 126) # 2026 - 1900
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    async def test_printer(self):
        self.inject_input(bytes([OP_PRINT, ord('H'), OP_PRINT, ord('i')]))
        self.inject_input(bytes([OP_PRINTFLUSH]))
        task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.2)
        self.assertEqual(len(self.server.print_buffer), 0)
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    async def test_disk_read_write(self):
        drives = [None] * 4
        drives[0] = "test_drive.dsk"
        self.server.config.set("drives", drives)
        self.server.reload_config()
        self.uart = self.server.uart
        
        # READ
        self.inject_input(bytes([OP_READ, 0, 0, 0, 0]))
        task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertEqual(output[0], 0)
        
        # WRITE
        data_to_write = b"XYZ" + b" " * 253
        cs = sum(data_to_write) & 0xFFFF
        self.inject_input(bytes([OP_WRITE, 0, 0, 0, 2]) + data_to_write + struct.pack(">H", cs))
        await asyncio.sleep(0.2)
        
        # VERIFY
        self.inject_input(bytes([OP_READ, 0, 0, 0, 2]))
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertEqual(output[-256:], data_to_write)
        
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    async def test_serial_ops(self):
        # Mock connection success instead of error
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_reader.read.return_value = b"" 
        
        with patch('asyncio.open_connection', return_value=(mock_reader, mock_writer)):
            self.server.config.set("serial_map", {"1": {"host": "127.0.0.1", "port": 9999}})
            self.inject_input(bytes([OP_SERINIT, 1]))
            task = asyncio.create_task(self.server.run())
            await asyncio.sleep(0.2)
            
            # Now test SERREAD
            self.server.channels[0].extend(b"H")
            self.inject_input(bytes([OP_SERREAD]))
            await asyncio.sleep(0.2)
            output = self.get_output()
            self.assertTrue(len(output) >= 2)
            self.assertEqual(output[-2], 1) # Channel 0 + 1
            self.assertEqual(output[-1], ord('H'))
            
            # Test SERWRITE
            self.inject_input(bytes([OP_SERWRITE, 1, ord('P')]))
            await asyncio.sleep(0.2)
            mock_writer.write.assert_called_with(b'P')
            mock_writer.drain.assert_called()
        
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    async def test_extended_ops(self):
        from drivewire import OP_READEX, OP_REREAD, OP_REWRITE, OP_REREADEX
        # Standard Setup
        drives = ["test_drive.dsk"] + [None]*3
        self.server.config.set("drives", drives)
        self.server.reload_config()
        self.uart = self.server.uart
        
        # READEX
        self.inject_input(bytes([OP_READEX, 0, 0, 0, 0]))
        task = asyncio.create_task(self.server.run())
        
        # Wait for data to be written
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertTrue(len(output) >= 256)
        
        # Send checksum
        valid_cs = self.server.checksum(output[:256])
        self.inject_input(bytes([valid_cs >> 8, valid_cs & 0xFF]))
        await asyncio.sleep(0.1)
        
        output = self.get_output()
        self.assertTrue(len(output) >= 1) # Should be ACK
        self.assertEqual(output[-1], 0) # ACK

        # REREAD
        self.inject_input(bytes([OP_REREAD, 0, 0, 0, 0]))
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertTrue(len(output) > 2)

        # REWRITE (Same as WRITE)
        data = b"W" * 256
        cs = sum(data) & 0xFFFF
        self.inject_input(bytes([OP_REWRITE, 0, 0, 0, 3]) + data + struct.pack(">H", cs))
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertEqual(output[-1], 0) # ACK

        task.cancel()
        try:
            await task
        except asyncio.CancelledError: pass

    async def test_serterm(self):
        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_reader.read.return_value = b"" # Fix: Avoid infinite loop if reader task starts
        
        with patch('asyncio.open_connection', return_value=(mock_reader, mock_writer)):
            self.server.config.set("serial_map", {"2": {"host": "127.0.0.1", "port": 8888}})
            self.inject_input(bytes([OP_SERINIT, 2]))
            task = asyncio.create_task(self.server.run())
            await asyncio.sleep(0.2)
            self.assertIn(2, self.server.tcp_connections)
            
            # Now Terminate
            self.inject_input(bytes([OP_SERTERM, 2]))
            await asyncio.sleep(0.2)
            self.assertNotIn(2, self.server.tcp_connections)
            mock_writer.close.assert_called()
        
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    async def test_named_obj(self):
        # Create a file to mount
        with open("test_mount.dsk", "wb") as f:
            f.write(b"MOUNTME")
            
        # OP_NAMEOBJ_MOUNT ($01) + Len (14) + "test_mount.dsk"
        name = "test_mount.dsk"
        self.inject_input(bytes([OP_NAMEOBJ_MOUNT, len(name)]) + name.encode('ascii'))
        
        task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.2)
        
        output = self.get_output()
        # Should return drive number (e.g. 1 if 0 is taken)
        self.assertTrue(len(output) >= 1)
        drive_num = output[-1]
        self.assertTrue(0 <= drive_num < 4)
        self.assertIsNotNone(self.server.drives[drive_num])
        
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

class TestRemoteDrive(unittest.TestCase):
    def setUp(self):
        # Reset resilience mock
        mock_resilience.open_remote_stream.reset_mock()
        mock_resilience.open_remote_stream.side_effect = None
        
        self.drive = RemoteDrive('http://192.168.1.100:8080')
        mock_resilience.open_remote_stream.reset_mock()

    def test_remote_read_sector(self):
        """Remote read should use open_remote_stream and return sector data."""
        sector_data = bytes(range(256)) * 8  # Mock 8 sectors
        
        mock_sock = MagicMock()
        def mock_readinto(buf):
            size = min(len(buf), len(sector_data))
            buf[:size] = sector_data[:size]
            return size
        mock_sock.readinto.side_effect = mock_readinto
        mock_resilience.open_remote_stream.return_value = mock_sock

        result = self.drive.read_sector(5)
        self.assertEqual(result, bytes(range(256))) # Should return the 1 sector requested
        mock_resilience.open_remote_stream.assert_called_with('http://192.168.1.100:8080/sectors/5?count=8')
        mock_sock.close.assert_called()
        self.assertEqual(self.drive.stats['read_misses'], 1)

    def test_remote_write_protected(self):
        """Remote drives should reject writes."""
        result = self.drive.write_sector(0, bytes(256))
        self.assertFalse(result)

    def test_remote_cache_hit(self):
        """Second read of same sector should come from cache."""
        sector_data = bytes(range(256)) * 8  # Mock 8 sectors
        
        mock_sock = MagicMock()
        def mock_readinto(buf):
            size = min(len(buf), len(sector_data))
            buf[:size] = sector_data[:size]
            return size
        mock_sock.readinto.side_effect = mock_readinto
        mock_resilience.open_remote_stream.return_value = mock_sock

        # First read = cache miss
        self.drive.read_sector(10)
        self.assertEqual(self.drive.stats['read_misses'], 1)
        self.assertEqual(self.drive.stats['read_hits'], 0)

        mock_resilience.open_remote_stream.reset_mock()

        # Second read = cache hit (no network call)
        result = self.drive.read_sector(10)
        self.assertEqual(result, bytes(range(256)))
        self.assertEqual(self.drive.stats['read_hits'], 1)
        mock_resilience.open_remote_stream.assert_not_called()

    def test_remote_network_error_sets_notrdy(self):
        """Network failure should set last_error to E_NOTRDY."""
        mock_resilience.open_remote_stream.side_effect = OSError("Network unreachable")

        result = self.drive.read_sector(0)
        self.assertIsNone(result)
        self.assertEqual(self.drive.last_error, E_NOTRDY)

    def test_remote_write_sets_wp_error(self):
        """Write attempts should set last_error to E_WP."""
        result = self.drive.write_sector(0, bytes(256))
        self.assertFalse(result)
        self.assertEqual(self.drive.last_error, E_WP)


class TestSwapDrive(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with open("test_drive.dsk", "wb") as f:
            f.write(b"\x00" * 256 * 10)
        with open("test_swap.dsk", "wb") as f:
            f.write(b"\xff" * 256 * 10)
        self.server = DriveWireServer()

    async def asyncTearDown(self):
        self.server.stop()
        for fn in ["test_drive.dsk", "test_swap.dsk"]:
            if os.path.exists(fn):
                try: os.remove(fn)
                except Exception: pass

    async def test_swap_drive_replaces_only_target(self):
        """swap_drive should replace only the target drive slot."""
        old_drive = VirtualDrive("test_drive.dsk")
        self.server.drives[0] = old_drive
        self.server.drives[1] = None

        new_drive = VirtualDrive("test_swap.dsk")
        result = self.server.swap_drive(0, new_drive)

        self.assertTrue(result)
        self.assertEqual(self.server.drives[0].filename, "test_swap.dsk")
        self.assertIsNone(self.server.drives[1])  # Other drives unaffected

    async def test_swap_drive_transfers_cache(self):
        """swap_drive should copy read cache to new drive."""
        old_drive = VirtualDrive("test_drive.dsk")
        old_drive.read_cache = {0: bytes(256), 5: bytes(256)}
        self.server.drives[2] = old_drive

        new_drive = VirtualDrive("test_swap.dsk")
        self.server.swap_drive(2, new_drive)

        self.assertIn(0, self.server.drives[2].read_cache)
        self.assertIn(5, self.server.drives[2].read_cache)

    async def test_reload_config_http_url(self):
        """reload_config should create RemoteDrive for http:// paths."""
        # Setup mock for RemoteDrive constructor check
        mock_resilience.open_remote_stream.return_value = MagicMock()

        self.server.config.config['drives'] = [
            'http://192.168.1.100:8080', None, None, None
        ]
        self.server.reload_config()

        self.assertIsInstance(self.server.drives[0], RemoteDrive)
        self.assertIsNone(self.server.drives[1])


if __name__ == "__main__":
    unittest.main()
