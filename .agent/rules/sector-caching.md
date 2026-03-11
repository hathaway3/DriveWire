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
   - **Note**: This 2KB cache (8 sectors * 256B) is intentionally kept below the 4KB streaming threshold defined in [streaming-data.md](streaming-data.md).

### 🥇 Priority of Truth (Layering)
To ensure absolute data integrity, the server must query layers in this strict order:
1. **Dirty Layer** (`dirty_sectors`): Highest priority. If data exists here, it has been modified by the guest but not yet flushed to media.
2. **Read Layer** (`read_cache`): Medium priority. Provides 0-latency hits for recent/sequential reads.
3. **Physical Media**: Lowest priority. Only accessed if the LSN is missing from both RAM layers.

## 🚀 Read-Ahead Strategy

1. **Bulk Remote Fetch**: 
   - When a cache miss occurs on a `RemoteDrive`, fetch up to 8 sequential sectors in a single HTTP request (`?count=8`).
   - Populating the cache with sequential sectors dramatically improves OS-9 multi-sector read performance.
2. **Adaptive Read-Ahead (Planned)**: 
   - Future implementations should consider the CoCo's access pattern (e.g., sequential vs. random).

### 🔄 Read-Ahead vs. Dirty Interaction
- **Non-Blocking Logic**: A read-ahead operation never flushes dirty sectors, and dirty sectors never block a read-ahead fetch.
- **Cache Eviction**: If a dirty sector is evicted from the `read_cache` (due to a large read-ahead batch filling the LRU slots), it **remains safely in the `dirty_sectors` list** and continues to be the "source of truth" for that LSN.
- **Consistency**: When a write occurs, the entry is updated in **both** `dirty_sectors` and `read_cache` to ensure the next sequential read reflects the modification.

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

## 🧠 RBF Caching & RbfParser (OS-9 Specific)

To ensure performance when dealing with OS-9 RBF file systems, follow these specialized rules.

### RbfParser Helper Usage
- **Statelessness**: The `RbfParser` must remain a stateless utility. Use `memoryview` where possible and return specific offsets.
- **Minimal Allocation**: Avoid creating new objects (lists/dicts) during parsing. Use generators or yield offsets.
- **LSN 0 Identification**: Use `RbfParser.is_lsn0(data)` to verify Identification Sectors before extracting `DD.DIR`.
- **Inode Detection**: Use `RbfParser.is_file_descriptor(data)` to identify OS-9 File Descriptors.

### Directory Cache Management
- **LSN 0 Persistence**: Once identified, LSN 0 should NOT be evicted unless the drive is swapped/flushed.
- **Breadcrumb Strategy**: Mark directory FD segments as "sticky" directory body sectors for high-priority caching.
- **Flush on Swap**: The `directory_cache` MUST be cleared along with `read_cache` and `dirty_sectors` whenever a drive is swapped or closed.
- **Isolation**: Each drive instance maintains its own `directory_cache`. No global directory caching.

### 📊 Observability
- **Stats**: Track entry counts and hit/miss rates for the directory cache in the drive's `stats` object.

---

## 📐 Reference Implementations

| Feature | Class | File |
|---------|-------|------|
| Write-Back Cache | `VirtualDrive` | `drivewire.py` |
| LRU Read Cache | `VirtualDrive`/`RemoteDrive` | `drivewire.py` |
| Bulk Read-Ahead | `RemoteDrive.read_sector` | `drivewire.py` |
| Cache inheritance | `DriveWireServer.swap_drive` | `drivewire.py` |
| RBF Parsing | `RbfParser` | `drivewire.py` |
