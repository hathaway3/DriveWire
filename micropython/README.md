# MicroPython DriveWire Server

A full-featured DriveWire 4 server implementation in MicroPython, optimized for the **Raspberry Pi Pico W** and **Pico 2 W** with advanced memory management and performance optimizations.

---

## 🚀 Quick Start

1. **Upload Files**: Copy all files from the `micropython` folder to your Pico W/2 W root directory.
2. **Configure WiFi**: Edit `config.json` on the device:
   ```json
   {
     "wifi_ssid": "YourNetworkName",
     "wifi_password": "YourPassword",
     "baud_rate": 115200
   }
   ```
3. **Power On**: Device will auto-connect to WiFi and install dependencies (`microdot`) if missing.
4. **Access Dashboard**: Open browser to the IP address shown in the serial terminal.
5. **Connect CoCo**: Attach serial cable and start DriveWire on your CoCo (e.g., `DRIVEWIRE` in Disk BASIC 2.0).

---

## 📚 Documentation Index

| Section | Description |
|---------|-------------|
| [🔌 Wiring Guide](docs/wiring.md) | How to connect your Pico to the CoCo and SD card. |
| [🌐 Remote Drives](docs/remote_drives.md) | Using remote disk images and Clone & Hot-Swap. |
| [🛠️ REST API](docs/api.md) | Documentation for the server's internal API endpoints. |

---

## ✨ Key Features

- **Flash Wear Protection**: Sector-level write-back cache buffers all disk writes in RAM, significantly extending flash lifespan.
- **SD Card Support**: External SD card storage via SPI with automatic FAT/FAT32 mounting.
- **Remote Disk Images**: Mount read-only disk images from a remote HTTP sector server over WiFi.
- **Activity LED**: Onboard LED blinks during disk ops and glows during flash flushes.
- **Robust Error Handling**: Comprehensive exception handling across all I/O operations with graceful fallbacks.
- **Memory Optimized**: Reduced cache sizes and `const()` declarations minimize RAM usage (~80-120KB typical).
- **Retro Web Dashboard**: Tandy/CoCo-inspired dark mode interface for configuration and monitoring.
- **Virtual Serial TCP/IP**: Map CoCo virtual serial ports to external network services.
- **Remote File Manager (RFM)**: Full DriveWire 4 RFM support natively from the CoCo.
- **Configurable Logging**: Control log verbosity (DEBUG to CRITICAL) from the web dashboard.

---

## 📋 System Logging

The server maintains a circular log buffer for the Web Dashboard and an optional persistent `system.log` file on the flash.

| Level | Name | Description | Flash Wear |
|-------|------|-------------|------------|
| 0 | DEBUG | Verbosely log every packet and internal state change. | **HIGH** |
| 1 | INFO | Log system startups, drive mounts, and major events. | LOW |
| 2 | WARN | Log timeouts, retries, and non-fatal network issues. | MINIMAL |
| 3 | ERROR | Log failed operations (SD errors, protocol failures). | MINIMAL |
| 4 | CRIT | Log system crashes or hardware failures. | MINIMAL |

> [!WARNING]
> **Flash Wear Mitigation**: Setting the log level to **DEBUG (0)** results in frequent writes to the Pico's internal flash memory. Use this level only for active troubleshooting and revert to **INFO (1)** or **WARN (2)** for daily use to extend the lifespan of your device.

---

## 📊 Performance & Memory

**Typical Memory Usage:**
- **Base system**: ~60-80KB
- **Per mounted drive**: ~2-4KB (with 8-entry cache)
- **Web server**: ~20-30KB
- **Total typical usage**: 80-120KB

**Optimizations:**
- Reduced read cache (8 entries per drive) saves ~2KB per drive.
- `micropython.const()` for all opcodes/constants saves RAM.
- Limited channel buffers to 256 bytes max.
- Efficient timeout handling reduces latency.

---

## 🛠️ Troubleshooting

- **WiFi issues?** Verify SSID/password and ensure 2.4GHz network.
- **CoCo not responding?** Check level shifter wiring and baud rate (default 115200).
- **SD card not detected?** Verify wiring and format (FAT/FAT32 only).
- **Memory Errors?** Reduce mounted drives or clear `error.log`.
- **WDT Reboots?** Press Ctrl-C in Thonny and wait for the "WDT kept alive" message before uploading.

See the [Wiring Guide](docs/wiring.md) for detailed hardware troubleshooting.

---

## 📁 File Structure

| File | Purpose |
|------|---------|
| `tests/` | Host-side simulation tests and utilities |

---

## 🧪 Testing

The DriveWire server includes host-side simulation tests to verify protocol correctness and RBF (OS-9) disk handling without needing physical hardware.

### Running Tests
To run the full suite of simulation tests:
```bash
python3 tests/test_drivewire.py
python3 tests/test_resilience.py
python3 tests/test_os9_disk.py
```

### Generating Test Disks
You can create a minimal valid OS-9 RBF disk image for testing purposes using the utility:
```bash
python3 tests/os9_disk_util.py
```
This will create `test_os9.dsk` with a valid LSN 0 and root directory.

---

## 🤝 Contributing

This is a fork of the original [DriveWire](https://github.com/boisy/DriveWire) project. Contributions welcome!
