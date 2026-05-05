---
trigger: always_on
---
# Hot-Path Memory & Allocation Rules

The DriveWire UART protocol loop processes thousands of opcode transactions per second during OS-9 boot and sustained I/O. Every heap allocation in this path creates GC pressure that degrades CoCo serial latency.

## 🚫 Forbidden Patterns in Protocol Hot Path

These patterns **MUST NOT** appear inside `DriveWireServer.run()`, `read_bytes()`, or opcode handlers:

1. **One-shot `bytes()` for constants**: Never write `bytes([0])`, `bytes([243])`, or `bytes([E_UNIT])` inline. Pre-allocate all fixed response bytes as module-level constants.
2. **New `bytearray()` per call in `read_bytes()`**: The UART receive buffer must be a pre-allocated instance attribute (`self._rx_buf`), reused via `memoryview` slicing and `uart.readinto()`.
3. **`bytearray` concatenation for responses**: Never build a response with `resp += data`. Use `struct.pack_into()` on a pre-allocated buffer.
4. **f-string construction for filtered logs**: If `resilience.MIN_LOG_LEVEL` would discard the message, the f-string is still evaluated. Guard debug/info logs with a level check before building the string.
5. **`import` statements inside loops**: MicroPython caches modules but still performs a `sys.modules` dict lookup on every `import` statement. Move all imports to the top of the file.

## ✅ Required Patterns

1. **Pre-allocated response constants** at module level:
   ```python
   _RESP_OK = bytes([0])
   _RESP_CRC = bytes([243])
   _PAD_256 = bytes(256)
   ```

2. **Reusable UART receive buffer** in `DriveWireServer.__init__`:
   ```python
   self._rx_buf = bytearray(260)
   self._rx_view = memoryview(self._rx_buf)
   ```

3. **`readinto()` instead of `read()`** for UART and file I/O:
   ```python
   n = self.uart.readinto(self._rx_view[pos:count])
   ```

4. **`struct.pack_into()`** for building multi-field responses:
   ```python
   struct.pack_into(">H", self._read_resp, 1, checksum)
   ```

5. **`collections.deque(maxlen=N)`** for bounded FIFO buffers (log buffer, terminal buffer) instead of `list.pop(0)` which is O(n).

6. **`@micropython.native`** decorator on tight numeric loops like `checksum()`.

## 📏 Bounded Growth Rules

| Data Structure | Location | Max Size | Enforcement |
|---------------|----------|----------|-------------|
| `dir_lsns` set | VirtualDrive / RemoteDrive | 256 entries (~7KB) | Check `len()` before `.add()` |
| `directory_cache` | VirtualDrive / RemoteDrive | `MAX_DIR_CACHE_ENTRIES` (32) | Evict oldest, protect LSN 0 |
| `read_cache` | VirtualDrive / RemoteDrive | `MAX_READ_CACHE_ENTRIES` (8) | Evict oldest |
| `dirty_sectors` | VirtualDrive | `MAX_DIRTY_CACHE_ENTRIES` (8) | Auto-flush at limit |
| `log_buffer` | DriveWireServer | `MAX_LOG_ENTRIES` (20) | Use deque with maxlen |
| `terminal_buffer` | DriveWireServer | `MAX_TERMINAL_BUFFER_SIZE` (512) | Use deque with maxlen |
| `channels[n]` | DriveWireServer | `MAX_CHANNEL_BUFFER_SIZE` (256) | Truncate on overflow |

## ⚠️ Known Pitfalls

1. **`RemoteDrive._update_dir_awareness()`** must NOT set `self.last_error` unconditionally. Only error-return paths should modify `last_error`.
2. **`write_sector()` double-caching**: Storing data in both `dirty_sectors` and `read_cache` is redundant since dirty is checked first. Consider skipping the `read_cache` update for writes to reduce eviction churn.
3. **`resilience.log()` file I/O**: Each log call performs `os.stat()` + `open()` + `write()` + `close()`. During high-throughput operation, batch log writes or use an in-RAM buffer flushed periodically.
4. **Status endpoint deep copies**: `/api/status` should avoid `list(buffer)` copies of log and terminal buffers. Pass the original references to the JSON serializer.

## 📐 Reference

| Pattern | File | Function/Location |
|---------|------|-------------------|
| UART receive buffer | `drivewire.py` | `DriveWireServer.read_bytes()` |
| Response constants | `drivewire.py` | Module-level `_RESP_*` |
| Checksum native | `drivewire.py` | `DriveWireServer.checksum()` |
| Log batching | `resilience.py` | `log()` |
| Deque buffers | `drivewire.py` | `DriveWireServer.__init__()` |
