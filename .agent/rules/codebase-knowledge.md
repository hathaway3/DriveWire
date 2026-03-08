## Codebase Knowledge Base

Before starting any work on the DriveWire MicroPython server, **read the knowledge base**:

- **[.agent/knowledge/drivewire_codebase.md](../knowledge/drivewire_codebase.md)** — Architecture, protocol implementation, security patterns, WDT strategy, exception handling conventions, and known limitations.

This document is the single source of truth for codebase patterns and decisions. **Update it** when making significant architectural changes.

- **[.agent/rules/documentation-sync.md](documentation-sync.md)** — Rules for ensuring documentation stays in sync with code changes.
- **[.agent/rules/web-ui-standards.md](web-ui-standards.md)** — Best practices for responsive mobile/desktop UI development.
- **[.agent/workflows/deploy-docs.md](../workflows/deploy-docs.md)** — Workflow for updating and verifying documentation links.

### Documentation & GitHub Pages

1. **Relative Links**: All internal documentation links **MUST** use relative paths. This ensures they work both in the Git repo and on the GitHub Pages site (`hathaway3.github.io/DriveWire/`).
2. **Link Verification**: Run `python verify_links.py` before committing any documentation changes.
3. **MkDocs Sync**: Ensure new documentation files are added to `mkdocs.yml` navigation.


### DriveWire Protocol Specification

When working on **protocol-related code** (opcodes, serial channels, RFM, disk I/O in `drivewire.py`), also reference the full specification:

- **[DriveWire Specification.md](../../DriveWire%20Specification.md)** — Complete DriveWire 4.0 protocol specification including packet formats, opcode tables, virtual serial channel semantics, and error codes.

You do **not** need to read the full spec for non-protocol work (web UI, config, SD card, etc.) — the knowledge base covers those areas sufficiently.

## context-efficiency rules

1. **Grep Before View**: Before reading `drivewire.py`, use `grep_search` to find the specific opcode or function you need.
2. **Use Outlines**: Always call `view_file_outline` on new files over 200 lines before reading code.
3. **Log Priority**: When debugging, read `micropython/system.log` first rather than guessing state.

## Hardware Error Mapping

| OS-9 Error | DW Code | Pico Cause |
|------------|---------|------------|
| `E$NotRdy` | 246 | WiFi Down / Remote Server Timeout |
| `E$WP`     | 242 | SD Card Write Protect / Remote Drive |
| `E$CRC`    | 243 | Checksum mismatch in READEX/WRITE |
| `E$Read`   | 244 | Hardware SPI / SD read failure |
| `E$Unit`   | 240 | Invalid drive number (not 0-3) |
