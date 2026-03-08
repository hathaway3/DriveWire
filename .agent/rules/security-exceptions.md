---
trigger: always_on
---
# Security & Exception Handling Rules

The DriveWire server is an **unauthenticated, LAN-only** embedded device. Security focuses on preventing path traversal, injection, and ensuring graceful failure.

## 🔒 Path Traversal Prevention

1. **Sanitize All User Paths**: Every user-supplied file path (web API, RFM protocol) **MUST** pass through `_sanitize_path()` (web) or `_sanitize_rfm_path()` (protocol) before use. Direct path concatenation with user input is forbidden.
2. **Reject `..` Segments**: Any path containing `..` must be rejected immediately.
3. **RFM Sandbox**: Remote File Management is restricted to `/sd/` (`RFM_BASE_DIR`). Paths must start with this prefix after normalization.
4. **Static File Serving**: The `/static/<path>` route must reject `..` in path segments before calling `send_file()`.
5. **Filename Cleaning**: For uploads and disk creation, strip directory components with `.split('/')[-1].split('\\')[-1]` and enforce the `.dsk` extension.

## 🛡️ XSS Prevention (Web UI)

1. **Escape All Dynamic Content**: Every user-controlled value inserted into HTML via template literals **MUST** use the `escHtml()` wrapper. No exceptions.
2. **Use `textContent` for Logs**: Log messages and server-sourced text must use `element.textContent`, never `innerHTML`, to prevent injection.
3. **Button Labels Are Safe**: Static button text (`'DELETE'`, `'CLONE'`) may use `textContent` directly without escaping.

## ✅ Input Validation

1. **Config Whitelist**: Config POST accepts only known keys (`baud_rate`, `wifi_ssid`, `drives`, etc.). Unknown fields are silently dropped.
2. **Drive Array Length**: Drive config arrays must be validated for `len == 4` before acceptance.
3. **File Uploads**: Require both `X-Filename` header and `.dsk` extension. Reject all other file types at the API boundary.
4. **Numeric Bounds**: Validate channel numbers (0–31), drive numbers (0–3), and disk sizes against defined maximums.

## ⚠️ Exception Handling

1. **No Bare `except:`**: Always catch specific exceptions (`OSError`, `RuntimeError`, `Exception`). Bare `except:` hides bugs and is only acceptable in test teardown code.
2. **Log Every Error**: All caught exceptions **MUST** be logged via `resilience.log(msg, level=N)` with appropriate severity:
   - Level 0: Debug
   - Level 1: Info
   - Level 2: Warning (network timeouts, non-fatal)
   - Level 3: Error (SD failures, protocol errors)
   - Level 4: Critical (crash, reboot required)
3. **`finally` for Cleanup**: Use `finally` blocks to release resources (files, sockets, LED state, `_uploading` flags). Never leave resources dangling on error paths.
4. **Network Retry with Backoff**: Network operations (RemoteDrive reads, WiFi connect) must use exponential backoff with a maximum of 3 retries. Feed the WDT between retries.

## 💥 Crash Recovery

1. **Top-Level Handler**: The `main.py` crash handler (`except Exception`) must remain: log the error at level 4, blink 'error' LED, sleep 10s, then `machine.reset()`.
2. **WDT Keepalive on KeyboardInterrupt**: On `Ctrl+C`, install a hardware timer to keep feeding the WDT so the device stays alive for REPL access and file uploads.
3. **Boot Delay**: The 2-second `time.sleep()` at the top of `main.py` must remain to allow interrupting boot loops.

## 📐 Reference Implementations

| Pattern | File | Function |
|---------|------|----------|
| Web path sanitization | `web_server.py` | `_sanitize_path()` |
| RFM path sandboxing | `drivewire.py` | `_sanitize_rfm_path()` |
| XSS escaping | `script.js` | `escHtml()` |
| Network retry + backoff | `drivewire.py` | `RemoteDrive.read_sector()` |
| Crash recovery | `main.py` | Top-level `try/except` |
