---
trigger: always_on
---

# DriveWire Error Recovery Standards
& Timeout Handling

To ensure high reliability in a networked embedded environment, DriveWire MUST handle timeouts and transient failures gracefully.

## 🌐 Network Timeouts

1. **Socket Timeouts**: All raw socket operations MUST set a timeout (default 5s) to prevent the async loop from hanging.
   - `sock.settimeout(5)`
2. **Explicit Retries**: Operations like NTP sync or RemoteDrive reads MUST implement a retry mechanism with exponential backoff (e.g., 1s, 2s, 4s).
3. **Fail to Ready**: If a remote server is unreachable, the drive state MUST return `E$NotRdy` ($F6/246) immediately to the CoCo rather than timing out the UART loop.

## 🐕 Watchdog (WDT) Recovery

1. **Reason Tracking**: Always check `machine.reset_cause()` at boot (see `resilience.get_reset_cause()`). If a WDT reset occurred, log it at level 3 (ERROR).
2. **Post-Crash Delay**: The 2-second boot delay is sacrosanct. It prevents "death loops" where a crash happens immediately after boot, locking out the REPL.
3. **State Preservation**: Crucial configuration or state changed during an operation should be saved to `config.json` before entering a risky/blocking section.

## 💾 Filesystem Resilience

1. **Atomic Config Saves**: Configuration updates MUST use a temporary file or be written in a single `json.dump` followed by `os.sync()`.
2. **Ghost Directory Cleanup**: The `fs_repair.scrub_root()` utility MUST run at boot to resolve flash filesystem collisions (e.g., `/sd` folder vs `/sd` mount).
