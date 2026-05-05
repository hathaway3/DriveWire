---
trigger: always_on
---

# DriveWire Testing Standards

## 💻 Host-Side Unit Testing

1. **Mock Hardware**: Use `unittest.mock` to simulate MicroPython-specific modules like `machine`, `network`, and `os`.
2. **Requirement**: New core logic (parsers, state machines, utilities) must have accompanying host-side tests in `micropython/tests/`.
3. **Execution**: Tests MUST be runnable via `python run_all_tests.py`. This custom runner ensures process isolation, preventing `sys.modules` pollution and `MagicMock` state leakage between test modules.

> [!IMPORTANT]
> **Not a Substitute**: Host-side tests cannot replicate hardware-specific behavior like WDT resets, boot timing, or real-time SPI/UART latency. All hardware-interacting features MUST also pass on-device verification as defined in `mp-raspi-pico.md`.

### ⚠️ MicroPython Mocking Gotchas

1. **Identity Mocking**: All `micropython.const()` calls MUST be mocked as identity functions (`mock.const = lambda x: x`) in `shim.py`. Failure to do so converts opcodes and constants into `MagicMock` objects, breaking equality checks.
2. **Namespace Patching**: Always patch at the point of *usage*. For example, use `patch('resilience.machine')` instead of `patch('machine')` if the logic in `resilience.py` is being tested.
3. **Async reader.read()**: When mocking `uasyncio` streams, ensure `reader.read()` is configured to return `b''` (empty bytes) or `None` on its final call. Without this, protocol loops (`while True: data = await reader.read()`) will hang infinitely in tests.
4. **Initialization Guards**: Patch side-effect methods like `DriveWireServer.init_drives()` or `init_uart()` in the test `asyncSetUp`. These methods often overwrite test-injected mocks with default hardware handles at runtime.
5. **Decorator Preservation**: Mocked decorators (like `@app.post` in Microdot) MUST return the original function they decorate. Returning a `MagicMock` breaks `await` calls and results in `TypeError` or unawaited coroutine warnings.
6. **Object Structure Alignment**: Ensure mocked objects (like `config.shared_config`) match the expected runtime attribute structure (e.g., providing a `.config` dictionary instead of being a plain dictionary).

## 🍓 On-Device Testing

1. **Hardware Confirmation**: For features involving SPI, I2C, or UART hardware, on-device verification is required.
2. **Self-Contained**: On-device test scripts should be self-contained and not depend on the full DriveWire server to run.
3. **Logging**: Use `resilience.log()` during on-device tests to capture results to `system.log`.

## 🔄 Verification Workflow

1. **Pre-Commit**: Run all host-side tests before committing code changes.
2. **Regression Testing**: When fixing a bug, add a test case that covers the failing scenario to prevent future regressions.
3. **Environment Parity**: Ensure that tests run consistently across both Windows and Linux hosts where possible.

## 📋 Reporting

1. **Pass/Fail Clear**: All tests must clearly indicate failure with descriptive error messages.
2. **Traceability**: Link test results to the corresponding feature or bug ID in task summaries.
