# DriveWire MicroPython API

The MicroPython DriveWire server provides a REST API for configuration, monitoring, and file management. The web dashboard uses these endpoints to provide a real-time interface.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Retrieve the current server configuration. |
| `/api/config` | POST | Update server configuration (WiFi, UART, SD pins, etc.). |
| `/api/files` | GET | List all available `.dsk` files on internal flash and SD card. |
| `/api/status` | GET | Current server statistics, logs, and drive assignment info. |
| `/api/sd/status` | GET | SD card mount status, free space, and total capacity. |
| `/api/serial/monitor` | POST | Set the virtual serial channel to be monitored in the terminal tab. |
| `/api/remote/files` | GET | Combined list of `.dsk` files from all configured remote servers. |
| `/api/remote/test` | POST | Test connectivity and list files for a specific remote server URL. |
| `/api/remote/clone` | POST | Start cloning a remote disk image to local storage (SD card). |
| `/api/remote/clone/status`| GET | Poll the progress of an active clone operation. |
| `/api/files/delete` | POST | Delete a `.dsk` file from local storage (internal or SD). |
| `/api/files/download` | GET | Download a `.dsk` file from the Pico to your computer. |
| `/api/files/upload` | POST | Upload a `.dsk` file to the Pico via streaming POST. |
| `/api/files/upload_status`| GET | Poll the progress of an active file upload. |
| `/api/files/create` | POST | Create a new, blank (zero-filled) `.dsk` image. |
| `/api/files/info` | GET | Metadata (size, timestamp) for all local `.dsk` files. |

## Data Formats

Most endpoints return JSON. For example, `/api/status` returns a structure like:

```json
{
  "server_time": "2026-03-21 09:00:00",
  "stats": {
    "last_opcode": 82,
    "latency": {"rx_header_us": 120, "turnaround_us": 450}
  },
  "drive_stats": [
    {
      "filename": "NitrOS9.dsk",
      "full_path": "/sd/NitrOS9.dsk",
      "read_hits": 1050,
      "read_misses": 210,
      "dirty_count": 0,
      "is_remote": false
    },
    null,
    ...
  ],
  "logs": ["..."],
  "monitor_chan": 0
}
```


## Internal Use

> [!NOTE]
> These APIs are primarily intended for the built-in web dashboard. While they can be used by external tools, the formats are subject to change as the server evolves.

---
[Back to README](../README.md)
