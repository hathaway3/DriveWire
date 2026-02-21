import uasyncio as asyncio
import struct
import os
from machine import UART
from config import shared_config
import micropython
import activity_led

# OpCodes - using const() to save RAM on MicroPython
OP_BKPT = micropython.const(0x21)
OP_TIME = micropython.const(0x23)
OP_INIT = micropython.const(0x49)
OP_TERM = micropython.const(0x54)
OP_READ = micropython.const(0x52)
OP_READEX = micropython.const(0x58)
OP_REREAD = micropython.const(0xD2)
OP_REREADEX = micropython.const(0xD8)
OP_WRITE = micropython.const(0x57)
OP_REWRITE = micropython.const(0xD7)
OP_RESET = micropython.const(0xFE)
OP_RESET2 = micropython.const(0xFF)
OP_RESET3 = micropython.const(0xF8)
OP_DWINIT = micropython.const(0x5A)
OP_NAMEOBJ_MOUNT = micropython.const(0x01)
OP_NAMEOBJ_CREATE = micropython.const(0x02)
OP_GETSTAT = micropython.const(0x47)
OP_SETSTAT = micropython.const(0x53)
OP_PRINT = micropython.const(0x50)
OP_PRINTFLUSH = micropython.const(0x46)
OP_WIREBUG = micropython.const(0x42)
OP_SERREAD = micropython.const(0x43)
OP_SERWRITE = micropython.const(0xC3)
OP_SERINIT = micropython.const(0x4E)
OP_SERTERM = micropython.const(0x45)
OP_SERSETSTAT = micropython.const(0xD3)

# Constants for memory management
MAX_READ_CACHE_ENTRIES = micropython.const(8)
MAX_CHANNEL_BUFFER_SIZE = micropython.const(256)
MAX_LOG_ENTRIES = micropython.const(20)
MAX_TERMINAL_BUFFER_SIZE = micropython.const(512)
SECTOR_SIZE = micropython.const(256)
NUM_DRIVES = micropython.const(4)
NUM_CHANNELS = micropython.const(32)
# Let's define the class.

class VirtualDrive:
    """Manages a virtual disk drive with write-back caching for flash wear protection."""
    
    def __init__(self, filename):
        self.filename = filename
        self.file = None
        self.dirty_sectors = {}  # LSN -> data (write cache)
        self.read_cache = {}     # LSN -> data (LRU read cache)
        self.stats = {
            'read_hits': 0,
            'read_misses': 0,
            'write_count': 0
        }
        try:
            self.file = open(filename, "r+b")
        except OSError as e:
            print(f"Failed to open {filename}: {e}")

    def close(self):
        try:
            self.flush()
        except Exception as e:
            print(f"Flush error during close of {self.filename}: {e}")
        finally:
            if self.file:
                try:
                    self.file.close()
                except OSError as e:
                    print(f"Error closing {self.filename}: {e}")
                self.file = None

    def flush(self):
        if not self.file or not self.dirty_sectors: return
        flushed_lsns = []
        activity_led.on()
        try:
            for lsn, data in self.dirty_sectors.items():
                self.file.seek(lsn * 256)
                self.file.write(data)
                flushed_lsns.append(lsn)
            self.file.flush()
            self.dirty_sectors = {}
            print(f"Flushed {self.filename}")
        except OSError as e:
            # Only clear sectors that were successfully written
            for lsn in flushed_lsns:
                self.dirty_sectors.pop(lsn, None)
            print(f"Flush Error ({len(self.dirty_sectors)} sectors remain dirty): {e}")
        finally:
            activity_led.off()

    def read_sector(self, lsn):
        """Read a sector from the virtual drive, checking caches first."""
        # 1. Check write cache (dirty sectors have priority)
        if lsn in self.dirty_sectors:
            self.stats['read_hits'] += 1
            return self.dirty_sectors[lsn]
            
        # 2. Check read cache (LRU)
        if lsn in self.read_cache:
            self.stats['read_hits'] += 1
            data = self.read_cache.pop(lsn)
            self.read_cache[lsn] = data  # Move to end (most recent)
            return data
            
        # 3. Read from disk
        self.stats['read_misses'] += 1
        if not self.file:
            return None
            
        try:
            self.file.seek(lsn * SECTOR_SIZE)
            data = self.file.read(SECTOR_SIZE)
            activity_led.blink()
            if len(data) < SECTOR_SIZE:
                data = data + bytes(SECTOR_SIZE - len(data))
            
            # Add to read cache (reduced size for memory optimization)
            self.read_cache[lsn] = data
            if len(self.read_cache) > MAX_READ_CACHE_ENTRIES:
                # Remove oldest (first)
                self.read_cache.pop(next(iter(self.read_cache)))
            return data
        except Exception as e:
            print(f"Read Error LSN {lsn}: {e}")
            return None

    def write_sector(self, lsn, data):
        """Write a sector to the write-back cache (deferred write to flash)."""
        if lsn < 0:
            print(f"Write Error: Invalid LSN {lsn}")
            return False
        if len(data) != SECTOR_SIZE:
            print(f"Write Error: Data length {len(data)} != {SECTOR_SIZE}")
            return False
        self.stats['write_count'] += 1
        self.dirty_sectors[lsn] = data
        activity_led.blink()
        # Keep read cache consistent
        self.read_cache[lsn] = data
        if len(self.read_cache) > MAX_READ_CACHE_ENTRIES:
            self.read_cache.pop(next(iter(self.read_cache)))
        return True

class DriveWireServer:
    """DriveWire 4 protocol server implementation for MicroPython."""
    
    def __init__(self):
        self.config = shared_config
        self.uart = None
        self.drives = [None] * NUM_DRIVES
        self.running = False
        self.print_buffer = bytearray()
        self.stats = {
            'last_drive': 0, 
            'last_stat': 0, 
            'last_opcode': 0,
            'serial': {}  # Key: Channel, Val: {tx: 0, rx: 0}
        }
        self.log_buffer = []
        self.monitor_channel = -1
        self.terminal_buffer = bytearray()
        self.channels = [bytearray() for _ in range(NUM_CHANNELS)]
        self.tcp_connections = {}  # Key: Channel (int), Value: (reader, writer, task)
        self.reload_config()

    def reload_config(self):
        """Reload configuration and reinitialize drives and UART."""
        # Close existing drives
        for d in self.drives:
            if d:
                d.close()
        
        # Load drives from config
        drive_paths = self.config.get("drives")
        for i in range(NUM_DRIVES):
            path = drive_paths[i]
            if path:
                try:
                    self.drives[i] = VirtualDrive(path)
                except Exception as e:
                    print(f"Failed to mount drive {i}: {e}")
                    self.drives[i] = None
            else:
                self.drives[i] = None

        # Re-init UART with configured baud rate
        baud = self.config.get("baud_rate")
        if self.uart:
            self.uart.deinit()
        
        try:
            # UART 0 on Pico W: TX=GP0, RX=GP1
            self.uart = UART(0, baudrate=baud) 
            print(f"UART Initialized at {baud} baud")
        except Exception as e:
            print(f"Failed to init UART: {e}")

    def checksum(self, data):
        s = sum(data)
        return s & 0xFFFF

    def log_msg(self, msg):
        """Add a message to the log buffer (limited size for memory efficiency)."""
        self.log_buffer.append(msg)
        if len(self.log_buffer) > MAX_LOG_ENTRIES:
            self.log_buffer.pop(0)

    def snoop_serial(self, chan, data):
        """Capture serial data for the monitored channel."""
        if chan == self.monitor_channel:
            # Add to terminal buffer
            if isinstance(data, int):
                self.terminal_buffer.append(data)
            else:
                self.terminal_buffer.extend(data)
            # Keep last N bytes for memory efficiency
            if len(self.terminal_buffer) > MAX_TERMINAL_BUFFER_SIZE:
                self.terminal_buffer = self.terminal_buffer[-MAX_TERMINAL_BUFFER_SIZE:]

    async def run(self):
        print("Starting DriveWire Loop...")
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self.flush_loop())
        
        while self.running:
            try:
                # Read 1 byte for OpCode
                # We use uasyncio.StreamReader if available or just poll UART
                # UART.any() is non-blocking.
                
                if self.uart.any():
                    opcode_byte = self.uart.read(1)
                    if not opcode_byte:
                        await asyncio.sleep(0.001)
                        continue
                    
                    opcode = opcode_byte[0]
                    self.stats['last_opcode'] = opcode
                    
                    # Process OpCodes
                    if opcode in (OP_RESET, OP_RESET2, OP_RESET3):
                        # RESET
                        # Flush buffers
                        while self.uart.any():
                            self.uart.read()
                        print("Reset received")
                        
                    elif opcode == OP_DWINIT:
                         # Read capability byte
                         cap = await self.read_bytes(1)
                         if cap:
                             # Send our capability (0)
                             self.uart.write(bytes([0]))
                             print("DWINIT Handshake")

                    elif opcode in (OP_READ, OP_READEX, OP_REREAD, OP_REREADEX):
                        # READ / READEX / REREAD / REREADEX
                        # All these use a 4-byte request: Drive(1) + LSN(3)
                        req = await self.read_bytes(4)
                        if req:
                            drive_num = req[0]
                            lsn = (req[1] << 16) | (req[2] << 8) | req[3]
                            
                            is_extended = opcode in (OP_READEX, OP_REREADEX)
                            
                            if drive_num < NUM_DRIVES and self.drives[drive_num]:
                                data = self.drives[drive_num].read_sector(lsn)
                                if data:
                                    cs = self.checksum(data)
                                    if is_extended:
                                        # Extended Read: 256 bytes data -> CoCo calcs checksum -> CoCo sends checksum -> Server ACKs
                                        self.uart.write(data)
                                        # Wait for CoCo checksum (2 bytes)
                                        coco_cs_bytes = await self.read_bytes(2)
                                        if coco_cs_bytes:
                                            coco_cs = (coco_cs_bytes[0] << 8) | coco_cs_bytes[1]
                                            if coco_cs == cs:
                                                self.uart.write(bytes([0])) # No Error
                                            else:
                                                self.uart.write(bytes([243])) # E_CRC
                                    else:
                                        # Standard Read: 0x00 + Checksum(2) + Data(256)
                                        resp = bytearray([0])
                                        resp += struct.pack(">H", cs)
                                        resp += data
                                        self.uart.write(resp)
                                else:
                                    # Read Failure
                                    if is_extended:
                                        self.uart.write(bytes([0] * 256)) # Send zeros? Spec says 0-255 value.. wait.
                                        # Spec says: "If an error occurs... it shall return the Read Failure packet: 0-255 | 0 (256 bytes of 0)"
                                        # Actually it implies sending 256 bytes of zero?
                                        self.uart.write(bytes([0] * 256))
                                        # Then we still expect checksum from CoCo?
                                        # "Upon receipt of either the Read Success or the Read Failure packet, the CoCo shall... Compute checksum... Send checksum"
                                        # So yes, we send 256 bytes of garbage, consume checksum, then send error code.
                                        await self.read_bytes(2) 
                                        self.uart.write(bytes([240])) # E_UNIT
                                    else:
                                        self.uart.write(bytes([240])) # E_UNIT
                            else:
                                # Unit error
                                if is_extended:
                                     self.uart.write(bytes([0] * 256))
                                     await self.read_bytes(2) 
                                     self.uart.write(bytes([240]))
                                else:
                                     self.uart.write(bytes([240])) # E_UNIT

                    elif opcode in (OP_WRITE, OP_REWRITE):
                        # Write / ReWrite
                        # Req: Drive(1) + LSN(3) + Data(256) + Checksum(2)
                        header = await self.read_bytes(4) 
                        if header:
                            drive_num = header[0]
                            lsn = (header[1] << 16) | (header[2] << 8) | header[3]
                            
                            data = await self.read_bytes(SECTOR_SIZE)
                            checksum_bytes = await self.read_bytes(2)
                            
                            if data and checksum_bytes:
                                remote_cs = (checksum_bytes[0] << 8) | checksum_bytes[1]
                                local_cs = self.checksum(data)
                                
                                if remote_cs == local_cs:
                                    # Write to disk cache
                                    success = False
                                    if drive_num < NUM_DRIVES and self.drives[drive_num]:
                                        success = self.drives[drive_num].write_sector(lsn, data)
                                    
                                    if success:
                                        self.uart.write(bytes([0]))    # ACK
                                    else:
                                        self.uart.write(bytes([240]))  # E_UNIT
                                else:
                                    self.uart.write(bytes([243]))  # E_CRC

                    elif opcode == OP_TIME:
                        # OP_TIME ($23)
                        # Bi-directional.
                        # Server response: Year(0-255, yr-1900), Month(1-12), Day(1-31), Hour(0-23), Minute(0-59), Second(0-59)
                        try:
                            import time_sync
                            t = time_sync.get_local_time()
                            if not t or len(t) < 6:
                                raise ValueError("Invalid time tuple")
                            # t is (year, month, day, hour, minute, second, wday, yday)
                            year = t[0] - 1900
                            if year < 0: year = 0
                            if year > 255: year = 255
                            resp = bytes([year, t[1], t[2], t[3], t[4], t[5]])
                        except Exception as e:
                            print(f"OP_TIME Error: {e}")
                            resp = bytes([0, 1, 1, 0, 0, 0])  # Fallback: 1900-01-01 00:00:00
                        self.uart.write(resp)

                    elif opcode == OP_PRINT:
                        # OP_PRINT ($50) + 1 byte
                        b = await self.read_bytes(1)
                        if b:
                            self.print_buffer.extend(b)
                    
                    elif opcode == OP_PRINTFLUSH:
                        # OP_PRINTFLUSH ($46)
                        # Flush buffer to stdout (log)
                        try:
                            # Try decoding as text, fallback to hex if needed
                            msg = self.print_buffer.decode('utf-8', 'ignore')
                            print(f"[PRINTER] {msg}")
                        except Exception:
                            print(f"[PRINTER HEX] {self.print_buffer.hex()}")
                        self.print_buffer = bytearray()
                        
                    elif opcode == OP_GETSTAT:
                        # OP_GETSTAT ($47) + Drive(1) + Code(1)
                        # Server just logs it/updates stats? Spec says "informational purposes only".
                        req = await self.read_bytes(2)
                        if req:
                            self.stats['last_drive'] = req[0]
                            self.stats['last_stat'] = req[1]
                            # print(f"GETSTAT Drv:{req[0]} Code:{req[1]}")
                            
                    elif opcode == OP_SETSTAT:
                        # OP_SETSTAT ($53) + Drive(1) + Code(1)
                        req = await self.read_bytes(2)
                        if req:
                            self.stats['last_drive'] = req[0]
                            self.stats['last_stat'] = req[1]
                            # print(f"SETSTAT Drv:{req[0]} Code:{req[1]}")

                    elif opcode == OP_SERREAD:
                        # OP_SERREAD ($43) - Polling
                        # Response: Byte 1 (Status/Data Avail), Byte 2 (Data or Count)
                        found_channel = -1
                        for i in range(NUM_CHANNELS):
                            if len(self.channels[i]) > 0:
                                found_channel = i
                                break
                                
                        if found_channel >= 0 and len(self.channels[found_channel]) > 0:
                            # We have data!
                            ch_idx = found_channel
                            response_byte_1 = ch_idx + 1
                            data_byte = self.channels[ch_idx].pop(0)
                            response_byte_2 = data_byte
                            self.uart.write(bytes([response_byte_1, response_byte_2]))
                            
                            # Stats
                            if ch_idx not in self.stats['serial']: self.stats['serial'][ch_idx] = {'tx':0, 'rx':0}
                            self.stats['serial'][ch_idx]['rx'] += 1 # Rx from CoCo perspective (read)
                            
                            # Snoop
                            self.snoop_serial(ch_idx, data_byte)
                        else:
                            self.uart.write(bytes([0, 0]))

                    elif opcode == OP_SERWRITE:
                        # OP_SERWRITE ($C3) + Channel(1) + Data(1)
                        req = await self.read_bytes(2)
                        if req:
                            chan = req[0]
                            val = req[1]
                            # Handle Write. 
                            if chan in self.tcp_connections:
                                try:
                                    _, writer, _ = self.tcp_connections[chan]
                                    writer.write(bytes([val]))
                                    await writer.drain()
                                    
                                    # Stats
                                    if chan not in self.stats['serial']: self.stats['serial'][chan] = {'tx':0, 'rx':0}
                                    self.stats['serial'][chan]['tx'] += 1
                                    
                                    # Snoop
                                    self.snoop_serial(chan, val)
                                    
                                except Exception as e:
                                    print(f"TCP Write Error Ch{chan}: {e}")
                                    # Clean up dead connection
                                    self.log_msg(f"TCP Ch{chan} write failed, closing")
                                    await self.close_tcp(chan)
                            else:
                                pass # No connection, discard

                    elif (opcode & 0xF0) == 0x80:
                        # FASTWRITE ($8x) + Data(1)
                        # Channel is opcode & 0x0F
                        chan = opcode & 0x0F
                        val = await self.read_bytes(1)
                        if val:
                            self.log_msg(f"FASTWRITE Ch{chan}: data discarded (unimplemented)")

                    elif opcode == OP_SERINIT:
                         # 1 byte channel
                         ch_byte = await self.read_bytes(1)
                         if ch_byte:
                             chan = ch_byte[0]
                             # Check config for mapping
                             smap = self.config.get("serial_map")
                             # Keys are strings in json
                             if smap and str(chan) in smap:
                                 mapping = smap[str(chan)]
                                 host = mapping['host']
                                 port = mapping['port']
                                 mode = mapping.get('mode', 'client') # client or server
                                 
                                 print(f"Initialize VSerial Ch{chan} ({mode}) -> {host}:{port}")
                                 try:
                                     # Close existing if needed
                                     if chan in self.tcp_connections:
                                         await self.close_tcp(chan)
                                     
                                     if mode == 'server':
                                         # Start a server
                                         # We use a helper to capture chan in closure
                                         def make_accept_handler(c):
                                             return lambda r, w: self.tcp_accept_handler(c, r, w)
                                             
                                         server = await asyncio.start_server(make_accept_handler(chan), host, port)
                                         # Store server object so we can close it?
                                         # Actually asyncio.start_server returns a Server object.
                                         # But we also need to store the active client connection if one is made.
                                         # tcp_connections currently stores (reader, writer, task).
                                         # For server mode, we might need to store (server_obj, current_client_tuple).
                                         # To keep it simple: tcp_connections will ONLY store the active data connection (reader, writer, task).
                                         # We will need a separate dict for "servers" so we can close the listening port.
                                         if not hasattr(self, 'tcp_servers'): self.tcp_servers = {}
                                         self.tcp_servers[chan] = server
                                         print(f"Listening on {host}:{port} for Ch{chan}")
                                     else:
                                         # Client mode
                                         reader, writer = await asyncio.open_connection(host, port)
                                         # Start background reader
                                         task = asyncio.create_task(self.tcp_reader_task(chan, reader))
                                         self.tcp_connections[chan] = (reader, writer, task)

                                 except Exception as e:
                                     print(f"Failed to connect/listen VSerial Ch{chan}: {e}")

                    
                    elif opcode == OP_SERTERM:
                         # 1 byte channel
                         ch_byte = await self.read_bytes(1)
                         if ch_byte:
                             chan = ch_byte[0]
                             await self.close_tcp(chan)
                             # Also close server if any
                             if hasattr(self, 'tcp_servers') and chan in self.tcp_servers:
                                 self.tcp_servers[chan].close()
                                 # await self.tcp_servers[chan].wait_closed() # Optional in recent MP?
                                 del self.tcp_servers[chan]
                                 print(f"Stopped Listening on Ch{chan}")
                         
                    elif opcode == OP_SERSETSTAT:
                        # Channel(1) + Code(1) + Optional...
                        req = await self.read_bytes(2)
                        if req:
                            code = req[1]
                            if code == 0x28: # SS.ComSt -> 26 more bytes!
                                await self.read_bytes(26)

                    elif opcode in (OP_NAMEOBJ_MOUNT, OP_NAMEOBJ_CREATE):
                        # OP_NAMEOBJ_MOUNT ($01) / CREATE ($02) + Len(1) + Name(Len)
                        # Response: DriveNum(1) or 0 on fail.
                        ln_b = await self.read_bytes(1)
                        if ln_b:
                            ln = ln_b[0]
                            name_b = await self.read_bytes(ln)
                            if name_b:
                                name = name_b.decode('ascii', 'ignore')
                                print(f"NamedObj Mount/Create: {name}")
                                # Try to mount it.
                                # Find free drive slot
                                free_drive = -1
                                for i in range(NUM_DRIVES):
                                    if self.drives[i] is None:
                                        free_drive = i
                                        break
                                
                                if free_drive >= 0:
                                    # Try to mount
                                    try:
                                        # Assume file exists locally
                                        vd = VirtualDrive(name)
                                        if vd.file:
                                            self.drives[free_drive] = vd
                                            self.uart.write(bytes([free_drive]))
                                            print(f"Mounted {name} to Drive {free_drive}")
                                        else:
                                            self.uart.write(bytes([0]))
                                    except Exception:
                                        self.uart.write(bytes([0]))
                                else:
                                    self.uart.write(bytes([0])) # No free drives

                    elif opcode == OP_WIREBUG:
                        # OP_WIREBUG ($42) + CoCoType(1) + CPUType(1) + Reserved(21)??
                        # Param 3 says 3-23 reserved, so 21 bytes. Total 23 bytes payload.
                        wb_data = await self.read_bytes(23)
                        if wb_data:
                            print("Entered WireBug Mode")
                        else:
                            print("WireBug handshake timeout")
                        # We just stay silent now, as we are the server and we initiate commands.
                        # If we don't send commands, CoCo just waits. 
                        # To exit, we could send OP_WIREBUG_GO ($47) but usually we wait for user input.

                    elif opcode == OP_INIT:
                         pass # No response needed
                    
                    elif opcode == OP_TERM:
                         pass # No response needed
                        
                else:
                    await asyncio.sleep(0.01)  # Yield to other tasks (reduced CPU usage when idle)
                    
            except Exception as e:
                print(f"DW Error: {e}")
                await asyncio.sleep(1)

    async def tcp_accept_handler(self, chan, reader, writer):
        try:
            peer = writer.get_extra_info('peername')
            print(f"Accepted connection on Ch{chan} from {peer}")
        except Exception:
            print(f"Accepted connection on Ch{chan} (peername unavailable)")
        # If we already have a connection on this channel, close it?
        # Simple server: One client at a time overrides.
        if chan in self.tcp_connections:
            await self.close_tcp(chan)
            
        task = asyncio.create_task(self.tcp_reader_task(chan, reader))
        self.tcp_connections[chan] = (reader, writer, task)

    async def tcp_reader_task(self, chan, reader):
        print(f"Started Reader Task for Ch{chan}")
        try:
            while True:
                data = await reader.read(128)
                if not data: 
                    break # Connection closed
                self.channels[chan].extend(data)
                # Stats (incoming from TCP -> to be Read by CoCo)
                # Wait, 'rx' above was read by CoCo. Let's call this 'buffered'.
                # Actually let's just count it as part of 'read' potential?
                # Simpler: TCP In vs TCP Out.
                # Let's count it here? Or just count when actual OP_SERREAD happens?
                # User asked for "activity". 
        except Exception as e:
            print(f"TCP Reader Error Ch{chan}: {e}")
            self.log_msg(f"TCP Err Ch{chan}: {e}")
        finally:
            print(f"Reader Task Ch{chan} Ended")
            self.log_msg(f"TCP Ch{chan} Disconnected")
            # We don't necessarily close the whole connection here as it might be a temporary network blip or fin?
            # But usually EOF means closed.
            # self.close_tcp(chan) # calling this might recurse if we are not careful or block?
            # Just let it die. SERTERM/SERINIT will cleanup.
            pass

    async def close_tcp(self, chan):
        if chan in self.tcp_connections:
            reader, writer, task = self.tcp_connections[chan]
            try:
                task.cancel()
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            del self.tcp_connections[chan]
            self.channels[chan] = bytearray() # Clear buffer
            print(f"Closed VSerial Ch{chan}")

    async def read_bytes(self, count):
        """Read exact number of bytes from UART with timeout."""
        data = bytearray()
        attempts = 0
        max_attempts = 1000  # ~1 second timeout
        
        while len(data) < count and attempts < max_attempts:
            if self.uart.any():
                chunk = self.uart.read(count - len(data))
                if chunk:
                    data.extend(chunk)
                    attempts = 0  # Reset on successful read
            else:
                await asyncio.sleep(0.001)
                attempts += 1
                
        return data if len(data) == count else None

    def stop(self):
        self.running = False
        for i, d in enumerate(self.drives):
            if d:
                try:
                    d.close()
                except Exception as e:
                    print(f"Error closing drive {i}: {e}")

    async def flush_loop(self):
        """Periodically flush dirty sectors to disk (flash wear protection)."""
        while self.running:
            await asyncio.sleep(60)  # Flush every 60 seconds of inactivity
            for i, d in enumerate(self.drives):
                if d:
                    try:
                        d.flush()
                    except Exception as e:
                        print(f"Flush loop error drive {i}: {e}")

