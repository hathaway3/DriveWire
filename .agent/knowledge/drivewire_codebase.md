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
- **Max timeout**: ~8388ms (set to 8000ms). Originally was 15s but fixed to 8s.
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

## ⚡ Performance Checklist for Agents

1. **Avoid `view_file` on `drivewire.py`**: It is 1100+ lines. Use `view_file_outline` or `grep_search` first.
2. **Minimize `os.listdir`**: Use the `_dsk_files_cache` in the Web API or query `shared_config`.
3. **Batch Writes**: When updating multiple files on the SD card, call `os.sync()` only once at the end.
4. **WDT Awareness**: If adding a loop that takes >1s, YOU MUST call `machine.WDT().feed()` inside that loop.

---

## 🔍 Log Analysis Reference

| Prefix | Component | Meaning |
|--------|-----------|---------|
| `DW:` | `drivewire.py` | Protocol transactions, opcodes, errors. |
| `WEB:` | `web_server.py` | API requests, status, config changes. |
| `SYS:` | `resilience.py` | Boot, WDT, Memory, WiFi status. |
| `SD:` | `sd_card.py` | SPI init, mount, bus lock issues. |

---

## Web UI Architecture

- **Framework**: Microdot (lightweight async web framework, ~6KB)
- **Theme**: "Radio Shack" retro terminal aesthetic — green-on-dark (`#0f0` on `#222`), `Michroma` headers, `VT323` monospace body
- **Static files**: Served from `/www/static/` (script.js, style.css)
- **Pages**: Main terminal view (`index.html`), Setup page, Debug page
- **API polling**: Frontend polls `/api/status` for drive stats and log buffer, `/api/sd/status` for storage info

### Responsive Design Patterns
The UI uses a mobile-first philosophy with a **600px breakpoint**:
- **Desktop**: 700px max-width centered container, 2-column grids for configuration.
- **Mobile**: Full-width container, single-column stacked layout, larger touch targets for buttons.
- **CRT Effect**: A sticky scanline overlay and flicker animation are applied globally but designed not to interfere with readability on high-DPI mobile screens.

---

## Configuration

Stored in [config.json](../../micropython/config.json). Key fields:

| Key | Type | Description |
|-----|------|-------------|
| `baud_rate` | int | UART speed (validated against VALID_BAUD_RATES) |
| `drives` | list[4] | Paths to .dsk files or `http://` URLs for remote drives |
| `serial_map` | dict | Channel → `{host, port, mode}` for TCP bridging |
| `sd_spi_*` | int | SPI pins for SD card (id, sck, mosi, miso, cs) |
| `remote_servers` | list | `[{name, url}]` for remote sector servers |
| `syslog_server` | str | Remote syslog host (UDP) |

---

## Related Hardware

### COCOMMC.PLD
PLD logic file for the CoCo MMC hardware interface. Handles address decoding, SPI bus control, and data transfer synchronization between the CoCo bus and the DriveWire adapter. Past sessions optimized the state machine and fixed counter reset logic.

### Serial Port Wiring (MAX3232)
CoCo connects via UART through a MAX3232 level shifter with DB9 connector. Wiring documented in `micropython/docs/wiring.md`. Pins: VCC, GND, RXD, TXD.

### NitrOS-9 Level 2 Integration
Documentation for running NitrOS-9 Level 2 over DriveWire was created and lives in the project docs. NitrOS-9 uses the DriveWire protocol for both disk I/O and virtual serial terminals.

---

## Known Limitations & Future Work

1. **RFM write operations** (CREATE, MAKDIR, DELETE, WRITE, WRITLN) are **stubbed** — return error codes without implementation.
2. **VWindow FASTWRITE** ($91–$9E) not handled — only standard serial FASTWRITE ($80–$8F) implemented.
3. **SERSETSTAT SS.Open/SS.Close** not implemented — uses SERINIT/SERTERM (4.0.5+ approach) instead.
4. **No HTTPS** — remote server communication is HTTP only.
5. **Single client per TCP channel** — new connections override existing ones.
6. **No web authentication** — all API endpoints are unauthenticated.
7. **SD SPI speed** — stuck at 1MHz; higher speeds failed in testing.

---

## Testing Infrastructure

### Host-Side Simulation
Unit tests exist in the `micropython/` directory (e.g., `test_drivewire.py`) that mock the `machine` and `network` modules. This allows verifying protocol logic on a standard Python host without a physical Pico.

### Remote Drive Testing
The `micropython/tools/sector_server.py` utility acts as a local HTTP sector server. It can be used to test `RemoteDrive` logic:
- Serves `.dsk` files from a local directory via HTTP.
- Supports the same sector-level API used by remote DriveWire servers.

---

## Development Tips

- **2-second boot delay** in `main.py` allows interrupting boot loops via Thonny/REPL.
- **`resilience.blink_state()`** provides visual debugging: 'boot' (3 quick), 'wifi_wait' (slow), 'error' (rapid), 'running' (one long).
- **SD card lock** (`sd_card.get_lock()`) should be acquired for concurrent SD access, though currently only used in `get_info()`.
- **File cache invalidation**: Set `_dsk_files_cache = None` after any SD file modification to force rescan.
- **Config reload**: Call `app.dw_server.reload_config()` after config changes to hot-reload drives and serial map.
- **LED audit**: All SD card operations should trigger `activity_led.blink()` — 10 operations were missing and fixed in a past session.
- **Unit tests**: Exist in `tests/` directory, mock `machine` and `network` modules for host-side testing.

---

## Streaming Data Patterns

On the Pico W's ~192KB RAM, all network data transfers >4KB **must** use streaming. See [streaming-data.md](../rules/streaming-data.md) for the full rule set.

Three proven patterns exist in `web_server.py`:

| Pattern | Function | Technique |
|---------|----------|-----------|
| **Async Upload** | `upload_file_endpoint` | `request.stream.read()` → bounded buffer (depth 3) → background SD writer |
| **Raw Socket** | `_raw_http_get_stream` + `stream_remote_files` | Raw socket with byte-by-byte header scan + state-machine JSON parser |
| **Chunked Clone** | `remote_clone_endpoint` | Bulk 4KB sector fetches → immediate SD write → periodic GC + WDT feed |

**Key anti-patterns**: `urequests.get().content` (buffers entire response), `request.json` on large bodies, unbounded lists/bytearrays.

---

## Security & Exception Handling

This is an unauthenticated, LAN-only device. See [security-exceptions.md](../rules/security-exceptions.md) for the full rule set.

| Category | Key Pattern | Reference |
|----------|-------------|-----------|
| **Path Traversal** | `_sanitize_path()` / `_sanitize_rfm_path()` reject `..` segments | `web_server.py`, `drivewire.py` |
| **XSS Prevention** | `escHtml()` wraps all dynamic HTML; `textContent` for logs | `script.js` |
| **Input Validation** | Config whitelist, drive array length, `.dsk` extension check | `web_server.py`, `config.py` |
| **Exception Handling** | No bare `except:`; all errors logged via `resilience.log()` | All files |
| **Crash Recovery** | Top-level handler: log → blink → sleep 10s → `machine.reset()` | `main.py` |

---

## Sector Caching & Read-Ahead

Efficient sector access is critical for OS-9 performance on high-latency storage. See [sector-caching.md](../rules/sector-caching.md) for the full rule set.

| Pattern | Implementation | Benefit |
|---------|----------------|---------|
| **Write-Back** | `dirty_sectors` dict in `VirtualDrive` | Reduces flash wear; deferred writes |
| **LRU Read Cache** | `read_cache` dict (8 entries) | Lowers latency for repeated access |
| **Bulk Read-Ahead** | `RemoteDrive` fetches 8 sectors at once | Optimizes sequential read performance |
| **Zero-Copy** | `memoryview` for cache entries | Reduces RAM usage and overhead |

**Key anti-patterns**: Unbounded caches, synchronous `os.sync()` on every write, single-sector remote fetches.
