# MicroPython DriveWire Server

This is a full-featured DriveWire 4 server implementation written in MicroPython, optimized for the **Raspberry Pi Pico W** and **Pico 2 W**.

## Features

- **Standard DriveWire 4 Support**: Works with standard CoCo DriveWire clients (HDB-DOS, OS-9, etc.).
- **Retro Web Dashboard**: A Tandy/CoCo-inspired "Dark Mode" web interface for configuration and monitoring.
- **Virtual Serial TCP/IP**: Map virtual serial ports to external network services (Support for both Client and Server modes).
- **Disk Management**: Dropdown selection for `.dsk` files scanned from local storage and SD cards.
- **Automatic Library Installation**: Built-in installer to fetch dependencies (`microdot`) directly from GitHub.
- **NTP Time Sync**: synchronizes CoCo system time automatically.

## Hardware Requirements

- **Microcontroller**: Raspberry Pi Pico W or Pico 2 W.
- **Serial Connection**: UART pins (TX: GP0, RX: GP1 by default).
- **Level Shifter**: A TTL-to-RS232 level shifter is **required** to safely connect to the CoCo's serial port.

## Quick Start

1. **Upload Files**: Copy the contents of the `micropython` folder to your device.
2. **Configure WiFi**: Edit `config.json` on the device and enter your `wifi_ssid` and `wifi_password`.
3. **Power On**: The device will automatically connect to WiFi and install `microdot` if missing.
4. **Access UI**: Open your web browser and navigate to the IP address printed in the serial terminal (Thonny).
5. **Connect CoCo**: Start your CoCo with DriveWire enabled (e.g., `DRIVEWIRE` command in Disk BASIC 2.0).

## File Structure

- `main.py`: Entry point; starts the servers.
- `drivewire.py`: Core DriveWire protocol logic.
- `web_server.py`: Microdot-based web server and API.
- `config.py`: Configuration management.
- `lib_installer.py`: Automated dependency installer.
- `www/`: Static assets for the web dashboard.

## Dashboard Usage

Click the **DASHBOARD** tab in the web UI to monitor live:
- **Last OpCode**: The most recent command received from the CoCo.
- **Serial Activity**: TX/RX byte counts for active virtual serial channels.
- **System Logs**: Live scroll of internal events.

## Contributing

This is a fork of the original [DriveWire](https://github.com/boisy/DriveWire) project. Contributions are welcome!
