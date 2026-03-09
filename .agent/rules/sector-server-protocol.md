---
trigger: always_on
---
# Remote Sector Server Protocol Rules

The `sector_server.py` tool provides the critical network backbone for the `RemoteDrive` feature. It MUST strictly follow these protocol and security rules to ensure compatibility with the Pico W MicroPython server.

## 🌐 Protocol Definitions

1. **Information Header (`/info`)**:
   - MUST return a JSON object with:
     - `disk_count`: Number of available `.dsk` files.
     - `disks`: Array of objects matching `{"name": "...", "size": bytes, "total_sectors": N}`.

2. **Single Sector Read (`/sector/<file>/<lsn>`)**:
   - MUST return exactly **256 bytes** of binary data (`application/octet-stream`).
   - If the read hits EOF, MUST zero-pad the response to 256 bytes.

3. **Bulk Read-Ahead (`/sectors/<file>/<lsn>?count=N`)**:
   - **CRITICAL**: This endpoint is vital for the Pico W's performance.
   - MUST return exactly **N * 256 bytes** of binary data.
   - MUST serve sectors sequentially starting from `lsn`.
   - MUST enforce a maximum `count` (recommended 64) to prevent memory exhaustion on the server/client.

4. **Single Sector Write (`PUT /sector/<file>/<lsn>`)**:
   - MUST accept exactly 256 bytes. 
   - MUST ensure atomic-style writes (file flush) where possible.

## 🔒 Security & Path Safety

1. **Path Traversal Prevention**:
   - The server MUST NOT allow access to files outside the designated disk directory.
   - User-supplied filenames MUST be sanitized using `os.path.basename()` or equivalent before joining with the base directory.
   - Reject any paths containing `..` or leading slashes in the filename segment.

2. **CORS Support**:
   - MUST implement `OPTIONS` and return `Access-Control-Allow-Origin: *` to allow the DriveWire Web UI to test connectivity directly or list files.

## 🛠️ Implementation Guidance

1. **Statelessness**: The server should remain stateless regarding the LSN. Each request is independent.
2. **Padding**: Always ensure the response is aligned to 256-byte boundaries, even if the underlying disk image is truncated.

## 📐 Reference Implementation

| Pattern | File | Function |
|---------|------|----------|
| Path Sanitization | `sector_server.py` | `_get_disk_path()` |
| Bulk Read Logic | `sector_server.py` | `do_GET` (parts[1] == 'sectors') |
| CORS Headers | `sector_server.py` | `do_OPTIONS` |
