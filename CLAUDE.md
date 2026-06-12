# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🗂️ Project Overview
DriveWire is a server and protocol suite enabling guest computers (like the Tandy Color Computer) to access host resources (storage, networking, printing) over virtual serial lines. The repository is modular, containing distinct implementations for various platforms, allowing developers to work within their chosen environment.

## 📐 Architecture & Structure
The codebase is vertically sliced by language/platform. All major components interact through a defined, stable protocol managed by the core server logic.

*   **Core Protocol:** Defined by the DriveWire Protocol Specification (`DriveWire Specification.md`). This specification dictates the transactional data exchange that all platform implementations must adhere to.
*   **Platform Implementations:**
    *   **`c/`**: The foundational, portable server logic. This is the recommended starting point for understanding the core protocol state machine, as it handles the essential server functions and network communication.
    *   **`micropython/`**: Provides an advanced, embedded implementation for platforms like the Raspberry Pi Pico. It includes tools for file system repair and web server functionality.
    *   **`swift/`**: The modern macOS implementation, built using Swift. This is the primary target for Apple development.
    *   **`objc/`**: The legacy Objective-C implementation for macOS.
    *   **`delphi/`**: A native implementation for Windows platforms.

## ⚙️ Common Development Tasks

### 1. Running Tests
Testing is highly dependent on the platform:
*   **C Implementation:** Building and running tests typically involves navigating to the `c/` directory and using `make test`.
*   **MicroPython:** Tests are housed in `micropython/tests/` and can be run via `python micropython/run_all_tests.py`.
*   **Swift:** Utilize the Xcode workspace (`swift/DriveWire.xcodeproj/project.xcworkspace`) and the standard test runner provided by Xcode.

### 2. Building from Source
The build process is specific to the target platform:
*   **C/C++:** Use the `Makefile` within the `c/` directory.
*   **Swift:** Build via Xcode using the workspace (`swift/DriveWire.xcodeproj/project.xcworkspace`).
*   **Delphi:** Use the `.dpr` file and the Delphi IDE.

### 3. Development Workflow Guidance
*   **General Development:** When modifying the core protocol handling, focus on files in `c/` (e.g., `drivewire.c`, `dwprotocol.c`).
*   **Web/API:** The `micropython/web_server.py` and `micropython/www/` directories are relevant for client-side web components and network API interaction.
*   **GUI/Client Side:** For platform-specific user interfaces, review the respective folder structures (`objc/`, `swift/`).

## 📖 Documentation & Reference
*   **Protocol Details:** Always refer to the [DriveWire Protocol Specification](DriveWire Specification.md) for transaction details.
*   **Getting Started:** The `docs/` directory contains high-level guides (e.g., `docs/getting-started/installation.md`).
*   **Community:** Check `docs/community/beta-testing.md` for beta testing guidelines.