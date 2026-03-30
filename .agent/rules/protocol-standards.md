---
trigger: always_on
---
# Protocol & Sector Server Standards

## 🕹️ DriveWire Protocol Consistency
1. **Handshake**: Verify `OP_DWINIT`/`OP_READEX` against `DriveWire Specification.md`.
2. **Timing**: Avoid CPU-heavy tasks between CoCo command and response (UART timeout).
3. **Checksum**: READEX/WRITE must use 16-bit sum (sum of bytes).
4. **WDT Safety**: Loops waiting for UART/Network **MUST** feed watchdog. Use `self.read_bytes()`.
5. **Errors**: Use `E_NOTRDY`, `E_WP`, etc. Log via `resilience.log()` (Level 2/3).
6. **OP_SERREAD (Polling)**: Must handle dual response modes:
   - **Mode 1 (1-15)**: Single byte (Byte 1 = channel+1, Byte 2 = data).
   - **Mode 2 (17-31)**: Bulk count (Byte 1 = channel+1+16, Byte 2 = bytes waiting).
7. **OP_NAMEOBJ**: Mount and Create share a handler; both Mount the existing file. Lease management is not fully implemented; returns Drive Number or 0 on fail.

## 🌐 Remote Sector Server Protocol
1. **GET `/info`**: Returns Json `{disk_count, disks:[{name, size, total_sectors}]}`.
2. **GET `/sector/<file>/<lsn>`**: Returns exactly 256 bytes (binary). Pad if EOF.
3. **GET `/sectors/<file>/<lsn>?count=N`**: Returns `N * 256` bytes. Sequential. Max `N=64`.
4. **PUT `/sector/<file>/<lsn>`**: Accepts 256 bytes. Atomic write.
5. **Security**: Sanitize paths (`os.path.basename`). Reject `..` or leading slashes.
6. **CORS**: `OPTIONS` must return `Access-Control-Allow-Origin: *`.

## 📐 Implementation Reference
| Feature | File | Function/Class |
|---------|------|----------------|
| Handshake/Opcode | `drivewire.py` | `DriveWireServer.run` |
| Sector Fetch | `drivewire.py` | `RemoteDrive.read_sector` |
| Multi-sector | `sector_server.py` | `do_GET` (bulk read-ahead) |
| Path Safety | `sector_server.py` | `_get_disk_path` |
