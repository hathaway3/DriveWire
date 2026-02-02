import uasyncio as asyncio
import struct
import os
from machine import UART
from config import shared_config

# OpCodes
OP_dwInit = 0x5a # 'Z' ?? No, typically we follow spec. 
# DW4 Commands:
OP_BKPT = 0x21
OP_TIME = 0x23
OP_INIT = 0x49 # 'I'
OP_TERM = 0x54 # 'T'
OP_READ = 0x52 # 'R'
OP_READEX = 0x58 # 'X'
OP_WRITE = 0x57 # 'W'
OP_RESET = 0xFE
OP_RESET2 = 0xFF
OP_RESET3 = 0xF8
OP_DWINIT = 0x5A # 'Z'
OP_NAMEOBJ_MOUNT = 0x01
OP_NAMEOBJ_CREATE = 0x02
OP_GETSTAT = 0x47
OP_SETSTAT = 0x53
OP_PRINT = 0x50
OP_PRINTFLUSH = 0x46
OP_WIREBUG = 0x42
OP_SERREAD = 0x43
OP_SERWRITE = 0xC3
OP_SERINIT = 0x4E
OP_SERTERM = 0x43 # Wait, C3 is write. SERTERM? Spec might vary. C is channel ops.
OP_SERTERM = 0x43 # Re-using code? Actually typically SERTERM is distinct. 
# Checking typical DW implementations... 
# Actually let's trust my previous impl or these constants.
# SERTERM usually implies closing.
# Let's define the class.

class VirtualDrive:
    def __init__(self, filename):
        self.filename = filename
        self.file = None
        self.dirty_sectors = {} # LSN -> data
        try:
            self.file = open(filename, "r+b")
        except OSError:
             print(f"Failed to open {filename}")

    def close(self):
        self.flush()
        if self.file:
            self.file.close()
            self.file = None

    def flush(self):
        if not self.file or not self.dirty_sectors: return
        try:
            for lsn, data in self.dirty_sectors.items():
                self.file.seek(lsn * 256)
                self.file.write(data)
            self.file.flush()
            self.dirty_sectors = {}
            print(f"Flushed {self.filename}")
        except Exception as e:
            print(f"Flush Error: {e}")

    def read_sector(self, lsn):
        if lsn in self.dirty_sectors:
            return self.dirty_sectors[lsn]
        if not self.file: return None
        try:
            self.file.seek(lsn * 256)
            data = self.file.read(256)
            if len(data) < 256:
                return data + bytes(256 - len(data))
            return data
        except Exception as e:
            print(f"Read Error: {e}")
            return None

    def write_sector(self, lsn, data):
        self.dirty_sectors[lsn] = data
        return True

class DriveWireServer:
    def __init__(self):
        self.config = shared_config
        self.config = shared_config
        self.uart = None
        self.drives = [None] * 4
        self.running = False
        self.print_buffer = bytearray()
        self.stats = {
            'last_drive': 0, 
            'last_stat': 0, 
            'last_opcode': 0,
            'serial': {} # Key: Channel, Val: {tx: 0, rx: 0}
        }
        self.log_buffer = []
        self.monitor_channel = -1
        self.terminal_buffer = bytearray()
        self.channels = [bytearray() for _ in range(32)] # 0-14 VSerial, 15-30 ??? Spec says 30 channels.
        self.tcp_connections = {} # Key: Channel (int), Value: (reader, writer, task)
        # Spec: 0-14 Virtual Serial. 128-142 Virtual Window. 
        # For simplicity, we'll map 128+ to index 16+.
        self.reload_config()

    def reload_config(self):
        # Close existing drives
        for d in self.drives:
            if d: d.close()
        
        # Load drives from config
        drive_paths = self.config.get("drives")
        for i in range(4):
            path = drive_paths[i]
            if path:
                self.drives[i] = VirtualDrive(path)
            else:
                self.drives[i] = None

        # Re-init UART if baud rate changed (not easily done dynamically without restart usually, but let's try)
        baud = self.config.get("baud_rate")
        # Note: UART ID 0 is often the REPL. UART 1 might be better if available, 
        # or we might need to detach REPL. For now assuming UART 0 or 1 depending on board.
        # Raspberry Pi Pico: UART0 on GP0/GP1.
        if self.uart:
             self.uart.deinit()
        
        try:
            # Using UART 0 for now, customize pins for specific board if needed.
            # For Pico W, UART0 is tx=gp0, rx=gp1 usually.
            self.uart = UART(0, baudrate=baud) 
            print(f"UART Initialized at {baud}")
        except Exception as e:
            print(f"Failed to init UART: {e}")

    def checksum(self, data):
        s = sum(data)
        return s & 0xFFFF

    def log_msg(self, msg):
        # Keep last 20 lines
        self.log_buffer.append(msg)
        if len(self.log_buffer) > 20:
            self.log_buffer.pop(0)

    def snoop_serial(self, chan, data):
        if chan == self.monitor_channel:
            # Add to terminal buffer
            if isinstance(data, int):
                self.terminal_buffer.append(data)
            else:
                self.terminal_buffer.extend(data)
            # Keep last 512 bytes
            if len(self.terminal_buffer) > 512:
                self.terminal_buffer = self.terminal_buffer[-512:]

    async def run(self):
        print("Starting DriveWire Loop...")
        self.running = True
        sreader = asyncio.StreamReader(self.uart)
        swriter = asyncio.StreamWriter(self.uart, {})
        
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
                            
                            if drive_num < 4 and self.drives[drive_num]:
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
                        # Total 263 bytes needed (1+3+256+2 = 262 excluding opcode)
                        header = await self.read_bytes(4) 
                        if header:
                            drive_num = header[0]
                            lsn = (header[1] << 16) | (header[2] << 8) | header[3]
                            
                            data = await self.read_bytes(256)
                            checksum_bytes = await self.read_bytes(2)
                            
                            if data and checksum_bytes:
                                remote_cs = (checksum_bytes[0] << 8) | checksum_bytes[1]
                                local_cs = self.checksum(data)
                                
                                if remote_cs == local_cs:
                                    # Write to disk
                                    success = False
                                    if drive_num < 4 and self.drives[drive_num]:
                                        success = self.drives[drive_num].write_sector(lsn, data)
                                    
                                    if success:
                                        self.uart.write(bytes([0])) # ACK
                                    else:
                                        self.uart.write(bytes([240])) # Write Error
                                else:
                                    self.uart.write(bytes([243])) # E_CRC
                            else:
                                # Timeout reading data
                                pass

                    elif opcode == OP_TIME:
                        # OP_TIME ($23)
                        # Bi-directional.
                        # Server response: Year(0-255, yr-1900), Month(1-12), Day(1-31), Hour(0-23), Minute(0-59), Second(0-59)
                        import time_sync
                        t = time_sync.get_local_time()
                        # t is (year, month, day, hour, minute, second, wday, yday)
                        year = t[0] - 1900
                        if year < 0: year = 0
                        if year > 255: year = 255
                        
                        resp = bytes([year, t[1], t[2], t[3], t[4], t[5]])
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
                        
                        # Simplified Check: Do we have data for any channel?
                        # For now, we don't populate channels with data source, so always empty.
                        # Unless loopback? Let's just return "No Data".
                        # Byte 1 = 0: No data.
                        # Byte 2 = Ignored.
                        
                        # Check if any channel has data?
                        # For this basic implementation, we just echo nothing.
                        found_channel = -1
                        for i in range(15):
                            if len(self.channels[i]) > 0:
                                found_channel = i
                                break
                                
                        if found_channel >= 0:
                            # We have data!
                            # Byte 1: 1 to 15 (Channel + 1) -> Byte 2 is single byte data
                            # OR 17-31 -> Byte 2 is count
                            # Let's send single byte for now
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
                            else:
                                pass # No connection, discard

                    elif (opcode & 0xF0) == 0x80:
                        # FASTWRITE ($8x) + Data(1)
                        # Channel is opcode & 0x0F
                        chan = opcode & 0x0F
                        val = await self.read_bytes(1)
                        pass

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
                                # Find free drive?
                                free_drive = -1
                                for i in range(4):
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
                        await self.read_bytes(23)
                        print("Entered WireBug Mode")
                        # We just stay silent now, as we are the server and we initiate commands.
                        # If we don't send commands, CoCo just waits. 
                        # To exit, we could send OP_WIREBUG_GO ($47) but usually we wait for user input.

                    elif opcode == OP_INIT:
                         pass # No response needed
                    
                    elif opcode == OP_TERM:
                         pass # No response needed
                        
                else:
                    await asyncio.sleep(0.001) # Yield to other tasks (web server)
                    
            except Exception as e:
                print(f"DW Error: {e}")
                await asyncio.sleep(1)

    async def tcp_accept_handler(self, chan, reader, writer):
        print(f"Accepted connection on Ch{chan} from {writer.get_extra_info('peername')}")
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
        data = bytearray()
        # Simple timeout mechanism
        attempts = 1000 # 1 second approx
        while len(data) < count and attempts > 0:
            if self.uart.any():
                chunk = self.uart.read(count - len(data))
                if chunk:
                    data.extend(chunk)
            else:
                await asyncio.sleep(0.001)
                attempts -= 1
        return data if len(data) == count else None

