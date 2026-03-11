## Codebase Knowledge Base

Before starting any work on the DriveWire MicroPython server, **read the knowledge base**:

- **[drivewire_codebase.md](../knowledge/drivewire_codebase.md)** — Architecture & protocol summary.
- **[protocol-standards.md](protocol-standards.md)** — DW/Sector server protocol standards.
- **[mp-raspi-pico.md](mp-raspi-pico.md)** — Hardware resilience & WDT strategy.
- **[sector-caching.md](sector-caching.md)** — Sector/RBF caching & parser.
- **[security-exceptions.md](security-exceptions.md)** — Security & Error standards.
- **[task-priority.md](task-priority.md)** — Performance & Tasking rules.
- **[streaming-data.md](streaming-data.md)** — Memory-safe data patterns.
- **[web-ui-standards.md](web-ui-standards.md)** — Responsive UI standards.
- **[code-quality.md](code-quality.md)** — MicroPython coding standards.
- **[testing-standards.md](testing-standards.md)** — Host and on-device testing.
- **[feature-development.md](../workflows/feature-development.md) — Safe feature addition workflow.
- **[hardware-verification.md](../workflows/hardware-verification.md) — Hardware health checks.
- **[release-checklist.md](../workflows/release-checklist.md) — Pre-release verification.
- **[documentation-sync.md](documentation-sync.md)** — Code/Doc sync rules.

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
