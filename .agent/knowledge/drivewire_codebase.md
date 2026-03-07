# DriveWire MicroPython Server — Codebase Knowledge

> Last updated: 2026-03-07 by security/reliability review session.

## Project Overview

A MicroPython DriveWire 4.0 protocol server running on **Raspberry Pi Pico W / Pico 2 W** (RP2040/RP2350). It bridges a **TRS-80 Color Computer (CoCo)** via UART serial to modern storage (SD card, HTTP remote servers) and networking (TCP virtual serial channels). Includes a web UI for management.

**Repository**: [/Users/jimmiehathaway/DriveWire](file:///Users/jimmiehathaway/DriveWire)
**MicroPython source**: [/Users/jimmiehathaway/DriveWire/micropython/](file:///Users/jimmiehathaway/DriveWire/micropython/)
**Swift reference**: [DriveWireHost.swift](file:///Users/jimmiehathaway/DriveWire/swift/DriveWire/Model/DriveWireHost.swift) (~1768 lines, macOS reference implementation)
**Specification**: [DriveWire Specification.md](file:///Users/jimmiehathaway/DriveWire/DriveWire%20Specification.md)

---

## File Structure & Responsibilities

| File | Lines | Purpose |
|------|-------|---------|
| [boot.py](file:///Users/jimmiehathaway/DriveWire/micropython/boot.py) | 73 | WiFi connect, SD card mount, lib install. Feeds WDT between steps. |
| [main.py](file:///Users/jimmiehathaway/DriveWire/micropython/main.py) | 77 | Entry point. Starts DW server + web server as async tasks. WDT init here. |
| [drivewire.py](file:///Users/jimmiehathaway/DriveWire/micropython/drivewire.py) | ~1150 | **Core protocol engine.** Opcode dispatch, VirtualDrive, RemoteDrive, RFM, serial channels. |
| [web_server.py](file:///Users/jimmiehathaway/DriveWire/micropython/web_server.py) | ~910 | Microdot web API. File management, config, remote cloning, status. |
| [config.py](file:///Users/jimmiehathaway/DriveWire/micropython/config.py) | 122 | JSON config with validation. Stored in `config.json`. |
| [resilience.py](file:///Users/jimmiehathaway/DriveWire/micropython/resilience.py) | 135 | Logging (file + syslog), SafeWatchdog wrapper, GC helper, LED blink codes. |
| [syslog.py](file:///Users/jimmiehathaway/DriveWire/micropython/syslog.py) | 109 | UDP syslog client with network-ready check and 30s backoff on failure. |
| [sd_card.py](file:///Users/jimmiehathaway/DriveWire/micropython/sd_card.py) | 174 | SPI SD card init/mount/unmount. Has async Lock for concurrent access. |
| [time_sync.py](file:///Users/jimmiehathaway/DriveWire/micropython/time_sync.py) | 62 | NTP sync with retry. Periodic 12h re-sync task. |
| [activity_led.py](file:///Users/jimmiehathaway/DriveWire/micropython/activity_led.py) | 84 | LED control via CYW43 WiFi chip pin. Context manager `activity()`. |
| [lib_installer.py](file:///Users/jimmiehathaway/DriveWire/micropython/lib_installer.py) | 132 | Auto-install microdot + sdcard via mip or GitHub fallback. |
| [fs_repair.py](file:///Users/jimmiehathaway/DriveWire/micropython/fs_repair.py) | 62 | Fixes duplicate `/sd` ghost directories on flash. |

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

The Swift `DriveWireHost.swift` is the macOS reference implementation. Key finding: **Swift serial handlers are stubs** — they consume correct byte counts but don't implement TCP bridging or channel queues. The MicroPython code is functionally ahead.

---

## Security Hardening (Applied 2026-03-07)

### Path Traversal Protection

- **Web API**: `_sanitize_path()` in `web_server.py` — rejects `..`, restricts to `/sd/` or root-level `.dsk` files. Applied to delete/download endpoints.
- **RFM Protocol**: `_sanitize_rfm_path()` in `drivewire.py` — sandboxes all RFM file operations to `RFM_BASE_DIR = '/sd'`.
- **NamedObj Mount**: Rejects filenames containing `..` or not ending in `.dsk`.

### Input Validation

- **Config GET**: WiFi password masked as `'********'` in API responses.
- **File creation**: Capped at `MAX_DSK_SIZE = 50MB`.
- **Monitor channel**: Validated to range -1 (off) through 31.
- **Config POST**: Already had baud rate and timezone validation in `config.py`.

### No Authentication

The web server runs on port 80 with **no auth**. This is by design for a LAN-only embedded device, but be aware all endpoints are open.

---

## WDT (Watchdog Timer) Patterns

### Hardware Constraints (RP2040)

- **Cannot be disabled** once started — `machine.WDT` is permanent until reboot.
- **Max timeout**: ~8388ms (set to 8000ms).
- Once started, must be fed continuously or the device resets.

### Feeding Strategy

| Location | Pattern | Why |
|----------|---------|-----|
| `main.py` line 47 | Async task, every 2s | Primary feeder during normal operation |
| `main.py` line 68 | `machine.Timer` on KeyboardInterrupt | Keeps device alive in REPL after Ctrl+C |
| `drivewire.py` run() | After every opcode transaction | Prevents starvation during sustained I/O |
| `drivewire.py` read_bytes() | Every 500 iterations (~500ms) | Prevents starvation during UART timeout |
| `boot.py` | Between WiFi/SD/lib steps | Prevents starvation during slow boot |
| `web_server.py` | During upload/clone loops | Prevents starvation during long SD writes |
| `drivewire.py` flush_loop() | Before each drive flush | Prevents starvation during multi-drive flush |

### Known Safe Patterns

- `boot.py` caps `time.sleep()` to 6s (within 8s WDT window).
- `time_sync.py` retry: 3 × 1s = 3s max blocking (safe).

---

## Exception Handling Conventions

- **Always use `resilience.log()`** — never raw `print()` for errors (ensures file + syslog logging).
- **No bare `except:`** — all exception clauses specify types (`OSError`, `Exception`, etc.) to avoid catching `KeyboardInterrupt`.
- **Hardware I/O** (UART, SPI, WiFi): wrap in `try/except OSError`.
- **TCP connections**: catch `Exception`, log, then `close_tcp()`.
- **Levels**: 0=Debug, 1=Info, 2=Warning, 3=Error, 4=Critical.

---

## Configuration

Stored in [config.json](file:///Users/jimmiehathaway/DriveWire/micropython/config.json). Key fields:

| Key | Type | Description |
|-----|------|-------------|
| `baud_rate` | int | UART speed (validated against VALID_BAUD_RATES) |
| `drives` | list[4] | Paths to .dsk files or `http://` URLs for remote drives |
| `serial_map` | dict | Channel → `{host, port, mode}` for TCP bridging |
| `sd_spi_*` | int | SPI pins for SD card (id, sck, mosi, miso, cs) |
| `remote_servers` | list | `[{name, url}]` for remote sector servers |
| `syslog_server` | str | Remote syslog host (UDP) |

---

## Known Limitations & Future Work

1. **RFM write operations** (CREATE, MAKDIR, DELETE, WRITE, WRITLN) are **stubbed** — return error codes without implementation.
2. **VWindow FASTWRITE** ($91–$9E) not handled — only standard serial FASTWRITE ($80–$8F) implemented.
3. **SERSETSTAT SS.Open/SS.Close** not implemented — uses SERINIT/SERTERM (4.0.5+ approach) instead.
4. **No HTTPS** — remote server communication is HTTP only.
5. **Single client per TCP channel** — new connections override existing ones.
6. **No web authentication** — all API endpoints are unauthenticated.

---

## Development Tips

- **2-second boot delay** in `main.py` allows interrupting boot loops via Thonny/REPL.
- **`resilience.blink_state()`** provides visual debugging: 'boot' (3 quick), 'wifi_wait' (slow), 'error' (rapid), 'running' (one long).
- **SD card lock** (`sd_card.get_lock()`) should be acquired for concurrent SD access, though currently only used in `get_info()`.
- **File cache invalidation**: Set `_dsk_files_cache = None` after any SD file modification to force rescan.
- **Config reload**: Call `app.dw_server.reload_config()` after config changes to hot-reload drives and serial map.
