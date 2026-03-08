# Installation

This guide covers the general installation of the DriveWire server software.

## 📋 Prerequisites

- **Hardware**: You will need a suitable serial cable to connect your CoCo to your host computer. See **[DriveWire Cables](cables.md)**.
- **Client Software**:
    - **[Color Computer (CoCo)](../clients/coco.md)**: Hardware-side drivers.
    - **[Non-CoCo Systems](../clients/non-coco.md)**: Support for compatible systems.
    - **[Custom Drivers](../guides/add-drivewire-drivers.md)**: For advanced setups.

## 🔨 General Installation

Installing the DriveWire server typically involves unpacking an archive for your specific platform. Most implementations are self-contained and do not require a formal installer.

> [!IMPORTANT]
> Choose the implementation that matches your host operating system:
> - **Linux / macOS**: See the **[C implementation](https://github.com/hathaway3/DriveWire/tree/master/c)**.
> - **macOS (Modern)**: See the **[Swift implementation](https://github.com/hathaway3/DriveWire/tree/master/swift)**.
> - **Windows**: See the **[Delphi implementation](https://github.com/hathaway3/DriveWire/tree/master/delphi)**.
> - **RPi Pico W**: See the **[MicroPython implementation](https://github.com/hathaway3/DriveWire/tree/master/micropython)**.

## ☕ Java Server Requirements

The legacy Java-based DriveWire server requires a **Java J2SE 7** or newer JRE. You can download this from [java.com](http://www.java.com/getjava/).

## ➡️ Next Steps

Once your server is installed and running, proceed to **[Configuration](configuration.md)** or learn about **[Using DriveWire](using-drivewire.md)**.

---
[Return to Documentation Index](../index.md)
