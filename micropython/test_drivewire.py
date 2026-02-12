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

# Mock time_sync
mock_time_sync = MagicMock()
mock_time_sync.get_local_time.return_value = (2026, 2, 12, 9, 0, 0, 3, 43)
sys.modules['time_sync'] = mock_time_sync

# Mock ntptime
sys.modules['ntptime'] = MagicMock()

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
    DriveWireServer, OP_DWINIT, OP_READ, OP_WRITE, OP_TIME, OP_RESET,
    OP_PRINT, OP_PRINTFLUSH, OP_SERREAD, OP_SERWRITE, OP_SERINIT, OP_SERTERM,
    OP_NAMEOBJ_MOUNT
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
            except: pass
        if os.path.exists("test_mount.dsk"):
            try: os.remove("test_mount.dsk")
            except: pass

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
        from drivewire import OP_READEX, OP_REREAD, OP_REWRITE
        # Standard Setup
        drives = ["test_drive.dsk"] + [None]*3
        self.server.config.set("drives", drives)
        self.server.reload_config()
        self.uart = self.server.uart
        
        # Extended Read: CoCo sends CS after data
        self.inject_input(bytes([OP_READEX, 0, 0, 0, 0]))
        # CoCo Checksum for "all zeros" (our dummy drive start) is 0
        self.inject_input(struct.pack(">H", 0))
        
        task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.3) # More time for extended
        output = self.get_output()
        self.assertTrue(len(output) >= 256)
        self.assertEqual(output[-1], 0) # ACK

        # REREAD (Same as READ)
        self.inject_input(bytes([OP_REREAD, 0, 0, 0, 0]))
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertEqual(output[0], 0)

        # REWRITE (Same as WRITE)
        data = b"W" * 256
        cs = sum(data) & 0xFFFF
        self.inject_input(bytes([OP_REWRITE, 0, 0, 0, 3]) + data + struct.pack(">H", cs))
        await asyncio.sleep(0.2)
        output = self.get_output()
        self.assertEqual(output[-1], 0) # ACK

        task.cancel()
        try: await task
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

if __name__ == "__main__":
    unittest.main()
