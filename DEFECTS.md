# DriveWire — Defect Tracker

A triaged list of known defects across platform implementations. Work items are
grouped by status and tagged with the affected platform(s), severity, and
suspected location.

**Platforms:** `c/` · `micropython/` · `swift/` · `objc/` · `delphi/`

**Severity:** 🔴 Critical (crash / data loss / unusable) · 🟠 Major (feature broken)
· 🟡 Minor (cosmetic / edge case)

---

## Open

| # | Severity | Platform | Summary | Symptom / Repro | Suspected location |
|---|----------|----------|---------|-----------------|--------------------|
| 1 | 🟠 Major | micropython | Web Statistics screen: several drive metrics never update | Some metrics update live, others stay frozen at 0/`--` | `web_server.py:_build_drive_stats` ↔ `www/static/script.js:renderDriveStats` |
| 2 | 🔴 Critical | micropython | Remote disk images unusable from client (I/O errors) | Drive mounts OK, but client reads fail with I/O errors | `drivewire.py:RemoteDrive.read_sector` · `resilience.open_remote_stream` |
| 3 | 🔴 Critical | micropython | Clone remote → local disk broken (regression) | Clone fails; worked in earlier versions | `web_server.py:remote_clone_endpoint/_do_clone` |
| 4 | 🟠 Major | micropython | Server-mode serial ports never listen; backend ignores `mode` | Config saves `server` channels but clients can't connect to any | `drivewire.py:init_channel` · dead `tcp_accept_handler` |
| 5 | 🔴 Critical | micropython | Hot config reload loses unflushed writes & leaks file handles | After Save/reload, pending sector writes vanish; old drives not closed | `drivewire.py:reload_config` → `init_drives` |
| 6 | 🔴 Critical | micropython | Writes to a read-only-opened drive are ACKed then silently dropped | CoCo write "succeeds" but data never persists | `drivewire.py:VirtualDrive._open` / `write_sector` / `flush` |
| 7 | 🟡 Minor | micropython | First request after boot can be dropped (`consecutive_opcodes` unbound) | Intermittent lost first transaction + ~1s stall | `drivewire.py:run` (~line 543/855) |
| 8 | 🟡 Minor | micropython | Out-of-range serial channel index throws IndexError | Client requesting channel ≥ 32 causes protocol error + 1s stall | `drivewire.py` OP_SERREADM / `channels[chan]` accesses |
| 9 | 🟡 Minor | micropython | Brittle hand-rolled JSON parser for remote `/info` | Disk names containing JSON metacharacters desync parsing → disks dropped / clone size lookup fails | `web_server.py:stream_remote_info` |
| 10 | 🟡 Minor | micropython | SD pin/mount config changes saved but never applied without reboot | Changing SD SPI pins / mount point has no effect until power cycle | `web_server.py:config_endpoint` · `sd_card.init_sd` (boot-only) |
| 11 | 🟡 Minor | micropython | Upload with missing/zero Content-Length silently writes empty file + reports OK | 0-byte `.dsk` created, `{status: ok}` returned | `web_server.py:upload_file_endpoint` (~line 659/713) |
| 12 | 🟡 Trivial | micropython | Drive-count bound hardcoded (`drive_num < 4`) instead of `NUM_DRIVES` | Latent divergence if drive count changes; minor double config save | `web_server.py:_do_clone` (~line 1144/1151) |

## In Progress

| # | Severity | Platform | Summary | Notes |
|---|----------|----------|---------|-------|
| _ | _ | _ | _ | _ |

## Fixed

| # | Platform | Summary | Fixed in |
|---|----------|---------|----------|
| _ | _ | _ | _ |

---

### #1 — Web Statistics screen: several drive metrics never update

- **Severity:** 🟠 Major
- **Platform(s):** micropython
- **Symptom:** On the web front end's statistics view, some drive metrics update
  live while others stay stuck at `0` / `--`.
- **Steps to reproduce:** Mount a drive, generate read/write activity, open the
  Drives/Status tab on the web UI. READ HITS, READ MISSES, HIT RATE, DIR CACHE
  SIZE, and TOTAL WRITES never move; DIR cache hits/misses, latency, dirty
  sectors, and filename update normally.
- **Root cause:** Field-name contract mismatch between the JSON producer and
  consumer. `_build_drive_stats()` emits `reads` / `writes` and omits
  `read_misses` / `dir_cache_size`, but `renderDriveStats()` reads `read_hits`,
  `read_misses`, `write_count`, and `dir_cache_size`. The frontend's `|| 0`
  fallbacks silently mask the missing fields, so those tiles render a constant 0.
- **Suspected file(s):**
  - `micropython/web_server.py` — `_build_drive_stats()` (~line 298)
  - `micropython/www/static/script.js` — `renderDriveStats()` (~line 790)
  - Note: `www/static/script.js.gz` is a pre-compressed copy served by
    `static()` when present — it must be regenerated after any `script.js` fix
    or the browser keeps loading stale JS.
- **Open question:** decide the canonical names. The drive model in
  `drivewire.py` tracks `reads` (total), `cache_hits`, `dir_cache_*`. The UI
  labels imply `read_hits` vs `read_misses` (a cache hit/miss split) — confirm
  whether the intended metric is total reads or a cache hit/miss breakdown
  before aligning the names.

### #2 — Remote disk images unusable from the DriveWire client (I/O errors)

- **Severity:** 🔴 Critical
- **Platform(s):** micropython
- **Symptom:** The remote disk image mounts successfully, but as soon as the
  CoCo/client tries to read it, the client reports I/O errors.
- **Steps to reproduce:** Mount a remote drive (`REMOTE:<url>`), then attempt to
  access it from the client (e.g. `DIR`/`LOAD`). Client returns I/O errors.
- **Suspected area:** `drivewire.py:RemoteDrive.read_sector` (~line 316). It
  builds `"{base_url}/sectors/{base_name}/{lsn}?count=8"` and streams via
  `resilience.open_remote_stream(url)`. On failure it sets `last_error =
  E_NOTRDY` and returns `None`, which surfaces to the client as an I/O error.
  Candidate causes to check: URL construction (`base_name` derived from
  `filename.split(':')[-1].split('/')[-1]`; `base_url` strips `/disk/`), the
  remote `/sectors/` endpoint contract, and short-read handling in the
  `readinto` loop (a partial sector `break`s and yields `None`).
- **Likely related:** commit `19787c3` ("fix remote drive url resolution and
  implement sequential sector cloning") reworked this exact path — treat as a
  prime regression suspect.
- **Notes:** Confirm whether the prime read (`read_sector(0)` on construction)
  succeeds while later sectors fail — that would isolate URL vs. sector-range
  handling.
- **Investigation (2026-06-14):** The client-side URL construction is **correct**
  and matches the intended contract — a drive mounted as
  `http://<host>:6809/disk/<name>.dsk` (built by `script.js:257`) fetches from
  `http://<host>:6809/sectors/<name>.dsk/<lsn>?count=8`, verified by
  `test_remote_drive_url_resolution`. No client-side bug was found that would
  break *all* reads, so the remaining root cause is most likely **server-side or
  a Host/contract detail** against the port-6809 server.
- **Done so far (branch `fix/remote-disk-io`):**
  - `ea52b4e` — read failures now report `E$Read` + increment error stats
    (were silently mapped to `E$Unit`).
  - `23e3c38` — `open_remote_stream` now sends an RFC-correct Host header (with
    port) **and logs the actual non-2xx status**, so the failure is diagnosable
    from the on-device system log. The Host-header fix is also a candidate root
    cause if the server validates Host.
- **Needed to close:** reproduce on-device and read the system-log line, or share
  `curl -i 'http://<host>:6809/sectors/<name>.dsk/0?count=8'` output, to confirm
  whether the server returns 2xx + raw sector bytes.

### #3 — Clone remote disk to local is broken (regression)

- **Severity:** 🔴 Critical
- **Platform(s):** micropython
- **Symptom:** Cloning a remote disk image to local storage fails. Previously
  worked without issue in earlier versions.
- **Steps to reproduce:** From the web UI, use "CLONE TO LOCAL" on a remote
  drive (or `POST /api/remote/clone`). Operation errors out.
- **Suspected area:** `web_server.py:remote_clone_endpoint` → `_do_clone()`
  (~lines 1010–1176). The clone now streams sequential chunks of
  `CHUNK_SECTORS = 64` via `"{remote_url}/sectors/{disk_name}/{lsn}?count={count}"`
  and `resilience.open_remote_stream(url, addr=remote_addr)`, raising
  "Stream ended early at LSN …" on short reads. Check the count/chunk contract
  against the remote server and the early-termination logic.
- **Likely related:** Same commit `19787c3` introduced the "sequential sector
  cloning" rewrite — strong regression suspect. Shares the `/sectors/` streaming
  path with defect #2, so the two may have a common root cause.
- **Next step:** `git show 19787c3` to diff against the last known-good clone
  implementation.
- **Investigation (2026-06-14):** Diffed `19787c3`. The rewrite replaced one
  persistent stream (`/sectors/<name>/0?count=<total>`) with a **new socket per
  64-sector chunk** (`/sectors/<name>/<lsn>?count=64`) that hard-fails with
  "Stream ended early" on any short read. Prime regression suspects: (a) rapid
  open/close of many sockets exhausting LwIP PCBs, or (b) the server returning a
  different byte count than `count*256`. Both require observing the live server.
  The non-2xx logging added in `23e3c38` also covers this path (clone uses the
  same `open_remote_stream`).
- **Needed to close:** same diagnostic as #2 — on-device system log during a
  clone, or a manual `curl -i` of a `/sectors/...?count=64` request.

### #4 — Server-mode serial ports never listen (backend ignores `mode`)

- **Severity:** 🟠 Major (functional gap + design concern)
- **Platform(s):** micropython
- **Symptom:** Serial-map channels configured as `server` are saved and shown in
  the UI, but no listening socket is ever opened, so clients cannot connect to
  any server-side port.
- **Steps to reproduce:** In the web UI serial map, add a channel with
  MODE = SERVER and a port, save, then attempt to connect from an external
  client. Connection fails (nothing is listening).
- **Root cause:** Backend never implements server/listen mode.
  - `drivewire.py:init_channel` (~line 466) reads `serial_map[chan]` but only
    ever calls `asyncio.open_connection(host, port)` — an *outgoing* (client)
    connection. It never inspects `mapping.get('mode')`.
  - `drivewire.py:tcp_accept_handler` (~line 886) exists to handle *incoming*
    connections but is **dead code** — never referenced; there is no
    `asyncio.start_server` / listening socket anywhere in `drivewire.py`.
  - The frontend already persists `mode` (`client`/`server`) per row
    (`www/static/script.js:addSerialMapRow`, ~line 874), so the config side is
    fine; only the backend is missing.
- **Design considerations (raised by reporter):**
  - Pico 2W lwIP has a small fixed pool of TCP PCBs. Opening 16 listeners plus
    the web server (:80) plus remote-drive streams risks exhausting socket
    resources. Fix should open listeners **only** for channels explicitly set to
    `server`, and consider a hard cap / lazy open.
  - Confirm desired lifecycle: open listeners at config-apply time and keep them
    monitoring for remote connections; close/reopen cleanly on config change.
- **Suspected file(s):**
  - `micropython/drivewire.py` — `init_channel`, `tcp_accept_handler`, server
    lifecycle/teardown
  - `micropython/www/static/script.js` — `addSerialMapRow` (schema reference; no
    change expected)

### #5 — Hot config reload loses unflushed writes & leaks file handles

- **Severity:** 🔴 Critical (data loss)
- **Platform(s):** micropython
- **Symptom:** Applying a config change while drives are mounted can drop
  buffered (dirty) sector writes and leak open file handles.
- **Root cause:** `DriveWireServer.reload_config()` (`drivewire.py:897`) calls
  `init_drives()`, which does `self.drives[i] = VirtualDrive(path)` /
  `RemoteDrive(path)` and **overwrites the existing drive object without first
  calling `await old.close()`** (which is what flushes `dirty_sectors`). The old
  file handle is never closed, and any unflushed writes are lost.
- **Additional issues in the same path:**
  - Drives present in the old config but absent/`None` in the new one are left
    mounted (stale), since `init_drives` only assigns indices that have a path.
  - `init_uart()` constructs a new `UART(0, …)` without deinitializing the
    previous instance.
- **Steps to reproduce:** Mount a drive, perform writes (so `dirty_sectors` is
  non-empty), then Save config / trigger reload before the 60s periodic flush.
  Pending writes are lost.
- **Suspected file(s):** `micropython/drivewire.py` — `reload_config`,
  `init_drives`, `swap_drive` (note: `swap_drive` *does* close the old drive;
  `init_drives` should follow the same discipline).

### #6 — Writes to a read-only-opened drive are ACKed, then silently dropped

- **Severity:** 🔴 Critical (silent data loss / integrity)
- **Platform(s):** micropython
- **Symptom:** When a disk image opens read-only, the CoCo still receives a
  successful write acknowledgement, but the data never persists.
- **Root cause:** `VirtualDrive._open` (`drivewire.py:165`) falls back to
  `open(filename, "rb")` when `"r+b"` fails (read-only FS, locked file, etc.).
  `write_sector` (line 249) only checks `if not self.file` — a read-only handle
  is truthy — so it stores the sector in `dirty_sectors` and returns `True`,
  which the protocol layer turns into `_RESP_OK`. The later `flush()` then fails
  with `OSError` on the read-only handle, logs at level 3, and discards the data.
- **Fix direction:** Track a writable/`read_only` flag on the drive; have
  `write_sector` return `False` with `last_error = E_WP` when not writable so the
  CoCo gets a proper write-protect error instead of a false success.
- **Suspected file(s):** `micropython/drivewire.py` — `VirtualDrive._open`,
  `write_sector`, `flush`.

### #7 — First request after boot can be dropped (`consecutive_opcodes` unbound)

- **Severity:** 🟡 Minor (intermittent, self-clearing)
- **Platform(s):** micropython
- **Symptom:** Occasionally the first serial transaction after start is lost and
  followed by a ~1s stall; subsequent requests are fine.
- **Root cause:** In `DriveWireServer.run()` (`drivewire.py:539`), `loop_counter`
  is initialized before the loop but `consecutive_opcodes` is only set inside the
  `if not self.uart.any():` idle branch (line 550). If UART data is already
  present on the very first loop iteration, execution reaches
  `consecutive_opcodes += 1` (line 855) before the name is ever bound →
  `NameError`, caught by the generic `except` (logged as "Protocol error",
  `sleep(1)`). After the handler sets it to 0, the bug cannot recur this run.
- **Fix direction:** Initialize `consecutive_opcodes = 0` next to
  `loop_counter = 0` before the loop.
- **Suspected file(s):** `micropython/drivewire.py` — `run()`.

### #8 — Out-of-range serial channel index throws IndexError

- **Severity:** 🟡 Minor (robustness / DoS on malformed request)
- **Platform(s):** micropython
- **Symptom:** A client request referencing a serial channel ≥ `NUM_CHANNELS`
  (32) raises `IndexError`, caught as a generic "Protocol error" with a 1s stall;
  the transaction is lost.
- **Root cause:** `self.channels` has `NUM_CHANNELS` (32) entries, but several
  handlers index it with a client-supplied channel byte (0–255) without a bounds
  check. Confirmed at `OP_SERREADM` (`drivewire.py:675`,
  `len(self.channels[chan])`). `init_channel`/`OP_SERTERM` *do* guard with
  `chan < len(self.channels)`; `tcp_reader_task` also does `channels[chan]` and
  would fault if `init_channel` opened a TCP connection for an out-of-range
  channel (the TCP setup itself is not channel-bounded).
- **Fix direction:** Validate `chan < NUM_CHANNELS` consistently at every
  client-channel entry point before indexing `self.channels` / opening TCP.
- **Suspected file(s):** `micropython/drivewire.py` — `OP_SERREADM` path,
  `init_channel`, `tcp_reader_task`.

### #9 — Brittle hand-rolled JSON parser for remote `/info`

- **Severity:** 🟡 Minor (robustness)
- **Platform(s):** micropython
- **Symptom:** Remote disk discovery / clone sizing can drop disks or fail to
  find a disk when a disk name or path contains JSON metacharacters.
- **Root cause:** `stream_remote_info()` (`web_server.py:821`) counts `{` `}`
  `[` `]` and commas to find object boundaries **without tracking string
  context**, so any of those characters appearing inside a string value (e.g. a
  disk name like `my[disk].dsk`) desyncs `depth` and corrupts parsing.
  `stream_remote_files()` *does* handle string/escape state — `stream_remote_info`
  should do the same (or use incremental `json` parsing).
- **Impact:** Affects `/api/remote/files`, remote test, and clone size lookup
  (which feeds defect #3).
- **Suspected file(s):** `micropython/web_server.py` — `stream_remote_info`.

### #10 — SD pin/mount config changes are saved but never applied without reboot

- **Severity:** 🟡 Minor (config gap)
- **Platform(s):** micropython
- **Symptom:** Editing SD SPI pins or the mount point in the web UI persists to
  config but has no effect until a power cycle; can leave drives pointing at an
  unmounted `/sd`.
- **Root cause:** `sd_card.init_sd()` is only called once at boot
  (`boot.py:64`). `DriveWireServer.reload_config()` re-inits drives and UART but
  never deinits/remounts the SD card, and the config POST whitelist accepts the
  `sd_*` keys without triggering a remount.
- **Fix direction:** On SD-related config change, call `sd_card.deinit_sd()` then
  `init_sd()` (guarding against in-flight uploads), or surface a "reboot
  required" hint in the UI.
- **Suspected file(s):** `micropython/web_server.py` — `config_endpoint`;
  `micropython/sd_card.py` — `init_sd`/`deinit_sd`.

### #11 — Upload with missing/zero Content-Length silently writes an empty file

- **Severity:** 🟡 Minor (edge case)
- **Platform(s):** micropython
- **Symptom:** A POST to `/api/files/upload` without a (valid) `Content-Length`
  produces a 0-byte `.dsk` and returns `{'status': 'ok'}`.
- **Root cause:** `upload_file_endpoint` (`web_server.py:659`) sets
  `total_size = int(content_length) if content_length else 0`; the receive loop
  is `while remaining > 0`, so with `total_size == 0` it never reads the body and
  reports success. Browsers always send Content-Length, so this is edge-case, but
  it should reject the request or read until stream EOF instead.
- **Suspected file(s):** `micropython/web_server.py` — `upload_file_endpoint`.

### #12 — Drive-count bound hardcoded instead of `NUM_DRIVES`

- **Severity:** 🟡 Trivial (maintainability)
- **Platform(s):** micropython
- **Symptom:** No live failure today; latent divergence risk.
- **Details:** Clone hot-swap uses `if 0 <= drive_num < 4` literal
  (`web_server.py:1144`) rather than `drivewire.NUM_DRIVES`. Also `_do_clone`
  calls `config.set('drives', drives)` (which already saves) immediately followed
  by a redundant `config.save()` (line 1151–1152).
- **Suspected file(s):** `micropython/web_server.py` — `_do_clone`.

---

## Feature Gaps / Missing Functionality

Tracked separately from defects: functionality that is referenced, partially
implemented, or implied by the protocol/UI but not actually delivered.

| # | Area | Gap | Where |
|---|------|-----|-------|
| F1 | Printing | CoCo print jobs are buffered then discarded — never sent anywhere | `drivewire.py` OP_PRINT / OP_PRINTFLUSH |
| F2 | RFM (Remote File Manager) | Only OPEN/CHGDIR/SEEK/READ/CLOSE handled; CREATE/MAKDIR/DELETE/WRITE/READLN/WRITLN/GETSTT/SETSTT are no-ops (no response → client may hang) | `drivewire.py` OP_RFM dispatch (~742–824) |
| F3 | Remote drives | Network-mounted drives are read-only (`write_sector` → E$WP) | `drivewire.py:RemoteDrive.write_sector` |
| F4 | Serial server mode | Inbound/listen serial ports not implemented (also tracked as bug #4) | `drivewire.py:init_channel` |
| F5 | CoCo debugging | `OP_WIREBUG` (0x42) and `OP_BKPT` (0x21) opcodes defined but unhandled | `drivewire.py:run` dispatch |

### F1 — Printing is captured but never output

- `OP_PRINT` appends bytes to `print_buffer` (capped at 4096), and
  `OP_PRINTFLUSH` simply `clear()`s it. There is no code path that writes the
  buffer to a file, serial printer, or network spooler — so all CoCo print output
  is silently dropped. Either implement an output sink or document as unsupported.

### F2 — RFM is read-only and incomplete (and can hang the client)

- The RFM sub-op constants are all defined (`OP_RFM_CREATE` … `OP_RFM_SETSTT`),
  but the dispatch in `run()` only implements OPEN, CHGDIR, SEEK, READ, and CLOSE.
  Unhandled sub-ops (CREATE, MAKDIR, DELETE, WRITE, READLN, WRITLN, GETSTT,
  SETSTT) fall through and **write no response**, so a CoCo issuing them will
  wait and time out. Beyond the missing features, the no-response behavior is a
  robustness issue worth a default error reply even where unimplemented.

### F3 — Remote drives are read-only

- `RemoteDrive.write_sector` always returns `E_WP`. Writing back to a
  network-hosted image is unsupported. May be intentional; tracked so the
  limitation is explicit (and so the UI can label remote drives WP).

### F4 — Serial server (listen) mode

- Cross-reference: see defect **#4**. The `server` mode exists in config/UI but no
  listening socket is ever opened.

### F5 — WireBug / breakpoint debugging opcodes

- `OP_WIREBUG` and `OP_BKPT` are defined but have no handler in the opcode
  dispatch, so CoCo-side debugging over DriveWire is unsupported. Likely by
  design; tracked for completeness.

---

### Defect detail template

```
#N — <one-line summary>
- Severity:
- Platform(s):
- Symptom:
- Steps to reproduce:
- Expected:
- Actual:
- Suspected file(s):
- Notes:
```
