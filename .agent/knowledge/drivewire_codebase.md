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

### Protocol Details
| Context | Implementation Detail |
|---------|-----------------------|
| **FASTWRITE** | Primary CoCo->Server path ($80-$8F). channel = opcode & 0x0F. |
| **SERREAD** | Supports 1-15 (single) and 17-31 (bulk, triggers SERREADM). |
| **READEX** | 3-step: server sends 256B -> CoCo sends checksum -> Server ACKs. |
| **Swift Ref** | Swift implements RFM fully but stubs virtual serial TCP bridging. |

---

### Known Bugs & Hardware Gotchas
| Issue | Cause | Fix/Workaround |
|-------|-------|----------------|
| **Ghost `/sd`** | Folder named `sd` on flash conflicts with mount. | `fs_repair.scrub_root()` at boot. |
| **SPI Deadlock** | Status polling during bulk uploads. | `_uploading` flag suspends polling. |
| **SPI Clock** | Reliability issues at >1MHz. | Hardware SPI fixed at 1MHz. |
| **OOM Polling** | Rapid concurrent polling from browser UI. | Polling guards + aggressive `gc.collect()`. |
| **OOM Uploads** | Buffering >100KB files in Microdot. | Use `request.stream` for chunked SD write. |
| **Syslog Spam** | Early boot UDP send without WiFi. | Added `isconnected()` check + 30s backoff. |

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
