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

    def readinto(self, buf):
        n = min(len(buf), len(self.input_buffer))
        if n == 0:
            return 0
        buf[:n] = self.input_buffer[:n]
        self.input_buffer = self.input_buffer[n:]
        return n

    def any(self):
        return len(self.input_buffer) > 0
    
    def deinit(self):
        pass

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
            'utime': MagicMock()
        })
        cls.patcher.start()
        
        # Patch time_sync at the drivewire module's reference (imported at module level)
        drivewire.time_sync.get_local_time = MagicMock(return_value=(2026, 3, 28, 1, 51, 0, 5, 87))

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    async def asyncSetUp(self):
        self.uart_mock = MockUART()
        with patch('drivewire.UART', return_value=self.uart_mock):
            self.server = DriveWireServer()
            self.server.uart = self.uart_mock
        self._init_drives_patcher = patch.object(self.server, 'init_drives')
        self._init_drives_patcher.start()
        
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
        self.assertEqual(list(self.uart_mock.output_buffer), [0x00])
        with open(self.test_dsk, 'rb') as f:
            f.seek(5 * 256)
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
        self.uart_mock.input_buffer.extend([0xFF, 0xFF])
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
        
        # Wait for output or timeout
        for _ in range(20):
            if len(self.uart_mock.output_buffer) > 0: break
            await asyncio.sleep(0.01)
            
        await self.server.stop()
        await server_task
        
        self.assertGreater(len(self.uart_mock.output_buffer), 0)
        assigned_drive = self.uart_mock.output_buffer[0]
        self.assertIn(assigned_drive, range(4))
        self.assertIsNotNone(self.server.drives[assigned_drive])
        self.assertEqual(self.server.drives[assigned_drive].filename, filename)

    async def test_printer_opcode(self):
        self.uart_mock.input_buffer.extend([OP_PRINT, 0x48, OP_PRINT, 0x69, OP_PRINTFLUSH])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        self.assertEqual(len(self.server.print_buffer), 0)

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
