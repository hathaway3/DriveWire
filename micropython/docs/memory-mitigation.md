# Memory Resilience & Mitigation Guide

On the Raspberry Pi Pico W, the ~192KB heap is shared between the DriveWire protocol, TCP networking, and the Web UI. Under high stress, memory exhaustion (OOM) and heap fragmentation are the primary risks.

## 📊 Estimated Memory Footprint

| Component | RAM Usage (Est.) | Multiplier | Total |
|-----------|-----------------|------------|-------|
| Read Cache | 2KB / drive | 4 drives | 8KB |
| Write-Back Cache | ~4KB (at 16-sector limit) | 4 drives | 16KB |
| TCP Channels | 0.25KB / channel | 32 channels | 8KB |
| Web UI (Microdot) | Base overhead + state | 1 server | ~25KB |
| UI Polling Task | ~2KB / connection | ~3 clients | 6KB |
| Cloning / Upload | 12KB (chunk buffer) | 1 task | 12KB |
| System Overhead | MicroPython VM + WiFi | Shared | ~65KB |
| **Pessimistic Peak** | | | **~140KB** |

**Remaining Safety Buffer**: ~52KB (Critical for preventing fragmentation-induced OOM).

## ⚠️ Potential Break Points

1. **Unbounded Write-Back Cache**: If multiple drives are written to heavily without flushing, the `dirty_sectors` dict can consume all remaining RAM.
2. **Heap Fragmentation**: Rapid allocation/deallocation of 4KB chunks during cloning, combined with UI polling, can "hole" the heap, preventing the allocation of larger objects.
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

### 4. Backpressure in Pipelines
- **Bounded Buffers**: The Async Upload Pipeline uses a max depth of 3 chunks. If the SD writer falls behind, the network reader waits, preventing RAM buildup.

## 🛠️ Mitigation Checklist for New Features

- [ ] Does this feature buffer more than 4KB? (If yes, use a stream).
- [ ] Does it use a dictionary or list that grows with activity? (If yes, implement a limit).
- [ ] Are buffers pre-allocated or created per-request? (Prefer pre-allocation).
- [ ] Is there a `try...finally` block for resource cleanup?
