# SPI SD Storage Wiring Guide

This guide explains how to connect SPI SD storage devices to the Raspberry Pi Pico 2 W.

> [!IMPORTANT]
> **GPIO vs. Physical Pin Numbers**: MicroPython and the server logs use **GPIO numbers** (e.g., GP10). Physical wiring uses the **Board Pins** (1 through 40). These are **NOT** the same. 
> 
> *Example: GPIO 10 is Physical Pin 14.*

---

## Default Configuration: SPI Bus 1

The system defaults to **SPI1** using the following pins. This is what you will see in the server logs: `SD card: Init SPI1 SCK=10 MOSI=11 MISO=12 CS=13`.

### SPI1 Wiring Table (Pico 2 W)

| Signal | GPIO (Software) | Physical Pin (Hardware) | Description |
| :--- | :--- | :--- | :--- |
| **SCK** | **GP10** | **14** | SPI Clock |
| **MOSI** | **GP11** | **15** | Data sent to SD card |
| **MISO** | **GP12** | **16** | Data received from SD card |
| **CS** | **GP13** | **17** | Chip Select (Active Low) |
| **3.3V** | - | **36** | Power (3.3V Out) |
| **GND** | - | **3, 8, 13, 18, 23, 28, 33, or 38** | Ground |

---

## Alternative Configuration: SPI Bus 0

If you prefer to use **SPI0**, you can change the `sd_spi_id` to `0` in the Web UI or `config.json`. Below is a common pinout for SPI0:

### SPI0 Wiring Table (Pico 2 W)

| Signal | GPIO (Software) | Physical Pin (Hardware) |
| :--- | :--- | :--- |
| **SCK** | **GP18** | **24** |
| **MOSI** | **GP19** | **25** |
| **MISO** | **GP16** | **21** |
| **CS** | **GP17** | **22** |

---

## Device-Specific Wiring

### Adafruit 4682 (Micro SD Breakout)

> [!CAUTION]
> **3.3V ONLY!** Connect to **Pin 36 (3V3 OUT)** on the Pico. Do **NOT** use Pin 40 (VBUS/5V).

| Adafruit 4682 Pin | Pico Physical Pin (SPI1) |
| :--- | :--- |
| **3V** | **36** (3.3V) |
| **GND** | **13** (GND) |
| **CLK** | **14** (GP10) |
| **SI** (MOSI) | **15** (GP11) |
| **SO** (MISO) | **16** (GP12) |
| **CS** | **17** (GP13) |

---

### Adafruit 6038 (SPI Flash SD)

The 6038 includes a regulator and can be powered by 3.3V or 5V safely.

| Adafruit 6038 Pin | Pico Physical Pin (SPI1) |
| :--- | :--- |
| **VIN** | **36** (3.3V) or **40** (5V) |
| **GND** | **13** (GND) |
| **SCK** | **14** (GP10) |
| **MOSI** | **15** (GP11) |
| **MISO** | **16** (GP12) |
| **CS** | **17** (GP13) |

---

## Troubleshooting "0 entries"

If you see `SD card mounted at /sd (0 entries)` in your logs:
1. **Empty Card**: The card may be mounted correctly but has no `.dsk` files in the root or `/sd` folder.
2. **Formatting**: Ensure the card is formatted as **FAT** or **FAT32**. exFAT is not supported by the default driver.
3. **MISO Pull-up**: SPI communication can be flaky on some modules. Adding a 10kΩ pull-up resistor from **MISO (GP12 / Pin 16)** to **3.3V (Pin 36)** can significantly improve stability.
