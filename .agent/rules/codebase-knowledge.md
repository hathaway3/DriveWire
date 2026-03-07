## Codebase Knowledge Base

Before starting any work on the DriveWire MicroPython server, **read the knowledge base**:

- **[.agent/knowledge/drivewire_codebase.md](file:///Users/jimmiehathaway/DriveWire/.agent/knowledge/drivewire_codebase.md)** — Architecture, protocol implementation, security patterns, WDT strategy, exception handling conventions, and known limitations.

This document is the single source of truth for codebase patterns and decisions. **Update it** when making significant architectural changes.

### DriveWire Protocol Specification

When working on **protocol-related code** (opcodes, serial channels, RFM, disk I/O in `drivewire.py`), also reference the full specification:

- **[DriveWire Specification.md](file:///Users/jimmiehathaway/DriveWire/DriveWire%20Specification.md)** — Complete DriveWire 4.0 protocol specification including packet formats, opcode tables, virtual serial channel semantics, and error codes.

You do **not** need to read the full spec for non-protocol work (web UI, config, SD card, etc.) — the knowledge base covers those areas sufficiently.
