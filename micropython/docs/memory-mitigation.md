# Memory Resilience & Mitigation Guide

On the Raspberry Pi Pico W, the ~192KB heap is shared between the DriveWire protocol, TCP networking, and the Web UI. Under high stress, memory exhaustion (OOM) and heap fragmentation are the primary risks.

## 📊 Estimated Memory Footprint

| Component | RAM Usage (Est.) | Multiplier | Total |
| :--- | :--- | :--- | :--- |
| Directory Cache | 8KB / drive | 4 drives | 32KB |
| Read Cache | 2KB / drive | 4 drives | 8KB |
| Internal Buffers | Pre-allocated | Server | 1KB |
| TCP Channels | 0.25KB / channel | 32 channels | 8KB |
| Web UI (Microdot) | Base overhead + state | 1 server | ~25KB |
| UI Polling Task | ~2KB / connection | ~3 clients | 6KB |
| Cloning / Upload | 12KB (chunk buffer) | 1 task | 12KB |
| System Overhead | MicroPython VM + WiFi | Shared | ~65KB |
| **Pessimistic Peak** | | | **~175KB** |

**Remaining Safety Buffer**: ~20KB (Critical for preventing fragmentation-induced OOM).

## ⚠️ Potential Break Points

1. **Unbounded Write-Back Cache**: If multiple drives are written to heavily without flushing, the `dirty_sectors` dict can consume all remaining RAM.
2. **Stack Overflow / Deep Recursion**: Even when using generators, recursive directory walks (`yield from`) consume stack space. On the Pico, this is hardware-limited.
3. **Ghost Object Accumulation**: Unclosed HTTP connections (from browser tabs being closed or network drops) can leave dangling sockets and buffers.

## 🛡️ Mitigation Strategies

### 1. Hard-Bounded Write-Back Cache (Implemented)

- **Auto-Flush**: In `VirtualDrive.write_sector`, the cache is automatically flushed to the SD card if it reaches **16 sectors (4KB)**. This prevents any one drive from monopolizing memory.

### 2. Adaptive Garbage Collection

- **Strategic Collection**: `gc.collect()` is triggered manually before memory-intensive operations (mounting a drive, starting a clone).
- **Periodic Collection**: The streaming rules mandate GC every 64-128KB of data processed.

### 3. Connection & Client Management

- **Polling Debounce**: The Web UI uses a 2-second polling interval and cancels previous requests if they time out, preventing "stacked" requests in memory.
- **Resource Timeouts**: Sockets are wrapped in `finally` blocks to ensure they close even on unexpected client disconnection.

### 4. Generator-Based Pipelines & Streaming

- **Recursive Bounding**: The directory scanner uses `yield from` to walk the SD card but is strictly capped at `max_depth=3` to prevent MicroPython stack overflow.
- **JSON Streaming**: Large API responses (like `/api/files/info`) are streamed as individual chunks, preventing the Pico from trying to buffer the entire response in RAM.

### 5. Pre-allocation & Throttling

- **Internal Buffers**: High-frequency protocol buffers (`_resp_buf`, `_header_buf`) are pre-allocated once at startup to prevent heap fragmentation during rapid I/O.
- **Throttled I/O**: Periodic checks (like log file size monitoring) are throttled (e.g., every 20 calls) to reduce SD card latency and CPU spikes.

## 🛠️ Mitigation Checklist for New Features

- [ ] Does this feature buffer more than 4KB? (If yes, use a stream).
- [ ] Does it use a dictionary or list that grows with activity? (If yes, implement a limit).
- [ ] Are buffers pre-allocated or created per-request? (Prefer pre-allocation).
- [ ] Is there a `try...finally` block for resource cleanup?
