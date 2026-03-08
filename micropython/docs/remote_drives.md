# Remote Disk Images & Cloning

The MicroPython DriveWire server can mount disk images hosted on a remote server (Linux, Mac, or Windows) over your local network.

## Concepts

- **Remote Sector Server**: A lightweight Python script running on your workstation that serves `.dsk` files over HTTP.
- **Read-Only by Default**: Remote drives are mounted as read-only to protect the source images on your workstation.
- **Clone & Hot-Swap**: A feature that allows you to copy a remote image to your local SD card and immediately "swap" the drive assignment to the new local copy without interrupting the CoCo.

## Setting Up the Sector Server

The sector server is a zero-dependency Python script included in the `tools` directory:

```bash
# Basic usage — serve all .dsk files in current directory
python tools/sector_server.py

# Specify directory and port
python tools/sector_server.py --dir /home/user/coco/disks --port 8080

# Custom server name (shown in the web UI)
python tools/sector_server.py --dir ./disks --port 8080 --name "Build Server"
```

### Sector Server API

The MicroPython DriveWire server communicates with the sector server using these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/info` | GET | Server identity and list of available disks with sizes. |
| `/files` | GET | Simple list of `.dsk` filenames. |
| `/sector/<filename>/<lsn>` | GET | Read a single 256-byte sector. |
| `/sectors/<filename>/<lsn>?count=N` | GET | Bulk read of N consecutive sectors (max 64). |
| `/sector/<filename>/<lsn>` | PUT | Write a single 256-byte sector (usually disabled). |

## Configuring Remote Servers

1. Open the DriveWire web dashboard in your browser.
2. Go to the **CONFIGURATION** tab and expand **ADVANCED OPTIONS**.
3. Under **REMOTE SERVERS**, click **+ ADD SERVER**.
4. Enter a **Name** and the **URL** (e.g., `http://192.168.1.100:8080`).
5. Click **TEST** to verify connectivity (🟢 confirms, 🔴 indicates a problem).
6. Click **SAVE CONFIG**.

## Clone & Hot-Swap

Clone a remote disk image to your local SD card to enable write access or to work offline.

### From the Files Tab
1. Navigate to **FILES → REMOTE FILES**.
2. Click **CLONE** next to the desired image.
3. (Optional) Set a local filename and assign it to a drive slot (hot-swap).
4. Click **CLONE**. A progress bar will show the download status.

### From the Drives Tab
- Active remote drives show a **CLONE TO LOCAL** button directly on their status card for quick one-click cloning.

> [!TIP]
> **Performance**: A 360KB disk image typically clones in 5-10 seconds over a stable WiFi connection. The download uses 4KB bulk chunks to optimize SD card writes.

---
[Back to README](../README.md)
