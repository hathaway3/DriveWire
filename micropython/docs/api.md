# DriveWire MicroPython API

The MicroPython DriveWire server provides a REST API for configuration, monitoring, and file management. The web dashboard uses these endpoints to provide a real-time interface.

## Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/config` | GET | Retrieve the current server configuration. |
| `/api/config` | POST | Update server configuration (WiFi, UART, SD pins, etc.). |
| `/api/files` | GET | List all `.dsk` files (up to 3 levels deep). Skips hidden files. |
| `/api/files/info` | GET | Metadata (size, timestamp) for all local files (Streamed JSON). |
| `/api/files/upload` | POST | Upload a `.dsk` file to the Pico via streaming POST. |
| `/api/files/upload_status` | GET | Poll the progress of an active file upload. |
| `/api/files/download` | GET | Download a `.dsk` file from the Pico to your computer. |
| `/api/files/delete` | POST | Delete a `.dsk` file from local storage (internal or SD). |
| `/api/files/create` | POST | Create a new, blank (zero-filled) `.dsk` image. |
| `/api/files/create/status` | GET | Poll the progress of a blank disk creation. |
| `/api/status` | GET | Full server stats, drive stats, and protocol metrics. |
| `/api/status/heartbeat` | GET | Lightweight 1s poll: server time and last opcode. |
| `/api/status/stats` | GET | Drive stats, protocol stats, serial channel activity. |
| `/api/status/terminal` | GET | Incremental terminal buffer data (uses `?offset=N`). |
| `/api/status/logs` | GET | Incremental system log entries (uses `?offset=N`). |
| `/api/sd/status` | GET | SD card mount status and capacity (Streamed response). |
| `/api/serial/monitor` | POST | Set the virtual serial channel to be monitored in the terminal tab. |
| `/api/remote/files` | GET | Combined list of `.dsk` files from all configured remote servers. |
| `/api/remote/test` | POST | Test connectivity and list files for a specific remote server URL. |
| `/api/remote/clone` | POST | Start cloning a remote disk image to local storage (SD card). |
| `/api/remote/clone/status` | GET | Poll the progress of an active clone operation. |

## Data Formats

### `/api/status/heartbeat` (JSON — 1s interval)
```json
{
  "server_time": "09:00:00",
  "last_opcode": 82
}
```

### `/api/status/stats` (JSON — 3s interval)
```json
{
  "protocol_stats": {
    "last_opcode": 82,
    "last_drive": 0,
    "latency": {
      "rx_header_us": 120,
      "turnaround_us": 450
    }
  },
  "drive_stats": [
    {
      "filename": "NitrOS9.dsk",
      "full_path": "/sd/NitrOS9.dsk",
      "read_hits": 1050,
      "read_misses": 210,
      "dir_cache_hits": 300,
      "dir_cache_misses": 15,
      "dir_cache_size": 12,
      "dirty_count": 0,
      "latency_us": 1500,
      "is_remote": false
    },
    null
  ],
  "serial": { "0": { "tx": 120, "rx": 45 } }
}
```

### `/api/status/terminal` (JSON — incremental)
```json
{
  "offset": 1024,
  "data": [72, 101, 108, 108, 111],
  "monitor_chan": 0
}
```

### `/api/status/logs` (JSON — incremental)
```json
{
  "offset": 50,
  "logs": ["[INFO] Drive 0 mounted: NitrOS9.dsk"]
}
```

## Internal Use

> [!NOTE]
> These APIs are primarily intended for the built-in web dashboard. While they can be used by external tools, the formats are subject to change as the server evolves.

---
[Back to README](../README.md)
