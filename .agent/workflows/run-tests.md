---
description: How to run host-side simulation tests and the sector server
---

1. **Host-Side Unit Tests**:
   - Run specific tests using standard Python:
     `python micropython/test_drivewire.py`
     `python micropython/test_resilience.py`
   - These tests use mocks for `machine` and `network` modules.

2. **Remote Drive Testing (Sector Server)**:
   - Start the local sector server:
     `python micropython/tools/sector_server.py --port 8080 --dir ./tests/disks`
   - Configure a remote drive in `config.json`:
     ```json
     "remote_servers": [{"name": "LocalTest", "url": "http://localhost:8080"}]
     ```
   - Verify connectivity via `DW: RemoteDrive` log entries.

3. **Serial Channel Simulation**:
   - For TCP bridging tests, use `nc` (netcat) or a similar utility to listen on mapped ports.
