# DriveWire Server Implementation (C)

This folder contains the core DriveWire server implementation written in C.  This implementation is designed for maximum portability, allowing it to run on a wide range of platforms. While primarily intended for Linux, it's known to be buildable and functional on macOS as well. This version focuses on foundational server logic and network communication.

## 📋 Overview

The C implementation provides the bedrock for the DriveWire system. It handles the essential functions of emulating virtual drives and printers, communicating with clients, and managing the overall server state.

Key files include:
*   `drivewire.c`: The main server application logic.
*   `drivewire.h`:  Public header file defining the server API.
*   `dwprotocol.c`:  Implementation of the DriveWire communication protocol.
*   `dwwin.c`: Windows-specific implementation details (may contain platform-dependent features).

## 🔨 Build Instructions

To build the C server:

1.  **Prerequisites:** You'll need a C compiler (e.g., GCC, Clang) and a build environment (e.g., Make).
2.  **Make:** Navigate to the `c` directory and run `make`.
    ```bash
    cd c
    make
    ```
3.  **Run:** execute the generated binary (e.g., `./drivewire`).

## ✅ Status

- **Stability**: Stable. Used as the base for several other implementations.
- **Support**: Primarily targeted at Linux/UNIX-like systems.
- **Known Issues**: Windows support is legacy and may require modern compiler adjustments.

---
[Return to Documentation Index](../docs/index.md)
