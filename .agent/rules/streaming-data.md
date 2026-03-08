---
trigger: always_on
---
# Streaming Data & Memory Safety Rules

On the Pico W (~192KB RAM), buffering entire network payloads causes memory exhaustion. All data transfer features **MUST** use lightweight streaming.

## 📏 When to Stream vs. Buffer

1. **Stream Required**: Any network data exceeding **4KB** total (uploads, downloads, API responses, remote file lists).
2. **Buffer Acceptable**: Small, predictable responses under 4KB (e.g., JSON config, status polls). Must be short-lived.

## 📦 Chunk Size Guidelines

1. **SD Card I/O**: Use **4KB chunks** (SD-aligned) for reads and writes. This balances network efficiency with RAM usage.
2. **Network Reads**: Match chunk size to SD write size (4096 bytes) to avoid intermediate buffering.
3. **JSON Parsing**: For large responses, use character-by-character state-machine parsing (see `stream_remote_files` for the reference pattern).

## 🚰 Backpressure & Flow Control

1. **Throttle Producers**: When a network reader outpaces an SD writer, use a bounded buffer (max depth **3 chunks**) and suspend network reads until the writer catches up.
2. **Yield to Scheduler**: Insert `await asyncio.sleep(0)` after each chunk in background tasks to prevent starving the DriveWire protocol loop or web server.
3. **Progress Tracking**: Expose a polling endpoint (e.g., `/api/.../status`) so the UI can track real progress without blocking the pipeline.

## 🧹 Memory Management During Streaming

1. **Periodic GC**: Call `gc.collect()` every **64-128KB** of data processed (e.g., every 16-32 chunks at 4KB each).
2. **Feed the WDT**: Call `resilience.feed_wdt()` after every chunk write. Long transfers will trigger a watchdog reset otherwise.
3. **Pre-allocate Buffers**: For zero-fill operations (e.g., blank disk creation), reuse a single `bytearray(4096)` instead of allocating new ones per chunk.
4. **Resource Cleanup**: Close sockets and files in `finally` blocks. Never leave a raw socket open after an error path.

## 🚫 Anti-Patterns

1. **`urequests.get().content`**: Buffers entire response into RAM. Use `_raw_http_get_stream()` for responses larger than 4KB.
2. **`request.json` on large POST bodies**: Parses entire body into a dict. For file uploads, use `request.stream.read(chunk_size)` with the `X-Filename` header convention.
3. **Unbounded lists or bytearrays**: Any buffer that grows without a cap will eventually exhaust RAM. Always enforce a maximum size.
4. **Blocking I/O without WDT feeding**: Any loop that waits for network or SD I/O must feed the watchdog timer.

## 📐 Reference Implementations

| Pattern | File | Lines | Use Case |
|---------|------|-------|----------|
| Async Upload Pipeline | `web_server.py` | `upload_file_endpoint` | Browser → Pico file upload with backpressure |
| Raw Socket Streaming | `web_server.py` | `_raw_http_get_stream` + `stream_remote_files` | Parsing large JSON lists from remote servers |
| Chunked Clone Download | `web_server.py` | `remote_clone_endpoint` | Sector-by-sector disk image cloning |
