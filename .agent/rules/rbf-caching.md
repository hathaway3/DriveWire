# RBF Caching & RbfParser Rules

To ensure performance and correctness when dealing with OS-9 RBF file systems, follow these rules regarding the `RbfParser` and the directory cache.

## 🧠 RbfParser Helper Usage

1.  **Statelessness**: The `RbfParser` must remain a stateless utility. It should take a 256-byte sector (via `memoryview` where possible) and return specific offsets or parsed segments.
2.  **Minimal Allocation**: Avoid creating new objects (like lists or dicts) during parsing if possible. Use generators or yield segment offsets to keep memory pressure low.
3.  **LSN 0 Identification**: Always use `RbfParser.is_lsn0(data)` to verify if a sector is a valid Identification Sector before extracting `DD.DIR`.
4.  **Inode Detection**: `RbfParser.is_file_descriptor(data)` should be used to identify if a sector is an OS-9 File Descriptor (Inode).

## 💾 Directory Cache Management

1.  **LSN 0 Persistence**: Once LSN 0 is identified and cached, it should NOT be evicted unless the drive is swapped or flushed. It is the "anchor" for all further RBF lookups.
2.  **Breadcrumb Strategy**: When a directory FD is read, the parser should mark its segments as "sticky" directory body sectors. These are high-priority for the `directory_cache`.
3.  **Flush on Swap**: Whenever a virtual drive is closed or swapped (`swap_drive`), the `directory_cache` MUST be cleared along with the `read_cache` and `dirty_sectors`.
4.  **Cross-Drive Isolation**: Each drive instance must maintain its own `directory_cache`. No global directory caching.

## 📊 Observability

1.  **Count Tracking**: The number of active entries in the `directory_cache` must be tracked and exposed via the drive's `stats` object.
2.  **Hit Rate**: Track separate hit/miss statistics for the directory cache to measure effectiveness versus general read-ahead.
