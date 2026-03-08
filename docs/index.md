# DriveWire Documentation

DriveWire is a flexible server and protocol suite for the TRS-80 Color Computer and compatible systems, providing virtual disks, high-speed networking, and various host services.

---

## 🧭 Navigation

- **[Installation](getting-started/installation.md)**: How to install DriveWire on your host system.
- **[Configuration](getting-started/configuration.md)**: Setting up DriveWire for your specific hardware.
- **[Using DriveWire](getting-started/using-drivewire.md)**: A comprehensive guide to standard features.
- **[Cables & Wiring](getting-started/cables.md)**: Physical connection requirements and diagrams.

---

## 💻 Platform Compatibility

| Host Platform | Implementation | Host OS Requirement | Recommended For |
|---------------|----------------|---------------------|-----------------|
| **Pico W / 2 W** | [MicroPython](../micropython/README.md) | Firmware | Standalone / Low Power |
| **Linux** | [C](../c/README.md) | Kernel 2.6+ | Headless / Servers |
| **macOS** | [Swift](../swift/README.md) | macOS 11+ | Desktop Users |
| **Windows** | [Delphi](../delphi/README.md) | Windows 7+ | Windows Desktop |
| **Classic Mac** | [Objective-C](../objc/README.md) | OS X 10.9+ | Older Macs |

---

## 🛠️ User Guides

- **[NitrOS-9 Integration](guides/nitros9-level2-integration.md)**: Using DriveWire with NitrOS-9 Level 2.
- **[OS-9 Modules](guides/os9-modules.md)**: Technical details for OS-9 users.
- **[The 'dw' Commands](guides/dw-commands.md)**: CLI power-tool reference.
- **[Low Memory Tips](guides/solving-low-memory-issues.md)**: Running on systems with limited RAM.
- **[Custom Drivers](guides/add-drivewire-drivers.md)**: Adding new hardware drivers.

---

## 📐 Technical Specifications

- **[DriveWire Protocol 4.0](../DriveWire%20Specification.md)**: The core protocol details.
- **[Becker Ports](technical/becker-port-specification.md)**: Low-level hardware interface.
- **[Config.xml Reference](technical/config-xml.md)**: XML configuration file schema.
- **[Writing Software](technical/writing-network-software.md)**: Developer's guide for network tools.

---

## 🌍 Community & Support

- **[Getting Help](community/getting-help.md)**: Discord, Mailing Lists, and Forums.
- **[Bug Reports](https://github.com/boisy/DriveWire/issues)**: Submit issues on GitHub.
- **[License](#license)**: GPL v3.0 Software.

---

## 📜 History

DriveWire began in 2003 as a solution for the Tandy Color Computer, filling the gap as floppy drives became scarce. It was originally developed by Boisy Pitre and later expanded by Aaron Wolfe and Jim Hathaway to include networking services, winning the 2010 RetroChallenge.

Today, DriveWire continues to power Color Computer setups worldwide, with new implementations like the **RPi Pico MicroPython** version keeping the project alive on modern hardware.

---

## License

DriveWire is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
