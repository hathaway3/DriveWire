---
description: Steps to verify the health and configuration of the Pico W hardware.
---

# Hardware Verification Workflow

Use this workflow to troubleshoot or verify a new hardware setup (SD card, WiFi, UART).

## 📊 WiFi Verification
1. **Check Signal**: Log the RSSI value during boot.
   - `resilience.log(f"WiFi Status: {network.WLAN(network.STA_IF).status()}, RSSI: {network.WLAN(network.STA_IF).status('rssi')}")`
2. **Connectivity Test**: Ping the default gateway or common remote server.
3. **Backoff Check**: Verify that the retry mechanism in `boot.py` triggers on connection failure.

## 💾 SD Card Verification
1. **Mount Check**: Ensure `/sd` is visible in `os.listdir('/')`.
2. **Write/Read Test**: Create a temporary file and read it back.
   - `with open('/sd/test.tmp', 'w') as f: f.write('PicoTest')`
3. **Speed Test**: Measure time to write a 1MB file (4KB chunks). This confirms SPI bus performance (10MHz+).

## 🏎️ UART & Protocol Verification
1. **Loopback Test**: Connect GP0 to GP1 and send/receive data at 115200 baud.
2. **Baud Rate Sweep**: Verify stability at 115200, 230400, and 460800 baud.
3. **WDT Feed Check**: Ensure the system does not reboot during high UART traffic.

## 🚨 LED Signal Codes
1. **Self-Test**: Run `resilience.blink_state('boot')`.
2. **Error State**: Simulate an error (e.g., unplug SD) and verify the 'error' blink pattern.
