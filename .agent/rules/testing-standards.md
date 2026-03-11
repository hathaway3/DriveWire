# Testing & Verification Standards

To maintain high reliability, all changes to the DriveWire codebase must be verified using the following testing standards.

## 💻 Host-Side Unit Testing

1. **Mock Hardware**: Use `unittest.mock` to simulate MicroPython-specific modules like `machine`, `network`, and `os`.
2. **Requirement**: New core logic (parsers, state machines, utilities) must have accompanying host-side tests in `micropython/tests/`.
3. **Execution**: Tests should be runnable via standard Python 3.x using `python -m unittest discover tests`.

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
