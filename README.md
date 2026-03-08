# DriveWire

DriveWire is a powerful server and protocol suite that allows guest computers (like the Tandy Color Computer) to access storage, networking, and printing resources on a host computer.

---

## ⚡ Key Concepts

- **Virtual Storage**: Guest computers treat the server like a directly connected mass storage device.
- **Remote Operation**: Long serial cables or network connections allow for flexible hardware placement.
- **Modern Management**: Virtual disks are stored as simple files on the host, making backups and sharing effortless.
- **Protocol Driven**: Built on a documented set of *transactions* for reliable data exchange over serial lines.

---

## 🚀 Getting Started

New to DriveWire? Visit our **[Documentation Center](docs/index.md)** for installation guides, hardware wiring, and user manuals.

---

## 📂 Host Implementations

This repository contains official host implementations for multiple platforms:

| Platform | Language | Status | Folder |
|----------|----------|--------|--------|
| **Linux / macOS** | C | Stable | [`c/`](c) |
| **macOS (Modern)** | Swift | Active | [`swift/`](swift) |
| **macOS (Classic)** | Objective-C | Legacy | [`objc/`](objc) |
| **Windows** | Delphi | Native | [`delphi/`](delphi) |
| **RPi Pico W / 2 W** | MicroPython | Advanced | [`micropython/`](micropython) |

> [!TIP]
> **Which one should I use?** 
> - For a dedicated standalone server, the **[MicroPython](micropython/README.md)** version on a Raspberry Pi Pico is highly recommended.
> - For Mac users, the **[Swift](swift/README.md)** version provides the most modern experience.
> - For Linux or headless setups, the **[C](c/README.md)** implementation is best.

---

## 📖 Specifications

Developers interested in implementing the protocol can refer to the:
- **[DriveWire Protocol Specification](DriveWire%20Specification.md)**

---

## 🤝 History & Community

DriveWire began in 2003 and has evolved through multiple iterations (documented in our [History section](docs/index.md#history)). 

**Other Implementations:**
- [pyDriveWire](https://github.com/n6il/pyDriveWire) (Mike Furman)
- [DriveWire 4 Server](https://github.com/qbancoffee/drivewire4) (Java, Aaron Wolfe/Rocky Hill)

---

## 📜 License

DriveWire is free software licensed under the **GPL v3.0**.
