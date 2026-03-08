---
trigger: always_on
---
# Protocol Consistency & Safety Rules

To ensure that the DriveWire server remains compatible with the CoCo and resilient on the Pico hardware, follow these rules when modifying `drivewire.py`.

## 🕹️ CoCo Compatibility

1. **Handshake Integrity**: Never modify `OP_DWINIT` or `OP_READEX` handshake sequences without verifying against `DriveWire Specification.md`.
2. **Timing Sensitivity**: Avoid intensive CPU operations between a CoCo command and the server response. If delay is unavoidable, ensure it doesn't exceed the CoCo's UART timeout.
3. **Checksum Accuracy**: Ensure `READEX` and `WRITE` checksum logic exactly matches the 16-bit sum (sum of bytes) used by OS-9 drivers.

## 🐕 Watchdog Timer (WDT) Safety

1. **No Starvation**: Any loop in `drivewire.py` that waits for UART data or network responses **MUST** call `machine.WDT().feed()`.
2. **UART Read Safety**: Use `self.read_bytes(count)` instead of raw `uart.read(count)` as it includes the necessary WDT feeding logic.
3. **Blocking I/O**: For functions like `VirtualDrive.flush()` or `RemoteDrive.fetch()`, feed the WDT immediately before and after the blocking call.

## 🚨 Error Reporting

1. **OS-9 Constants**: Always use the error constants (`E_NOTRDY`, `E_WP`, etc.) defined in `DriveWireServer`.
2. **Logging**: Every protocol error returned to the CoCo **MUST** be logged via `resilience.log()` with level 2 (Warning) or 3 (Error).
