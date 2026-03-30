import asyncio
import struct
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Centralized MicroPython mocking shim
import tests.shim as shim
shim.setup_all_mocks()

# Ensure we have a mock for os.sync which Python 3 on Windows lacks
if not hasattr(os, 'sync'):
    os.sync = lambda: None

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock UART for DriveWire tests
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

# Import AFTER shim setup
import drivewire
from drivewire import (
    DriveWireServer, OP_DWINIT, OP_READ, OP_READEX, OP_WRITE, OP_NAMEOBJ_MOUNT,
    OP_NAMEOBJ_CREATE, OP_TIME, E_NONE, E_UNIT, E_CRC, E_WP,
    OP_SERINIT, OP_SERTERM, OP_SERWRITE, OP_SERREAD, OP_PRINT, OP_PRINTFLUSH,
    NUM_DRIVES
)

class TestDriveWire(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Isolate sys.modules to prevent mock leakage during discovery
        cls.patcher = patch.dict('sys.modules', {
            'machine': MagicMock(),
            'network': MagicMock(),
            'time_sync': MagicMock(),
            'utime': MagicMock() # Ensure utime is mocked consistently
        })
        cls.patcher.start()
        
        # Configure time_sync specifically for our tests
        import time_sync
        time_sync.get_local_time = MagicMock(return_value=(2026, 3, 28, 1, 51, 0, 5, 87))

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    async def asyncSetUp(self):
        # Patch UART so we can inject byte streams
        self.uart_mock = MockUART()
        with patch('drivewire.UART', return_value=self.uart_mock):
            self.server = DriveWireServer()
            self.server.uart = self.uart_mock
        # Patch init_drives to prevent run() from wiping test-configured drives
        self._init_drives_patcher = patch.object(self.server, 'init_drives')
        self._init_drives_patcher.start()
        
        # Pre-create test disk files
        self.test_dsk = "test_drive.dsk"
        with open(self.test_dsk, "wb") as f:
            f.write(bytes([0x55] * 256 * 10))
            
        self.test_mount = "test_mount.dsk"
        with open(self.test_mount, "wb") as f:
            f.write(bytes([0xAA] * 256 * 10))

    async def asyncTearDown(self):
        self._init_drives_patcher.stop()
        if hasattr(self, 'server'):
            await self.server.stop()
        
        await asyncio.sleep(0.05)
        
        for f in [self.test_dsk, self.test_mount, "test_swap.dsk", "test_verify.dsk", "system.log"]:
            if os.path.exists(f):
                try: os.remove(f)
                except OSError: pass

    async def test_dwinit_handshake(self):
        self.uart_mock.input_buffer.extend([OP_DWINIT, 0x00])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        self.assertEqual(list(self.uart_mock.output_buffer), [0x00])

    async def test_read_opcode_standard(self):
        vd = drivewire.VirtualDrive(self.test_dsk)
        self.server.drives[0] = vd
        self.uart_mock.input_buffer.extend([OP_READ, 0x00, 0x00, 0x00, 0x01])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        expected_cs = (256 * 0x55) & 0xFFFF
        self.assertEqual(self.uart_mock.output_buffer[0], 0x00)
        self.assertEqual(self.uart_mock.output_buffer[1], (expected_cs >> 8) & 0xFF)
        self.assertEqual(self.uart_mock.output_buffer[2], expected_cs & 0xFF)
        self.assertEqual(list(self.uart_mock.output_buffer[3:]), [0x55] * 256)

    async def test_read_opcode_extended(self):
        vd = drivewire.VirtualDrive(self.test_dsk)
        self.server.drives[0] = vd
        self.uart_mock.input_buffer.extend([OP_READEX, 0x00, 0x00, 0x00, 0x02])
        expected_cs = (256 * 0x55) & 0xFFFF
        async def coco_response():
            await asyncio.sleep(0.02)
            self.uart_mock.input_buffer.extend([(expected_cs >> 8) & 0xFF, expected_cs & 0xFF])
        asyncio.create_task(coco_response())
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        self.assertEqual(list(self.uart_mock.output_buffer[:256]), [0x55] * 256)
        self.assertEqual(self.uart_mock.output_buffer[256], 0x00)

    async def test_write_opcode(self):
        vd = drivewire.VirtualDrive(self.test_dsk)
        self.server.drives[1] = vd
        test_data = [0xAA] * 256
        cs = (sum(test_data)) & 0xFFFF
        self.uart_mock.input_buffer.extend([OP_WRITE, 0x01, 0x00, 0x00, 0x05])
        self.uart_mock.input_buffer.extend(test_data)
        self.uart_mock.input_buffer.extend([(cs >> 8) & 0xFF, cs & 0xFF])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        # Server ACKs with E_NONE (0x00) on success
        self.assertEqual(list(self.uart_mock.output_buffer), [0x00])
        # After stop(), dirty_sectors are flushed to disk and cleared.
        # Verify the data was persisted correctly by reading the file.
        with open(self.test_dsk, 'rb') as f:
            f.seek(5 * 256)  # LSN 5
            on_disk = f.read(256)
        self.assertEqual(on_disk, bytes(test_data))

    async def test_write_protected_error(self):
        remote_drive = MagicMock()
        remote_drive.write_sector = AsyncMock(return_value=False)
        remote_drive.last_error = E_WP
        self.server.drives[2] = remote_drive
        self.uart_mock.input_buffer.extend([OP_WRITE, 0x02, 0x00, 0x00, 0x01])
        self.uart_mock.input_buffer.extend([0x00] * 256)
        self.uart_mock.input_buffer.extend([0x00, 0x00])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        self.assertEqual(list(self.uart_mock.output_buffer), [E_WP])

    async def test_invalid_unit_error(self):
        self.uart_mock.input_buffer.extend([OP_READ, 0x03, 0x00, 0x00, 0x01])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        self.assertEqual(list(self.uart_mock.output_buffer), [E_UNIT])

    async def test_checksum_error(self):
        vd = drivewire.VirtualDrive(self.test_dsk)
        self.server.drives[0] = vd
        self.uart_mock.input_buffer.extend([OP_WRITE, 0x00, 0x00, 0x00, 0x01])
        self.uart_mock.input_buffer.extend([0xA5] * 256)
        self.uart_mock.input_buffer.extend([0xFF, 0xFF]) # Bad
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        self.assertEqual(list(self.uart_mock.output_buffer), [E_CRC])

    async def test_named_mount(self):
        filename = "test_mount.dsk"
        self.uart_mock.input_buffer.extend([OP_NAMEOBJ_MOUNT, len(filename)])
        self.uart_mock.input_buffer.extend(filename.encode('ascii'))
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        assigned_drive = self.uart_mock.output_buffer[0]
        self.assertIn(assigned_drive, range(4))
        self.assertIsNotNone(self.server.drives[assigned_drive])
        self.assertEqual(self.server.drives[assigned_drive].filename, filename)

    async def test_vserial_init_client(self):
        """OP_SERINIT reads 1 byte (channel), then looks up serial_map config.
        If a mapping exists, it opens a TCP connection."""
        # Configure serial_map so channel 1 maps to a host
        from config import shared_config
        shared_config.config["serial_map"] = {
            "1": {"host": "127.0.0.1", "port": 9999, "mode": "client"}
        }
        self.uart_mock.input_buffer.extend([OP_SERINIT, 0x01])
        mock_reader = AsyncMock()
        # Return empty bytes to signal connection closed, preventing infinite loop
        mock_reader.read = AsyncMock(return_value=b'')
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()
        with patch('drivewire.asyncio.open_connection', new_callable=AsyncMock, return_value=(mock_reader, mock_writer)):
            server_task = asyncio.create_task(self.server.run())
            await asyncio.sleep(0.1)
            await self.server.stop()
            await server_task
            # Verify connection was established
            self.assertIn(1, self.server.tcp_connections)

    async def test_vserial_term(self):
        """OP_SERTERM reads 1 byte (channel) and calls close_tcp.
        No UART response is sent - this is a uni-directional opcode."""
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        self.server.tcp_connections[2] = (MagicMock(), mock_writer, mock_task)
        self.uart_mock.input_buffer.extend([OP_SERTERM, 0x02])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        # Connection should be removed
        self.assertNotIn(2, self.server.tcp_connections)
        mock_writer.close.assert_called()

    async def test_vserial_write(self):
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        self.server.tcp_connections[1] = (MagicMock(), mock_writer, MagicMock())
        self.uart_mock.input_buffer.extend([OP_SERWRITE, 0x01, 0x42])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        mock_writer.write.assert_called_with(bytes([0x42]))

    async def test_vserial_read(self):
        """OP_SERREAD is a polling opcode with no request bytes.
        For a single-byte buffer: response is [channel+1, data_byte].
        For multi-byte buffer: response is [channel+17, count]."""
        # Single byte mode: put only 1 byte in channel 1
        self.server.channels[1].extend([0xDE])
        self.uart_mock.input_buffer.extend([OP_SERREAD])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        # Channel 1, single byte: byte1 = 1+1 = 2, byte2 = 0xDE
        self.assertEqual(list(self.uart_mock.output_buffer), [0x02, 0xDE])

    async def test_printer_opcode(self):
        """OP_PRINT accumulates bytes in print_buffer.
        OP_PRINTFLUSH prints to stdout and clears the buffer."""
        self.uart_mock.input_buffer.extend([OP_PRINT, 0x48])  # 'H'
        self.uart_mock.input_buffer.extend([OP_PRINT, 0x69])  # 'i'
        self.uart_mock.input_buffer.extend([OP_PRINTFLUSH])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        # After flush, print_buffer should be cleared
        self.assertEqual(len(self.server.print_buffer), 0)
        # The output goes to stdout (print()), not to log_buffer.
        # Verify the flush happened by confirming the buffer was reset.

    async def test_named_create(self):
        """OP_NAMEOBJ_CREATE uses the same handler as MOUNT.
        It opens an existing .dsk file, it does not create new files.
        Test that an existing file gets mounted correctly."""
        filename = "test_mount.dsk"  # Already created in asyncSetUp
        self.uart_mock.input_buffer.extend([OP_NAMEOBJ_CREATE, len(filename)])
        self.uart_mock.input_buffer.extend(filename.encode('ascii'))
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.1)
        await self.server.stop()
        await server_task
        assigned_drive = self.uart_mock.output_buffer[0]
        self.assertIn(assigned_drive, range(NUM_DRIVES))
        self.assertIsNotNone(self.server.drives[assigned_drive])

    async def test_time_sync(self):
        self.uart_mock.input_buffer.extend([OP_TIME])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        output = list(self.uart_mock.output_buffer)
        self.assertEqual(output[0], 126) # 2026

if __name__ == '__main__':
    unittest.main()

