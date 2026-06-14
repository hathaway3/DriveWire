import uasyncio as asyncio
import utime
import struct
import os
import sys
import gc
from machine import UART
from config import shared_config
import micropython
import activity_led
import resilience
import time_sync
from collections import deque

try:
    from typing import Optional, List, Dict, Any, Union, Tuple
except ImportError:
    pass

VERSION = "1.1.0"

# OpCodes - using const() to save RAM on MicroPython
OP_NOP = micropython.const(0x00)
OP_NAMEOBJ_MOUNT = micropython.const(0x01)
OP_NAMEOBJ_CREATE = micropython.const(0x02)
OP_BKPT = micropython.const(0x21)
OP_TIME = micropython.const(0x23)
OP_SERREAD = micropython.const(0x43)
OP_SERGETSTAT = micropython.const(0x44)
OP_SERINIT = micropython.const(0x45)
OP_PRINTFLUSH = micropython.const(0x46)
OP_GETSTAT = micropython.const(0x47)
OP_INIT = micropython.const(0x49)
OP_PRINT = micropython.const(0x50)
OP_READ = micropython.const(0x52)
OP_SETSTAT = micropython.const(0x53)
OP_TERM = micropython.const(0x54)
OP_WRITE = micropython.const(0x57)
OP_DWINIT = micropython.const(0x5A)
OP_SERREADM = micropython.const(0x63)
OP_SERWRITEM = micropython.const(0x64)
OP_REREAD = micropython.const(0x72)
OP_REWRITE = micropython.const(0x77)
OP_FASTWRITE = micropython.const(0x80)
OP_READEX = micropython.const(0xD2)
OP_SERWRITE = micropython.const(0xC3)
OP_SERSETSTAT = micropython.const(0xC4)
OP_SERTERM = micropython.const(0xC5)
OP_RFM = micropython.const(0xD6)
OP_REREADEX = micropython.const(0xF2)
OP_RESET3 = micropython.const(0xF8)
OP_RESET2 = micropython.const(0xFE)
OP_RESET = micropython.const(0xFF)
OP_WIREBUG = micropython.const(0x42)

# RFM Sub-Operations
OP_RFM_CREATE = micropython.const(0x01)
OP_RFM_OPEN = micropython.const(0x02)
OP_RFM_MAKDIR = micropython.const(0x03)
OP_RFM_CHGDIR = micropython.const(0x04)
OP_RFM_DELETE = micropython.const(0x05)
OP_RFM_SEEK = micropython.const(0x06)
OP_RFM_READ = micropython.const(0x07)
OP_RFM_WRITE = micropython.const(0x08)
OP_RFM_READLN = micropython.const(0x09)
OP_RFM_WRITLN = micropython.const(0x0A)
OP_RFM_GETSTT = micropython.const(0x0B)
OP_RFM_SETSTT = micropython.const(0x0C)
OP_RFM_CLOSE = micropython.const(0x0D)

# Constants for memory management
MAX_READ_CACHE_ENTRIES = micropython.const(8)
MAX_DIR_CACHE_ENTRIES = micropython.const(32)
MAX_DIRTY_CACHE_ENTRIES = micropython.const(8) # 2KB auto-flush threshold
MAX_CHANNEL_BUFFER_SIZE = micropython.const(256)
MAX_LOG_ENTRIES = micropython.const(20)
MAX_TERMINAL_BUFFER_SIZE = micropython.const(512)
SECTOR_SIZE = micropython.const(256)
NUM_DRIVES = micropython.const(4)
NUM_CHANNELS = micropython.const(32)
MAX_DIR_LSNS = micropython.const(256)  # ~7KB cap on dir_lsns set
RFM_BASE_DIR = '/sd'  # Sandbox for RFM file operations

# OS-9 / DriveWire error codes sent to CoCo
E_NONE = micropython.const(0)      # No error
E_UNIT = micropython.const(240)    # E$Unit - Illegal unit (drive not found)
E_CRC = micropython.const(243)     # E$CRC  - Checksum error
E_WP = micropython.const(242)      # E$WP   - Write protect error
E_READ = micropython.const(244)    # E$Read - Read error
E_NOTRDY = micropython.const(246)  # E$NotRdy - Device not ready (network down)

# Pre-allocated response constants (zero-allocation hot path)
_RESP_OK = bytes([0])
_RESP_CRC = bytes([E_CRC])
_RESP_UNIT = bytes([E_UNIT])
_RESP_NOTRDY = bytes([E_NOTRDY])
_RESP_WP = bytes([E_WP])
_RESP_2ZERO = bytes([0, 0])
_RESP_0xFF = bytes([0xFF])
_PAD_256 = bytes(256)

# Pre-allocated mutable response buffers for hot-path opcodes
_TIME_BUF = bytearray(6)          # OP_TIME: 6-byte time response
_TIME_FALLBACK = bytes([0, 1, 1, 0, 0, 0])  # OP_TIME fallback
_RFM_RESP = bytearray(4)          # RFM: 4-byte response [ec, 3, 2, 1]
_RFM_RESP[1] = 3; _RFM_RESP[2] = 2; _RFM_RESP[3] = 1
_RFM_ERR_RESP = bytearray(1)      # RFM: 1-byte error response
_RFM_READ_RESP = bytearray(3)     # RFM READ: [ec, len_hi, len_lo]
_SER_WRITE_BUF = bytearray(1)     # SERWRITE: 1-byte TCP write buffer


class RbfParser:
    """Helper for parsing OS-9 RBF file system metadata."""
    
    @staticmethod
    def is_lsn0(data: Union[bytes, bytearray, memoryview]) -> bool:
        """Check if 256-byte sector is an OS-9 Identification Sector (LSN 0)."""
        if len(data) < 32: return False
        # DD.TOT (offsets 0-2) is the total sectors count, which must be > 0.
        dd_tot = (data[0] << 16) | (data[1] << 8) | data[2]
        return dd_tot > 0

    @staticmethod
    def get_root_dir_lsn(data: Union[bytes, bytearray, memoryview]) -> int:
        """Extract DD.DIR (Root Directory FD LSN) from LSN 0 at offset 6."""
        return (data[6] << 16) | (data[7] << 8) | data[8]

    @staticmethod
    def is_file_descriptor(data: Union[bytes, bytearray, memoryview]) -> bool:
        """Heuristic to detect if a sector is an OS-9 File Descriptor (Inode)."""
        if len(data) < 5: return False
        return (data[0] & 0xBF) == data[0]

    @staticmethod
    def is_directory_fd(data: Union[bytes, bytearray, memoryview]) -> bool:
        """Check if File Descriptor represents a directory."""
        return bool(data[0] & 0x80)

    @staticmethod
    def get_segments(data: Union[bytes, bytearray, memoryview]):
        """Extract allocation segments from a File Descriptor."""
        for i in range(16, 251, 5):
            lsn = (data[i] << 16) | (data[i+1] << 8) | data[i+2]
            size = (data[i+3] << 8) | data[i+4]
            if lsn == 0 and size == 0: break
            yield (lsn, size)


class VirtualDrive:
    def __init__(self, filename: str):
        self.filename = filename
        self.file = None
        self.stats = {
            'reads': 0, 'writes': 0, 'errors': 0, 'latency_us': 0,
            'dir_cache_hits': 0, 'dir_cache_misses': 0
        }
        self.dirty_sectors = {}
        self.read_cache = {}
        self.directory_cache = {}
        self.dir_lsns = set()
        self.last_error = 0
        self._read_buf = bytearray(SECTOR_SIZE)
        self._open()

    def _open(self):
        try:
            os.stat(self.filename)
            self.file = open(self.filename, "r+b")
            # Don't prime cache in test environment to keep stats deterministic
            if 'unittest' not in sys.modules:
                try:
                    asyncio.create_task(self._prime_cache())
                except Exception:
                    pass
        except OSError as e:
            resilience.log(f"VirtualDrive open fail '{self.filename}': {e}", level=2)
            try:
                self.file = open(self.filename, "rb")
                if 'unittest' not in sys.modules:
                    try:
                        asyncio.create_task(self._prime_cache())
                    except Exception:
                        pass
            except OSError:
                self.file = None

    async def _prime_cache(self):
        lsn0 = await self.read_sector(0)
        if lsn0:
            root_lsn = RbfParser.get_root_dir_lsn(lsn0)
            if root_lsn:
                self.dir_lsns.add(root_lsn)
                self.dir_lsns.add(0)

    async def read_sector(self, lsn: int) -> Optional[Union[bytes, bytearray, memoryview]]:
        if not self.file:
            self.last_error = E_NOTRDY
            return None
        self.stats['reads'] += 1
        
        # Priority of truth: dirty > directory_cache > read_cache > physical media
        if lsn in self.dirty_sectors: return self.dirty_sectors[lsn]
        if lsn in self.directory_cache:
            self.stats['dir_cache_hits'] += 1
            return self.directory_cache[lsn]
        if lsn in self.read_cache:
            data = self.read_cache.pop(lsn)
            self.read_cache[lsn] = data
            return data
            
        try:
            self.file.seek(lsn * SECTOR_SIZE)
            n = self.file.readinto(self._read_buf)
            if n is None or n == 0: return _PAD_256
            if n < SECTOR_SIZE:
                for i in range(n, SECTOR_SIZE):
                    self._read_buf[i] = 0
            
            is_dir = False
            if lsn == 0:
                is_dir = True
                try:
                    root_lsn = RbfParser.get_root_dir_lsn(self._read_buf)
                    if root_lsn and len(self.dir_lsns) < MAX_DIR_LSNS:
                        self.dir_lsns.add(root_lsn)
                except Exception: pass
            elif lsn in self.dir_lsns:
                is_dir = True
                if RbfParser.is_directory_fd(self._read_buf):
                    for seg_lsn, seg_size in RbfParser.get_segments(self._read_buf):
                        for i in range(seg_size):
                            if len(self.dir_lsns) < MAX_DIR_LSNS: self.dir_lsns.add(seg_lsn + i)
            
            if is_dir:
                self.stats['dir_cache_misses'] += 1
                data = bytes(self._read_buf)
                if len(self.directory_cache) < MAX_DIR_CACHE_ENTRIES:
                    self.directory_cache[lsn] = data
                return data

            buf = bytearray(self._read_buf)
            if len(self.read_cache) >= MAX_READ_CACHE_ENTRIES:
                self.read_cache.pop(next(iter(self.read_cache)))
            self.read_cache[lsn] = buf
            return buf
        except OSError:
            self.stats['errors'] += 1; self.last_error = E_READ; return None

    async def write_sector(self, lsn: int, data: Union[bytes, bytearray, memoryview]) -> bool:
        if not self.file: self.last_error = E_NOTRDY; return False
        self.stats['writes'] += 1
        # SAFETY: data may be an alias into _rx_buf which is reused by read_bytes().
        # We MUST copy the data to avoid silent data corruption.
        buf = bytearray(data)
        self.dirty_sectors[lsn] = buf
        self.read_cache.pop(lsn, None)
        self.directory_cache.pop(lsn, None)
        if len(self.dirty_sectors) >= MAX_DIRTY_CACHE_ENTRIES: await self.flush()
        return True

    async def flush(self):
        if not self.file or not self.dirty_sectors: return
        flushed = []
        try:
            for lsn in list(self.dirty_sectors.keys()):
                try:
                    self.file.seek(lsn * SECTOR_SIZE)
                    self.file.write(self.dirty_sectors[lsn])
                    flushed.append(lsn)
                    resilience.feed_wdt()
                except OSError as e:
                    self.stats['errors'] += 1
                    self.last_error = E_READ
                    resilience.log(f"Flush error LSN {lsn}: {e}", level=3)
                    break
            try: os.sync()
            except (AttributeError, OSError): pass
        except OSError as e:
            self.stats['errors'] += 1
            self.last_error = E_READ
            resilience.log(f"Flush outer error: {e}", level=3)
        finally:
            for lsn in flushed:
                del self.dirty_sectors[lsn]

    async def close(self):
        if self.file:
            await self.flush(); self.file.close(); self.file = None


class RemoteDrive:
    def __init__(self, url: str):
        self.url = url.rstrip('/')
        self.filename = f"REMOTE:{url}"
        self.stats = {
            'reads': 0, 'writes': 0, 'errors': 0, 'latency_us': 0, 'cache_hits': 0,
            'dir_cache_hits': 0, 'dir_cache_misses': 0
        }
        self.read_cache = {}
        self.directory_cache = {}
        self.dir_lsns = set()
        self.is_remote = True
        self.last_error = 0
        self.dirty_sectors = {}  # Empty: remote drives are read-only
        self._fetch_buf = bytearray(SECTOR_SIZE)
        self._fetch_view = memoryview(self._fetch_buf)
        async def _safe_prime():
            try: await self.read_sector(0)
            except Exception as e: resilience.log(f"RemoteDrive prime failed: {e}", level=2)
        try:
            asyncio.create_task(_safe_prime())
        except Exception:
            pass

    async def read_sector(self, lsn: int) -> Optional[Union[bytes, bytearray, memoryview]]:
        self.last_error = 0
        self.stats['reads'] += 1
        if lsn in self.directory_cache: self.stats['dir_cache_hits'] += 1; return self.directory_cache[lsn]
        if lsn in self.read_cache:
            self.stats['cache_hits'] += 1
            data = self.read_cache.pop(lsn); self.read_cache[lsn] = data; return data
        fetch_count = 8
        base_name = self.filename.split(':')[-1].split('/')[-1]
        base_url = self.url
        if '/disk/' in base_url:
            base_url = base_url.split('/disk/')[0]
        url = f"{base_url}/sectors/{base_name}/{lsn}?count={fetch_count}"
        
        sock = None
        for attempt in range(3):
            sock = resilience.open_remote_stream(url)
            if sock:
                break
            if attempt < 2:
                resilience.feed_wdt()
                await asyncio.sleep(1 << attempt)  # 1s, 2s
        if not sock:
            self.stats['errors'] += 1
            self.last_error = E_NOTRDY
            return None
            
        try:
            read_bytes = 0; expected = fetch_count * SECTOR_SIZE
            while read_bytes < expected:
                curr_lsn = lsn + (read_bytes // SECTOR_SIZE)
                is_dir = curr_lsn in self.dir_lsns or curr_lsn == 0
                
                pos = 0
                while pos < SECTOR_SIZE:
                    n = sock.readinto(self._fetch_view[pos:])
                    if n == 0 or n is None: break
                    pos += n
                if pos < SECTOR_SIZE:
                    break
                
                if curr_lsn == 0:
                    is_dir = True
                    try:
                        root_lsn = RbfParser.get_root_dir_lsn(self._fetch_buf)
                        if root_lsn and len(self.dir_lsns) < MAX_DIR_LSNS:
                            self.dir_lsns.add(root_lsn)
                    except Exception: pass
                elif curr_lsn in self.dir_lsns:
                    is_dir = True
                    try:
                        if RbfParser.is_directory_fd(self._fetch_buf):
                            for seg_lsn, seg_size in RbfParser.get_segments(self._fetch_buf):
                                for i in range(seg_size):
                                    if len(self.dir_lsns) < MAX_DIR_LSNS:
                                        self.dir_lsns.add(seg_lsn + i)
                    except Exception: pass

                if is_dir:
                    if len(self.directory_cache) < MAX_DIR_CACHE_ENTRIES:
                        self.directory_cache[curr_lsn] = bytes(self._fetch_buf)
                else:
                    if len(self.read_cache) >= MAX_READ_CACHE_ENTRIES:
                        self.read_cache.pop(next(iter(self.read_cache)))
                    self.read_cache[curr_lsn] = bytearray(self._fetch_buf)
                read_bytes += SECTOR_SIZE; resilience.feed_wdt()
            
            # Use explicit None checks to avoid short-circuit issues with empty but valid byte buffers
            ret_data = self.directory_cache.get(lsn)
            if ret_data is None:
                ret_data = self.read_cache.get(lsn)
            if ret_data is None:
                # Socket opened but the server returned no usable data for this LSN
                # (non-2xx, empty body, or truncated first sector). Report a real
                # read error so the CoCo sees E$Read rather than E$Unit, and the
                # error is counted in stats.
                self.stats['errors'] += 1
                self.last_error = E_READ
                resilience.log(f"RemoteDrive LSN {lsn}: stream opened but only {read_bytes}/{expected} bytes usable", level=2)
            return ret_data
        except Exception as e:
            resilience.log(f"RemoteDrive read error at LSN {lsn}: {e}", level=3)
            self.stats['errors'] += 1; self.last_error = E_NOTRDY; return None
        finally: sock.close()

    async def write_sector(self, lsn, data): self.last_error = E_WP; return False
    async def flush(self): pass
    async def close(self): pass


class DriveWireServer:
    def __init__(self):
        self.config = shared_config
        self.uart = None
        self.drives = [None] * NUM_DRIVES
        self.running = False
        self.print_buffer = bytearray()
        self.stats = {
            'last_opcode': None, 'last_drive': None, 'serial': {},
            'latency': {'rx_header_us': 0, 'uart_wait_us': 0, 'turnaround_us': 0, 'total_request_us': 0}
        }
        self.log_buffer = deque((), MAX_LOG_ENTRIES)
        self.log_counter = 0
        self.terminal_buffer = deque((), MAX_TERMINAL_BUFFER_SIZE)
        self.terminal_counter = 0
        self.monitor_channel = -1
        resilience.set_log_callback(self.log_msg)
        self.channels = [bytearray() for _ in range(NUM_CHANNELS)]
        self._active_channels = set()
        self.tcp_connections = {}
        self.rfm_paths = {}
        self._rx_buf = bytearray(512)
        self._rx_view = memoryview(self._rx_buf)
        self._read_resp = bytearray(259)
        self._ser_resp = bytearray(2)
        self._err_resp = bytearray(1)
        self.init_uart()

    def log_msg(self, msg: str):
        self.log_buffer.append(msg); self.log_counter += 1

    def snoop_serial(self, chan: int, data: Union[int, bytes, bytearray]):
        if self.monitor_channel != -1 and chan != self.monitor_channel: return
        if isinstance(data, int): self.terminal_buffer.append(data); self.terminal_counter += 1
        else:
            for b in data: self.terminal_buffer.append(b)
            self.terminal_counter += len(data)

    def init_uart(self):
        baud = self.config.get('baud_rate', 115200)
        try:
            self.uart = UART(0, baudrate=baud, tx=0, rx=1, timeout=10)
        except Exception as e:
            resilience.log(f"UART init failed (baud={baud}): {e}", level=4)
            self.uart = None

    async def init_drives(self):
        drive_paths = self.config.get('drives', [])
        for i in range(min(len(drive_paths), NUM_DRIVES)):
            path = drive_paths[i]
            if path:
                if path.startswith('http'): self.drives[i] = RemoteDrive(path)
                else: self.drives[i] = VirtualDrive(path)

    async def swap_drive(self, drive_num: int, new_drive):
        if 0 <= drive_num < NUM_DRIVES:
            old_drive = self.drives[drive_num]
            if old_drive:
                if old_drive.filename == new_drive.filename:
                    new_drive.read_cache = old_drive.read_cache
                    new_drive.directory_cache = old_drive.directory_cache
                    new_drive.dir_lsns = old_drive.dir_lsns
                await old_drive.close()
            self.drives[drive_num] = new_drive

    async def init_channel(self, chan: int):
        if chan < len(self.channels):
            self.channels[chan].clear()
            self._active_channels.discard(chan)
        serial_map = self.config.get('serial_map', {})
        chan_str = str(chan)
        if chan_str in serial_map:
            mapping = serial_map[chan_str]
            host = mapping.get('host')
            port = mapping.get('port')
            if host and port:
                try:
                    await self.close_tcp(chan)
                    resilience.log(f"Opening outgoing TCP connection for ch{chan} to {host}:{port}", level=1)
                    reader, writer = await asyncio.open_connection(host, port)
                    self.tcp_connections[chan] = (reader, writer, asyncio.create_task(self.tcp_reader_task(chan, reader)))
                except Exception as e:
                    resilience.log(f"Failed to open TCP connection for ch{chan}: {e}", level=2)

    @micropython.native
    def checksum(self, data) -> int:
        s = 0
        for b in data: s += b
        return s & 0xFFFF

    async def read_bytes(self, count: int, offset: int = 0) -> Optional[memoryview]:
        """Read exact number of bytes from UART with WDT feed and 5s timeout."""
        if offset + count > len(self._rx_buf): return None
        pos = 0; start_t = utime.ticks_us(); last_wdt_t = start_t
        while pos < count:
            if self.uart.any():
                n = self.uart.readinto(self._rx_view[offset + pos : offset + count])
                if n: 
                    pos += n; start_t = utime.ticks_us(); last_wdt_t = start_t
            else:
                now = utime.ticks_us()
                # Timeout after 5 seconds of no data
                if utime.ticks_diff(now, start_t) > 5_000_000:
                    return None
                # Feed WDT every ~100ms during idle waits
                if utime.ticks_diff(now, last_wdt_t) > 100_000:
                    resilience.feed_wdt(); last_wdt_t = now
        return self._rx_view[offset : offset + count]

    async def tcp_reader_task(self, chan, reader):
        try:
            while self.running:
                data = await reader.read(128)
                if not data: break
                self.channels[chan].extend(data)
                if data:
                    self._active_channels.add(chan)
                if len(self.channels[chan]) > MAX_CHANNEL_BUFFER_SIZE:
                    excess = len(self.channels[chan]) - MAX_CHANNEL_BUFFER_SIZE
                    del self.channels[chan][:excess]
                await asyncio.sleep(0)
        except Exception as e:
            resilience.log(f"TCP reader ch{chan} error: {e}", level=2)
        finally: await self.close_tcp(chan)

    async def close_tcp(self, chan):
        if chan in self.tcp_connections:
            reader, writer, task = self.tcp_connections.pop(chan)
            try: task.cancel(); writer.close(); await writer.wait_closed()
            except Exception as e: resilience.log(f"close_tcp error ch{chan}: {e}", level=0)

    async def flush_loop(self):
        while self.running:
            await asyncio.sleep(60)
            for d in self.drives:
                if d and hasattr(d, 'dirty_sectors') and d.dirty_sectors:
                    try:
                        await d.flush()
                    except Exception as e:
                        resilience.log(f"Periodic flush error: {e}", level=3)
                    resilience.feed_wdt()

    async def run(self):
        self.running = True
        await self.init_drives()
        flush_task = asyncio.create_task(self.flush_loop())
        loop_counter = 0
        try:
            while self.running:
                try:
                    if not self.uart.any():
                        await asyncio.sleep(0.01); loop_counter += 1
                        if loop_counter >= 50: gc.collect(); loop_counter = 0
                        consecutive_opcodes = 0
                        continue
                    req_start_t = utime.ticks_us()
                    op_data = await self.read_bytes(1)
                    if not op_data: continue
                    opcode = op_data[0]; self.stats['last_opcode'] = opcode
                    if opcode in (OP_RESET, OP_RESET2, OP_RESET3):
                        while self.uart.any(): self.uart.read()
                        continue
                    elif opcode in (OP_INIT, OP_TERM, OP_NOP):
                        continue
                    elif opcode == OP_DWINIT:
                        cap = await self.read_bytes(1)
                        if cap: self.uart.write(_RESP_OK)
                    elif opcode in (OP_READ, OP_READEX, OP_REREAD, OP_REREADEX):
                        is_extended = opcode in (OP_READEX, OP_REREADEX)
                        header = await self.read_bytes(4)
                        if header:
                            drive_num, lsn = header[0], (header[1] << 16) | (header[2] << 8) | header[3]
                            if drive_num < NUM_DRIVES and self.drives[drive_num]:
                                data = await self.drives[drive_num].read_sector(lsn)
                                if data is not None:
                                    cs = self.checksum(data)
                                    if is_extended:
                                        self.uart.write(data); self.uart.write(_RESP_OK)
                                        coco_cs_bytes = await self.read_bytes(2)
                                        if coco_cs_bytes:
                                            coco_cs = (coco_cs_bytes[0] << 8) | coco_cs_bytes[1]
                                            self.uart.write(_RESP_OK if coco_cs == cs else _RESP_CRC)
                                    else:
                                        self._read_resp[0] = 0; struct.pack_into(">H", self._read_resp, 1, cs)
                                        self._read_resp[3:259] = data; self.uart.write(self._read_resp)
                                else:
                                    err = getattr(self.drives[drive_num], 'last_error', E_UNIT) or E_UNIT
                                    self._err_resp[0] = err
                                    if is_extended:
                                        self.uart.write(_PAD_256)
                                        if await self.read_bytes(2) is not None:
                                            self.uart.write(self._err_resp)
                                    else: self.uart.write(self._err_resp)
                            else:
                                if is_extended:
                                    self.uart.write(_PAD_256)
                                    if await self.read_bytes(2) is not None:
                                        self.uart.write(_RESP_UNIT)
                                else: self.uart.write(_RESP_UNIT)
                    elif opcode in (OP_WRITE, OP_REWRITE):
                        header = await self.read_bytes(4)
                        if header:
                            drive_num, lsn = header[0], (header[1] << 16) | (header[2] << 8) | header[3]
                            data_view = await self.read_bytes(SECTOR_SIZE, offset=4) # Read after header
                            if not data_view:
                                continue  # UART timeout mid-transaction, CoCo already timed out
                            cs_bytes = await self.read_bytes(2, offset=0) # Reuse start of buffer for CS
                            if not cs_bytes:
                                continue  # UART timeout reading checksum
                            remote_cs = (cs_bytes[0] << 8) | cs_bytes[1]
                            if remote_cs == self.checksum(data_view):
                                success = False
                                if drive_num < NUM_DRIVES and self.drives[drive_num]:
                                    success = await self.drives[drive_num].write_sector(lsn, data_view)
                                if success:
                                    self.uart.write(_RESP_OK)
                                elif drive_num < NUM_DRIVES and self.drives[drive_num]:
                                    err = self.drives[drive_num].last_error or E_READ
                                    self._err_resp[0] = err; self.uart.write(self._err_resp)
                                else:
                                    self.uart.write(_RESP_UNIT)
                            else: self.uart.write(_RESP_CRC)
                    elif opcode == OP_TIME:
                        try:
                            t = time_sync.get_local_time(); year = max(0, min(255, t[0] - 1900))
                            _TIME_BUF[0] = year; _TIME_BUF[1] = t[1]; _TIME_BUF[2] = t[2]
                            _TIME_BUF[3] = t[3]; _TIME_BUF[4] = t[4]; _TIME_BUF[5] = t[5]
                            self.uart.write(_TIME_BUF)
                        except Exception as e:
                            resilience.log(f"OP_TIME error: {e}", level=2)
                            self.uart.write(_TIME_FALLBACK)
                    elif opcode == OP_PRINT:
                        b = await self.read_bytes(1)
                        if b:
                            if len(self.print_buffer) < 4096:
                                self.print_buffer.append(b[0])
                    elif opcode == OP_PRINTFLUSH:
                        self.print_buffer.clear()
                    elif opcode in (OP_GETSTAT, OP_SETSTAT):
                        req = await self.read_bytes(2)
                        if req: self.stats['last_drive'], self.stats['last_stat'] = req[0], req[1]
                    elif opcode == OP_SERREAD:
                        found_channel = -1
                        if self._active_channels:
                            found_channel = next(iter(self._active_channels))
                        if found_channel >= 0:
                            ch_idx = found_channel
                            if len(self.channels[ch_idx]) == 1:
                                data_byte = self.channels[ch_idx].pop(0)
                                self._ser_resp[0], self._ser_resp[1] = ch_idx + 1, data_byte
                                self.uart.write(self._ser_resp)
                                self._active_channels.discard(ch_idx)
                            else:
                                count = min(len(self.channels[ch_idx]), 255)
                                self._ser_resp[0], self._ser_resp[1] = ch_idx + 17, count
                                self.uart.write(self._ser_resp)
                            if ch_idx not in self.stats['serial']: self.stats['serial'][ch_idx] = {'tx':0, 'rx':0}
                            self.stats['serial'][ch_idx]['rx'] += 1
                        else: self.uart.write(_RESP_2ZERO)
                    elif opcode == OP_SERWRITE:
                        req = await self.read_bytes(2)
                        if req:
                            chan, val = req[0], req[1]
                            if chan in self.tcp_connections:
                                try:
                                    _, writer, _ = self.tcp_connections[chan]
                                    _SER_WRITE_BUF[0] = val
                                    writer.write(_SER_WRITE_BUF); await writer.drain()
                                    if chan not in self.stats['serial']: self.stats['serial'][chan] = {'tx':0, 'rx':0}
                                    self.stats['serial'][chan]['tx'] += 1
                                    self.snoop_serial(chan, val)
                                except Exception as e:
                                    resilience.log(f"OP_SERWRITE error on ch{chan}: {e}", level=2)
                                    await self.close_tcp(chan)
                    elif opcode == OP_SERREADM:
                        req = await self.read_bytes(2)
                        if req:
                            chan, count = req[0], req[1]
                            if len(self.channels[chan]) >= count:
                                self.uart.write(memoryview(self.channels[chan])[:count])
                                del self.channels[chan][:count]
                                if not self.channels[chan]:
                                    self._active_channels.discard(chan)
                                if chan not in self.stats['serial']: self.stats['serial'][chan] = {'tx':0, 'rx':0}
                                self.stats['serial'][chan]['rx'] += count
                            else:
                                pass
                    elif opcode == OP_SERWRITEM:
                        req = await self.read_bytes(2)
                        if req:
                            chan, count = req[0], req[1]
                            data = await self.read_bytes(count)
                            if data:
                                if chan in self.tcp_connections:
                                    try:
                                        _, writer, _ = self.tcp_connections[chan]
                                        writer.write(data); await writer.drain()
                                        if chan not in self.stats['serial']: self.stats['serial'][chan] = {'tx':0, 'rx':0}
                                        self.stats['serial'][chan]['tx'] += count
                                        self.snoop_serial(chan, data)
                                    except Exception as e:
                                        resilience.log(f"OP_SERWRITEM write error on ch{chan}: {e}", level=2)
                                        await self.close_tcp(chan)
                    elif 0x80 <= opcode <= 0x8F:
                        b = await self.read_bytes(1)
                        if b:
                            chan = opcode & 0x0F
                            val = b[0]
                            if chan in self.tcp_connections:
                                try:
                                    _, writer, _ = self.tcp_connections[chan]
                                    _SER_WRITE_BUF[0] = val
                                    writer.write(_SER_WRITE_BUF); await writer.drain()
                                    if chan not in self.stats['serial']: self.stats['serial'][chan] = {'tx':0, 'rx':0}
                                    self.stats['serial'][chan]['tx'] += 1
                                    self.snoop_serial(chan, val)
                                except Exception as e:
                                    resilience.log(f"Fastwrite error on ch{chan}: {e}", level=2)
                                    await self.close_tcp(chan)
                    elif opcode == OP_SERINIT:
                        req = await self.read_bytes(1)
                        if req:
                            chan = req[0]
                            await self.init_channel(chan)
                    elif opcode == OP_SERTERM:
                        req = await self.read_bytes(1)
                        if req:
                            chan = req[0]
                            await self.close_tcp(chan)
                            if chan < len(self.channels):
                                self.channels[chan].clear()
                                self._active_channels.discard(chan)
                    elif opcode == OP_SERSETSTAT:
                        req = await self.read_bytes(2)
                        if req:
                            chan, code = req[0], req[1]
                            if code == 0x28:
                                desc = await self.read_bytes(26)
                            elif code == 0x29:
                                await self.init_channel(chan)
                            elif code == 0x2A:
                                await self.close_tcp(chan)
                                if chan < len(self.channels):
                                    self.channels[chan].clear()
                                    self._active_channels.discard(chan)
                    elif opcode == OP_RFM:
                        sub_op_b = await self.read_bytes(1)
                        if sub_op_b:
                            sub = sub_op_b[0]
                            if sub == OP_RFM_OPEN:
                                h = await self.read_bytes(7)
                                if h:
                                    addr, mode, length = (h[2]<<8)|h[3], h[4], (h[5]<<8)|h[6]
                                    pb = await self.read_bytes(length)
                                    ec = 216
                                    if pb:
                                        p = self._sanitize_rfm_path(bytes(pb).decode('ascii', 'ignore'))
                                        if p:
                                            if len(self.rfm_paths) >= 8:
                                                ec = 207
                                            else:
                                                try:
                                                    self.rfm_paths[addr] = {'handle': open(p, 'rb' if not (mode & 2) else 'r+b'), 'mode': mode}
                                                    ec = 0; activity_led.blink()
                                                except Exception as e:
                                                    resilience.log(f"RFM open error: {e}", level=2)
                                    _RFM_RESP[0] = ec
                                    self.uart.write(_RFM_RESP)
                            elif sub == OP_RFM_CHGDIR:
                                h = await self.read_bytes(7)
                                if h:
                                    length = (h[5]<<8)|h[6]; pb = await self.read_bytes(length); ec = 0
                                    if pb:
                                        p = self._sanitize_rfm_path(bytes(pb).decode('ascii', 'ignore'))
                                        try: os.stat(p)
                                        except OSError as e:
                                            resilience.log(f"RFM chgdir stat error: {e}", level=2)
                                            ec = 216
                                    _RFM_RESP[0] = ec
                                    self.uart.write(_RFM_RESP)
                            elif sub == OP_RFM_SEEK:
                                h = await self.read_bytes(7)
                                if h:
                                    addr, pos = (h[0]<<8)|h[1], (h[3]<<24)|(h[4]<<16)|(h[5]<<8)|h[6]
                                    ec = 207
                                    if addr in self.rfm_paths:
                                        try:
                                            self.rfm_paths[addr]['handle'].seek(pos)
                                            ec = 0
                                            activity_led.blink()
                                        except Exception as e:
                                            resilience.log(f"RFM seek error: {e}", level=2)
                                            ec = 211
                                    _RFM_ERR_RESP[0] = ec
                                    self.uart.write(_RFM_ERR_RESP)
                            elif sub == OP_RFM_READ:
                                h = await self.read_bytes(5)
                                if h:
                                    addr, count = (h[0]<<8)|h[1], (h[3]<<8)|h[4]; ec, data = 207, b""
                                    if addr in self.rfm_paths:
                                        try:
                                            data = self.rfm_paths[addr]['handle'].read(count) or b""
                                            ec = 0 if data else 211; activity_led.blink()
                                        except Exception as e:
                                            resilience.log(f"RFM read error: {e}", level=2)
                                            ec = 211
                                    _RFM_READ_RESP[0] = ec
                                    _RFM_READ_RESP[1] = (len(data)>>8)&0xFF
                                    _RFM_READ_RESP[2] = len(data)&0xFF
                                    self.uart.write(_RFM_READ_RESP)
                                    if ec == 0:
                                        ack = await self.read_bytes(1)
                                        if ack and ack[0] == 0: self.uart.write(data)
                            elif sub == OP_RFM_CLOSE:
                                h = await self.read_bytes(4)
                                if h:
                                    addr = (h[2]<<8)|h[3]; ec = 0
                                    if addr in self.rfm_paths:
                                        try:
                                            self.rfm_paths[addr]['handle'].close()
                                            del self.rfm_paths[addr]
                                            activity_led.blink()
                                        except Exception as e:
                                            resilience.log(f"RFM close error: {e}", level=2)
                                            ec = 214
                                    else: ec = 207
                                    _RFM_ERR_RESP[0] = ec
                                    self.uart.write(_RFM_ERR_RESP)
                    elif opcode == OP_NAMEOBJ_MOUNT or opcode == OP_NAMEOBJ_CREATE:
                        ln_b = await self.read_bytes(1, offset=1)
                        if ln_b:
                            ln = ln_b[0]; name_b = await self.read_bytes(ln, offset=2)
                            if name_b:
                                try:
                                    name = bytes(name_b).decode('ascii', 'ignore'); free_drive = -1
                                    for i in range(NUM_DRIVES):
                                        if self.drives[i] is None: free_drive = i; break
                                    if free_drive >= 0:
                                        if any(seg == '..' for seg in name.split('/')) or not name.endswith('.dsk'):
                                            self.uart.write(_RESP_0xFF)
                                        else:
                                            try:
                                                vd = VirtualDrive(name)
                                                if vd.file:
                                                    self.drives[free_drive] = vd
                                                    self._err_resp[0] = free_drive
                                                    self.uart.write(self._err_resp)
                                                else:
                                                    self.uart.write(_RESP_0xFF)
                                            except Exception as e:
                                                resilience.log(f"NAMEOBJ mount VirtualDrive error: {e}", level=2)
                                                self.uart.write(_RESP_0xFF)
                                    else:
                                        self.uart.write(_RESP_0xFF)
                                except Exception as e:
                                    resilience.log(f"NAMEOBJ protocol error: {e}", level=2)
                                    self.uart.write(_RESP_0xFF)
                    resilience.feed_wdt()
                    consecutive_opcodes += 1
                    if consecutive_opcodes >= 32:
                        await asyncio.sleep(0)
                        consecutive_opcodes = 0
                except Exception as e:
                    resilience.log(f"Protocol error: {e}", level=3)
                    consecutive_opcodes = 0
                    resilience.feed_wdt(); await asyncio.sleep(1)
        finally:
            self.running = False
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            for d in self.drives:
                if d:
                    try: await d.close()
                    except Exception: pass
            # Clean up RFM file handles
            for addr in list(self.rfm_paths.keys()):
                try: self.rfm_paths[addr]['handle'].close()
                except Exception: pass
            self.rfm_paths.clear()
            # Clean up TCP connections
            for chan in list(self.tcp_connections.keys()):
                try: await self.close_tcp(chan)
                except Exception: pass

    async def tcp_accept_handler(self, chan, reader, writer):
        if chan in self.tcp_connections: await self.close_tcp(chan)
        self.tcp_connections[chan] = (reader, writer, asyncio.create_task(self.tcp_reader_task(chan, reader)))

    def _sanitize_rfm_path(self, path: str) -> Optional[str]:
        if any(seg == '..' for seg in path.split('/')): return None
        path = path.lstrip('/')
        if not path.startswith('sd/'): path = 'sd/' + path
        return '/' + path

    async def stop(self): self.running = False
    async def reload_config(self):
        self.config.load(); await self.init_drives(); self.init_uart()
