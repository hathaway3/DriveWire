# DriveWire Configuration File (config.xml)

This document outlines the purpose and content of the `config.xml` file used by the Java and Delphi implementations of DriveWire.

## 📂 General
Global parameters that apply to the entire DriveWire application, such as the application name and global logging default.

## 🔧 Instance
Defines specific blocks for a single server instance. DriveWire can run multiple instances (servers) simultaneously, each with its own port and disk set.

## 💾 Drives
Defines the virtual storage devices. Each entry specifies a drive's name, type (local, network), and mount point.

## 🏷️ NamedObjects
Allows definition of named entities that can be mounted into drives by name (e.g., for CoCoBoot).

## ⚙️ Settings

### Debugging
Controls the level of diagnostic information generated. Useful for troubleshooting connectivity issues.

### Device
Hardware-specific settings for the host side, including **SerialRate**, **SerialParity**, and **TCPPort** for network-tethered setups.

### MIDI
Configuration for MIDI input and output, including port assignments and synthesis profiles.

### Networking
Governs network behavior, IP addresses, and firewall/remote connection permissions.

### Protocol
Specifies the DriveWire protocol version to be used and any encryption or authentication settings.

### Printing
Configuration for virtual printers, including default output formats and spooling behavior.

---
[Return to Documentation Index](../index.md)
