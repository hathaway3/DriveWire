1. **Unit Tests**: `python micropython/test_drivewire.py` / `test_resilience.py`.
2. **Sector Server**: `python micropython/tools/sector_server.py --port 8080 --dir ./tests/disks`.
3. **Serial**: Use `nc` (netcat) to listen on mapped TCP ports.
