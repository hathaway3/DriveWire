---
description: How to analyze system logs and troubleshoot connectivity issues
---

1. **Pull Latest Logs**:
   // turbo
   `git pull` (to ensure you have the latest `system.log` if synced).
2. **Read system.log**:
   Read the last 100 lines of `micropython/system.log`.
3. **Filter by Component**:
   - For WiFi issues: grep for `SYS:` and `WiFi`.
   - For DriveWire issues: grep for `DW:`.
   - For SD issues: grep for `SD:`.
4. **Check Reset Cause**:
   Look for `Reset cause:` at the start of log entries. 
   - Cause 1: Power on
   - Cause 3: Watchdog timer (starvation or crash)
5. **Memory Audit**:
   Check for `Memory free:` log entries to identify OOM (Out of Memory) patterns.
