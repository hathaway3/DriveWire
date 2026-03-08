---
trigger: always_on
---
# Sector Caching & Read-Ahead Rules

On the Pico W, disk and network latency are high but RAM is scarce. Efficient sector caching and read-ahead are essential for CoCo performance.

## 💾 Cache Types

1. **Write-Back Cache (Local Drives)**: 
   - Use a `dirty_sectors` dict to buffer writes to the SD card.
   - **Benefit**: Reduces flash wear and protocol latency.
   - **Requirement**: Must be flushed via `flush()` or `close()`.

2. **Read Cache (All Drives)**: 
   - Use an LRU (Least Recently Used) cache for sector data.
   - **Limit**: `MAX_READ_CACHE_ENTRIES` (default 8) to stay within RAM bounds.
   - **Pattern**: Check `dirty_sectors` first, then `read_cache`, then disk/network.

## 🚀 Read-Ahead Strategy

1. **Bulk Remote Fetch**: 
   - When a cache miss occurs on a `RemoteDrive`, fetch up to 8 sequential sectors in a single HTTP request (`?count=8`).
   - Populating the cache with sequential sectors dramatically improves OS-9 multi-sector read performance.
2. **Adaptive Read-Ahead (Planned)**: 
   - Future implementations should consider the CoCo's access pattern (e.g., sequential vs. random).

## 🚰 Memory Efficiency

1. **Pre-allocate Buffers**: Use a single `bytearray(256)` for sector transfers where possible instead of creating new ones.
2. **Zero-Copy**: Use `memoryview` for slicing or passing sector data fragments without copying memory.
3. **Cache Eviction**: Always enforce the cache limit. In Python dicts, use `pop(next(iter(cache)))` for a simple FIFO/LRU eviction of the oldest entry.

## 🧹 Consistency & Safety

1. **Dirty Consistency**: When a sector is written, update the `read_cache` immediately so subsequent reads are consistent before the next flush.
2. **WDT Feeding**: Loops processing bulk read-ahead or flushing large dirty buffers **MUST** feed the watchdog timer.
3. **Hot-Swap**: When swapping a drive, the new drive object should ideally inherit the `read_cache` of the old one if it's the same file (seamless transition).

## 🚫 Anti-Patterns

1. **Unbounded Caches**: Never let a cache grow without a fixed entry limit.
2. **Immediate Sync on Every Write**: Avoid calling `os.sync()` after every 256-byte write; use the write-back cache instead.
3. **Ignoring Read-Ahead**: Fetching only one sector at a time from a remote server is too slow for the CoCo's expectations.

## 📐 Reference Implementations

| Feature | Class | File |
|---------|-------|------|
| Write-Back Cache | `VirtualDrive` | `drivewire.py` |
| LRU Read Cache | `VirtualDrive`/`RemoteDrive` | `drivewire.py` |
| Bulk Read-Ahead | `RemoteDrive.read_sector` | `drivewire.py` |
| Cache inheritance | `DriveWireServer.swap_drive` | `drivewire.py` |
