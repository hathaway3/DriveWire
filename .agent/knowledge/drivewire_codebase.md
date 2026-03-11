# DriveWire MicroPython Server — Codebase Knowledge

> Last updated: 2026-03-07 — Consolidated from 15+ agent sessions.

## Project Overview

A MicroPython DriveWire 4.0 protocol server running on **Raspberry Pi Pico W / Pico 2 W** (RP2040/RP2350). It bridges a **TRS-80 Color Computer (CoCo)** via UART serial to modern storage (SD card, HTTP remote servers) and networking (TCP virtual serial channels). Includes a web UI for management.

**Repository**: [DriveWire](../../)
**MicroPython source**: [micropython/](../../micropython/)
**Swift reference**: [DriveWireHost.swift](../../swift/DriveWire/Model/DriveWireHost.swift) (~1768 lines, macOS reference implementation)
**Specification**: [DriveWire Specification.md](../../DriveWire%20Specification.md)

---

## File Structure & Responsibilities

| File | Lines | Purpose |
|------|-------|---------|
| [boot.py](../../micropython/boot.py) | 73 | WiFi connect, SD card mount, lib install. Feeds WDT between steps. |
| [main.py](../../micropython/main.py) | 77 | Entry point. Starts DW server + web server as async tasks. WDT init here. |
| [drivewire.py](../../micropython/drivewire.py) | ~1150 | **Core protocol engine.** Opcode dispatch, VirtualDrive, RemoteDrive, RFM, serial channels. |
| [web_server.py](../../micropython/web_server.py) | ~910 | Microdot web API. File management, config, remote cloning, status. |
| [config.py](../../micropython/config.py) | 122 | JSON config with validation. Stored in `config.json`. |
| [resilience.py](../../micropython/resilience.py) | 135 | Logging (file + syslog), SafeWatchdog wrapper, GC helper, LED blink codes. |
| [syslog.py](../../micropython/syslog.py) | 109 | UDP syslog client with network-ready check and 30s backoff on failure. |
| [sd_card.py](../../micropython/sd_card.py) | 174 | SPI SD card init/mount/unmount. Has async Lock for concurrent access. |
| [time_sync.py](../../micropython/time_sync.py) | 62 | NTP sync with retry. Periodic 12h re-sync task. |
| [activity_led.py](../../micropython/activity_led.py) | 84 | LED control via CYW43 WiFi chip pin. Context manager `activity()`. |
| [lib_installer.py](../../micropython/lib_installer.py) | 132 | Auto-install microdot + sdcard via mip or GitHub fallback. |
| [fs_repair.py](../../micropython/fs_repair.py) | 62 | Fixes duplicate `/sd` ghost directories on flash. |

---

## Architecture

```
CoCo ──UART──► DriveWireServer.run() ──► Opcode Handlers
                    │                         │
                    │                    VirtualDrive (local .dsk on SD)
                    │                    RemoteDrive (HTTP sector server)
                    │                    TCP Channels (virtual serial)
                    │                    RFM (remote file management)
                    │
                    └──► Web Server (Microdot, port 80)
                              │
                         /api/config, /api/status, /api/files/*
                         /api/serial/*, /api/remote/*
```

### Key Design Patterns

1. **Single async event loop** (`uasyncio`): DW server, web server, WDT feeder, flush loop, and time sync all run as concurrent tasks.
2. **Write-back caching**: `VirtualDrive` caches dirty sectors in RAM and flushes to SD every 60s to protect flash wear.
3. **Read-ahead caching**: `RemoteDrive` fetches `MAX_READ_CACHE_ENTRIES` (8) sectors per HTTP request to reduce network round-trips.
4. **TCP channel mapping**: `serial_map` in config maps CoCo virtual serial channels (0–31) to TCP host:port connections.

---

## DriveWire Protocol Implementation

### Opcode Dispatch

All opcodes handled in `DriveWireServer.run()` main loop via `if/elif` chain:

| Category | Opcodes | Status |
|----------|---------|--------|
| **Reset** | RESET, RESET2, RESET3 | ✅ Implemented |
| **Init** | DWINIT | ✅ Handshake |
| **Disk I/O** | READ, READEX, REREAD, REREADEX, WRITE, REWRITE | ✅ Full impl with caching |
| **Time** | TIME | ✅ With timezone offset |
| **Printer** | PRINT, PRINTFLUSH | ✅ Buffer → log |
| **Stats** | GETSTAT, SETSTAT | ✅ Informational only |
| **Serial** | SERREAD, SERWRITE, SERREADM, SERWRITEM, FASTWRITE ($80–$8F), SERGETSTAT, SERSETSTAT, SERINIT, SERTERM | ✅ Full TCP bridging |
| **Named Objects** | NAMEOBJ_MOUNT | ✅ With .dsk validation |
| **WireBug** | WIREBUG | ✅ Handshake only (silent after) |
| **RFM** | OPEN, CHGDIR, SEEK, READ, READLN, GETSTT, CLOSE | ✅ Sandboxed to /sd |
| **RFM (stubs)** | CREATE, MAKDIR, DELETE, WRITE, WRITLN, SETSTT | ❌ Not implemented |

### Important Protocol Details

- **FASTWRITE** is the primary CoCo→server data path (33% more efficient than SERWRITE). Encoded as opcode $80–$8F where channel = opcode & 0x0F.
- **SERREAD** uses dual response modes: single-byte (byte1=1–15) and bulk (byte1=17–31, triggers SERREADM).
- **READEX** has a 3-step handshake: server sends 256 bytes → CoCo sends checksum → server ACKs.
- **Error codes**: E_NONE(0), E_UNIT(240), E_WP(242), E_CRC(243), E_READ(244), E_NOTRDY(246).

### Swift Reference Comparison

The Swift `DriveWireHost.swift` (~1768 lines) is the macOS reference implementation. A detailed cross-reference was performed against both the MicroPython code and the DriveWire Specification.

**What Swift implements fully**: Disk I/O (READ, READEX, WRITE, REWRITE), TIME, PRINT, GETSTAT/SETSTAT, RESET, DWINIT, NAMEOBJ_MOUNT, RFM (all sub-ops including CREATE, MAKDIR, DELETE — which MicroPython stubs).

**What Swift stubs**: Virtual serial handlers (SERREAD, SERWRITE, SERREADM, SERWRITEM, FASTWRITE) — Swift consumes the correct byte counts per the spec but doesn't implement actual TCP bridging or channel queues. The MicroPython implementation is **functionally ahead** on serial.

**Key discrepancies resolved during cross-reference**:
1. **FASTWRITE** — MicroPython was silently discarding data instead of routing to TCP connections (fixed)
2. **SERREADM/SERWRITEM** — MicroPython had opcode constants defined but no handlers (added)
3. **SERGETSTAT** — Missing handler caused protocol sync loss on CoCo side (added)
4. **SERREAD bulk mode** — Single-byte mode worked but bulk response (byte1=17–31) was missing (added)
5. **Terminal channel range** — README documented 0–14 but code supports 0–31 via `NUM_CHANNELS=32` (doc fixed)

---

---

## 🛡️ Security, Resilience & Safety

Detailed rules and patterns for security, exception handling, and memory safety have been moved to specialized rule files to ensure clarity and avoid redundancy.

- **[security-exceptions.md](../rules/security-exceptions.md)**: Path traversal protection, XSS prevention, and standardized exception handling.
- **[mp-raspi-pico.md](../rules/mp-raspi-pico.md)**: Hardware constraints and the detailed **Watchdog Timer (WDT) Strategy**.
- **[streaming-data.md](../rules/streaming-data.md)**: Patterns for handling large data transfers on memory-constrained hardware.
- **[sector-caching.md](../rules/sector-caching.md)**: Write-back, LRU, and RBF-specific caching logic.
- **[task-priority.md](../rules/task-priority.md)**: Cooperative multitasking and the **Performance Checklist**.

---

---

## Known Bugs & Gotchas (from past sessions)

### Duplicate `/sd` Ghost Directory (RP2040)
`os.listdir('/')` can return `['sd', ..., 'sd']` — a physical folder on flash named `sd` conflicts with the SD card mount point. This causes VFS hangs, upload failures, and delete failures. **Fix**: `fs_repair.scrub_root()` runs at boot to rename ghost directories.

### SPI Bus Contention During Uploads
Background polling of SD status (`/api/sd/status`) while a file upload is in progress causes SPI bus contention. The hardware-level SPI driver can deadlock, hanging uploads around 320KB. **Fix**: Frontend sets `_uploading = True` flag; status endpoint returns minimal info without SPI access during uploads.

### SD Card SPI Clock Speed Limits
Tested 1MHz, 2MHz, and 10MHz SPI clock speeds. **Only 1MHz is reliable.** 10MHz and 2MHz both caused initialization failures with a `sdcard.py` driver. MicroPython firmware's built-in SD driver is more stable than the `micropython-lib` version. The experimental `sdcard.py` was removed.

### Frontend Polling Exhausts Pico W RAM  
Concurrent HTTP requests from browser polling (`pollStatus` + `pollSdStatus` + `pollFiles`) can exhaust RAM on the Pico W (264KB total). **Fixes applied**: reduced polling frequency, added in-flight request guards (skip if previous request pending), added `gc.collect()` calls after each request handler, added `_dsk_files_cache` with 30s TTL.

### Streaming Uploads Required
Standard Microdot body parsing buffers the entire request in RAM, causing OOM for files >100KB. **Fix**: `request.stream` is used to read upload data in chunks, writing directly to SD.

### Syslog UDP Spam Before WiFi
During early boot, `syslog.py` was spamming `Errno 113 EHOSTUNREACH` before WiFi connected. **Fix**: Added `wlan.isconnected()` check before attempting UDP send, plus 30s exponential backoff after failures.

---

## Protocol Flow Reference

### DWINIT Handshake
1. CoCo sends `OP_DWINIT` ($5A)
2. Server responds with 1 byte: `0x5A`
3. CoCo sends 1 byte: `0x5A`
4. Connection established.

### READEX (Fast Read)
1. CoCo sends `OP_READEX` + unit + LSN
2. Server responds with 256-byte sector data.
3. CoCo sends 1-byte checksum.
4. Server responds with `0x00` (ACK) or `0xFF` (NAK).

### SERREAD (Virtual Serial)
1. CoCo sends `OP_SERREAD` + channel.
2. Server responds with:
   - `0x00` (No data)
   - `0x01-0x0F` (Data count, followed by bytes)
   - `0x11-0x1F` (Bulk data count, triggers `OP_SERREADM`)

---

---

## ⚡ Performance & Context Checklist

This checklist has been moved to **[task-priority.md](../rules/task-priority.md)** to ensure it is always visible during task execution.

---

## 🔍 Log Analysis Reference

| Prefix | Component | Meaning |
|--------|-----------|---------|
| `DW:` | `drivewire.py` | Protocol transactions, opcodes, errors. |
| `WEB:` | `web_server.py` | API requests, status, config changes. |
| `SYS:` | `resilience.py` | Boot, WDT, Memory, WiFi status. |
| `SD:` | `sd_card.py` | SPI init, mount, bus lock issues. |
