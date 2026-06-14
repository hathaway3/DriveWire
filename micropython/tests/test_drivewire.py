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
    OP_SERREADM, OP_SERWRITEM, OP_FASTWRITE, OP_SERSETSTAT, OP_INIT, OP_TERM, OP_NOP,
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

    async def test_legacy_nops(self):
        self.uart_mock.input_buffer.extend([OP_NOP, OP_INIT, OP_TERM, OP_TIME])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        # Verify NOPs were ignored and OP_TIME was still processed correctly maintaining framing
        output = list(self.uart_mock.output_buffer)
        self.assertEqual(output[0], 126)

    async def test_bulk_serial_read_write(self):
        # Initialise TCP connection mock for channel 1
        reader_mock = AsyncMock()
        writer_mock = MagicMock()
        self.server.tcp_connections[1] = (reader_mock, writer_mock, MagicMock())

        # Test OP_SERWRITEM (bulk write to TCP)
        self.uart_mock.input_buffer.extend([OP_SERWRITEM, 1, 5, 0x48, 0x65, 0x6C, 0x6C, 0x6F])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        writer_mock.write.assert_called_with(b'Hello')

        # Test OP_SERREADM (bulk read from channel buffer)
        self.server.channels[2].extend(b'World!')
        self.uart_mock.input_buffer.extend([OP_SERREADM, 2, 6])
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task

        # Output buffer should contain "World!"
        self.assertEqual(bytes(self.uart_mock.output_buffer), b'World!')

    async def test_fastwrite(self):
        # Initialise TCP connection mock for channel 3
        reader_mock = AsyncMock()
        writer_mock = MagicMock()
        self.server.tcp_connections[3] = (reader_mock, writer_mock, MagicMock())

        # OP_FASTWRITE for channel 3 (0x83)
        self.uart_mock.input_buffer.extend([OP_FASTWRITE + 3, 0x41])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task

        # Verify single byte b'A' was written to TCP socket
        writer_mock.write.assert_called_with(b'\x41')

    async def test_channel_lifecycle(self):
        self.uart_mock.input_buffer.extend([OP_SERINIT, 4, OP_SERTERM, 4, OP_SERSETSTAT, 5, 0x29])
        server_task = asyncio.create_task(self.server.run())
        await asyncio.sleep(0.05)
        await self.server.stop()
        await server_task
        # Verify no crash, and channel buffers cleared
        self.assertEqual(len(self.server.channels[4]), 0)
        self.assertEqual(len(self.server.channels[5]), 0)

    async def test_swap_drive_cache_inheritance(self):
        # Prepare old drive with caches
        vd1 = drivewire.VirtualDrive(self.test_dsk)
        vd1.read_cache[10] = bytearray([1] * 256)
        vd1.directory_cache[20] = bytes([2] * 256)
        vd1.dir_lsns.add(20)
        self.server.drives[0] = vd1

        # Swap to new drive with same filename
        vd2 = drivewire.VirtualDrive(self.test_dsk)
        await self.server.swap_drive(0, vd2)

        # Verify caches inherited
        self.assertEqual(vd2.read_cache[10], bytearray([1] * 256))
        self.assertEqual(vd2.directory_cache[20], bytes([2] * 256))
        self.assertIn(20, vd2.dir_lsns)

        # Clean up
        await vd2.close()

    async def test_remote_drive_url_resolution(self):
        remote_url = "http://192.168.1.100:6809/disk/NOS9_6309_L2_DEV_coco3_dw.dsk"
        rd = drivewire.RemoteDrive(remote_url)

        mock_sock = MagicMock()
        mock_sock.recv.return_value = b''  # End of stream

        with patch('resilience.open_remote_stream', return_value=mock_sock) as mock_open:
            await rd.read_sector(612)
            mock_open.assert_called()
            called_url = mock_open.call_args[0][0]
            self.assertEqual(called_url, "http://192.168.1.100:6809/sectors/NOS9_6309_L2_DEV_coco3_dw.dsk/612?count=8")

    async def test_remote_drive_empty_response_reports_read_error(self):
        # When the socket opens but the server returns no usable data, read_sector
        # must surface a real read error (E$Read) and count it — not leave
        # last_error at 0, which the protocol layer maps to E$Unit.
        remote_url = "http://192.168.1.100:6809/disk/NOS9_6309_L2_DEV_coco3_dw.dsk"
        rd = drivewire.RemoteDrive(remote_url)

        mock_sock = MagicMock()
        mock_sock.recv.return_value = b''  # End of stream: no bytes delivered

        with patch('resilience.open_remote_stream', return_value=mock_sock):
            result = await rd.read_sector(612)

        self.assertIsNone(result)
        self.assertEqual(rd.last_error, drivewire.E_READ)
        self.assertGreaterEqual(rd.stats['errors'], 1)

    async def test_remote_drive_recv_reassembles_sectors_across_chunks(self):
        # Regression guard for defect #2: the body is read with recv(), which
        # returns arbitrary-length chunks that do not align to 256-byte sector
        # boundaries. read_sector must reassemble them into correct sectors.
        remote_url = "http://192.168.1.100:6809/disk/test.dsk"
        rd = drivewire.RemoteDrive(remote_url)

        # 8 sectors (count=8), each filled with a distinct byte value.
        payload = b''.join(bytes([(i + 10) & 0xFF]) * 256 for i in range(8))
        # recv delivers it in 100-byte slices that straddle sector boundaries.
        sock = _ChunkedSocket(payload, max_chunk=100)

        with patch('resilience.open_remote_stream', return_value=sock):
            result = await rd.read_sector(0)

        # LSN 0 is treated as a directory sector and returned from directory_cache.
        self.assertEqual(result, bytes([10]) * 256)
        # Remaining sectors of the fetch land in the read cache, intact.
        self.assertEqual(rd.read_cache[1], bytearray([11] * 256))
        self.assertEqual(rd.read_cache[7], bytearray([17] * 256))
        self.assertEqual(rd.last_error, 0)
        self.assertTrue(sock.closed)

    async def test_virtual_drive_read_hit_miss_counters(self):
        # Defect #1: the stats screen reads read_hits/read_misses. A physical
        # read of a data sector is a miss; the cached re-read is a hit.
        vd = drivewire.VirtualDrive(self.test_dsk)
        self.assertIn('read_hits', vd.stats)
        self.assertIn('read_misses', vd.stats)

        # LSN 5 is a plain data sector (not LSN 0 / not a directory).
        await vd.read_sector(5)
        self.assertEqual(vd.stats['read_misses'], 1)
        self.assertEqual(vd.stats['read_hits'], 0)

        await vd.read_sector(5)  # served from read_cache
        self.assertEqual(vd.stats['read_misses'], 1)
        self.assertEqual(vd.stats['read_hits'], 1)
        await vd.close()

    async def test_reload_config_preserves_dirty_and_flushes_removed(self):
        # Defect #5: reloading config must not silently drop unflushed writes
        # nor leak the open file handle of a drive being replaced/removed.
        server = self.server
        # init_drives is mocked out in asyncSetUp; exercise the real method.
        real_init = drivewire.DriveWireServer.init_drives
        server.config.config['drives'] = [self.test_dsk, None, None, None]
        await real_init(server)
        drive = server.drives[0]

        # Stage an unflushed write.
        await drive.write_sector(5, bytearray([0xAB] * 256))
        self.assertIn(5, drive.dirty_sectors)

        # Reload with identical config: same live drive, dirty buffers intact.
        await real_init(server)
        self.assertIs(server.drives[0], drive)
        self.assertIn(5, drive.dirty_sectors)

        # Remove the mount: the drive must be flushed to disk, then dropped.
        server.config.config['drives'] = [None, None, None, None]
        await real_init(server)
        self.assertIsNone(server.drives[0])
        with open(self.test_dsk, 'rb') as f:
            f.seek(5 * 256)
            self.assertEqual(f.read(256), bytes([0xAB] * 256))

    async def test_first_opcode_does_not_raise_unbound_consecutive(self):
        # Defect #7: with UART data ready on the very first loop iteration the
        # idle branch (which seeded consecutive_opcodes) is skipped. Pre-fix the
        # trailing `consecutive_opcodes += 1` raised UnboundLocalError, logged a
        # spurious "Protocol error" and stalled the loop for 1s.
        vd = drivewire.VirtualDrive(self.test_dsk)
        self.server.drives[0] = vd
        self.uart_mock.input_buffer.extend([OP_READ, 0x00, 0x00, 0x00, 0x01])
        with patch('drivewire.resilience.log') as mock_log:
            server_task = asyncio.create_task(self.server.run())
            await asyncio.sleep(0.05)
            await self.server.stop()
            await server_task
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list if c.args)
        self.assertNotIn("Protocol error", logged)

    async def test_serreadm_out_of_range_channel_does_not_crash(self):
        # Defect #8: OP_SERREADM indexed self.channels[chan] with an unchecked
        # client-supplied channel (0-255 vs NUM_CHANNELS=32), raising IndexError
        # caught as a "Protocol error" that stalled the loop.
        self.uart_mock.input_buffer.extend([OP_SERREADM, 200, 1])
        with patch('drivewire.resilience.log') as mock_log:
            server_task = asyncio.create_task(self.server.run())
            await asyncio.sleep(0.05)
            await self.server.stop()
            await server_task
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list if c.args)
        self.assertNotIn("Protocol error", logged)

    async def test_read_only_drive_rejects_writes_with_write_protect(self):
        # Defect #6: a drive opened read-only must report E_WP, not buffer the
        # write into dirty_sectors where flush() fails and the data is lost.
        vd = drivewire.VirtualDrive(self.test_dsk)
        vd.read_only = True
        ok = await vd.write_sector(5, bytearray([0xCD] * 256))
        self.assertFalse(ok)
        self.assertEqual(vd.last_error, drivewire.E_WP)
        self.assertNotIn(5, vd.dirty_sectors)
        await vd.close()


class _ChunkedSocket:
    """Minimal socket stand-in whose recv() honors the contract recv(n) <= n,
    returning data in small straddling chunks to exercise sector reassembly."""
    def __init__(self, payload, max_chunk=100):
        self._buf = bytes(payload)
        self._pos = 0
        self._max = max_chunk
        self.closed = False

    def recv(self, n):
        if self._pos >= len(self._buf):
            return b''
        take = min(n, self._max, len(self._buf) - self._pos)
        chunk = self._buf[self._pos:self._pos + take]
        self._pos += take
        return chunk

    def close(self):
        self.closed = True


if __name__ == '__main__':
    unittest.main()
