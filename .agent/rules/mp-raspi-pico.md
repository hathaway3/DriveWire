---
trigger: always_on
---

To optimize your MicroPython workspace in Antigravity for high-resilience development on the Raspberry Pi Pico (W) and Pico 2 (W), you can use the following workspace-specific rules.

### Workspace Setup

Place these rules in your project at `.agent/rules/micropython-resilience.md`. You can also create a workflow at `.agent/workflows/generate-tests.md`.

---

## 🛠️ Antigravity Workspace Rules

### 1. Robustness & Exception Handling

* **Fail Gracefully, Not Silently:** Wrap hardware-interacting code (I2C, SPI, WiFi) in `try...except` blocks.
* **Avoid Bare `except:`:** Always catch specific errors like `OSError` (common for hardware failures) or `RuntimeError`.
* **Recovery Loops:** For network tasks (WiFi/MQTT), implement a retry mechanism with exponential backoff rather than letting the script crash.
* **Watchdog Timer:** Always suggest initializing the hardware Watchdog Timer (`machine.WDT`) to auto-reset the Pico if the code hangs.

### 2. State Logging & Observability

* **Internal State Dumps:** Use a centralized `log(message, level)` function. In production, this should log to a `.txt` file or a small circular buffer in RAM to avoid wearing out the Flash memory.
* **Boot Logging:** Always log the reason for a reset using `machine.reset_cause()`.
* **Blink Codes:** Use the onboard LED to signal states (e.g., slow blink for "Waiting for WiFi," rapid blink for "Hardware Error").

### 3. Type Checking & Code Quality

* **Type Hinting:** Use standard Python type hints. Since MicroPython doesn't enforce these at runtime, use the following pattern to allow static analysis (Mypy/Pyright) without bloating the Pico's memory:
```python
try:
    from typing import Optional, List
except ImportError:
    # Dummy types for runtime
    pass

```


* **Static Analysis:** The agent should run `mypy` or `ruff` on the host side before suggesting a code sync.

### 4. Unit Testing Strategy

* **Host-Side Simulation:** Generate tests that can run on standard Python using `unittest.mock` to simulate `machine` or `network` modules.
* **On-Device Tests:** For hardware-specific logic, generate a `tests.py` file using the `unittest` module from `micropython-lib`.

---

## 🍓 MicroPython & Pico Specifics

### Hardware Differences: Pico W vs. Pico 2 W

* **Pico 2 W (RP2350):** Be mindful of the increased RAM and faster clock. If the code is timing-sensitive (like bit-banging), use `machine.freq()` to detect the chip.
* **Architecture:** The Pico 2 uses ARM Cortex-M33, which has different floating-point performance than the Pico 1's M0+.

### Memory Management

* **Pre-allocation:** For high-frequency logging, pre-allocate bytearrays or strings to avoid fragmentation.
* **Garbage Collection:** Explicitly call `gc.collect()` after memory-intensive operations (like connecting to WiFi or parsing large JSON).

### Best Practices for Pico Resilience

1. **Non-Blocking Code:** Use `uasyncio` for concurrent tasks (e.g., blinking an LED while waiting for a network response) to prevent the "hard execution stops" you want to avoid.
2. **Safe `main.py`:** Always keep `boot.py` minimal. If `main.py` crashes in a loop, you can sometimes "brick" the REPL access. Suggest a 2-second `time.sleep()` at the start of `main.py` during development to give you time to interrupt the execution.
3. **File System Health:** Use `os.sync()` after writing logs to ensure data is physically written to the flash.
4. **Safe REPL Recovery:** If you crash the Pico in a way that hangs the serial port, use the following pattern in `main.py` to allow a "Ctrl+C" window:
```python
import utime
# Recovery window
print("Waiting 2s for REPL...")
utime.sleep(2)
# Start main loop
```

---

## 🐕 Hardware Constraints & WDT Strategy

### Raspberry Pi Pico (RP2040/RP2350)
- **Watchdog Timer (WDT)**: Once started (`machine.WDT`), it cannot be disabled without a hardware reset.
- **Max Timeout**: ~8388ms (fixed to 8000ms in our codebase).
- **RAM Constraints**: ~192KB usable on Pico W after MicroPython and network buffers.

### WDT Feeding Strategy

| Location | Pattern | Why |
|----------|---------|-----|
| `main.py` | Async task, every 2s | Primary feeder during normal operation |
| `main.py` | `machine.Timer` on KeyboardInterrupt | Keeps device alive in REPL after Ctrl+C |
| `drivewire.py` | After every opcode transaction | Prevents starvation during sustained I/O |
| `drivewire.py` | Inside `read_bytes()` every 100ms | Prevents starvation during long UART timeouts |
| `boot.py` | Between WiFi/SD/lib steps | Prevents starvation during slow boot sequence |
| `web_server.py`| During upload/clones | Prevents starvation during long SD/Network I/O |
| `drivewire.py` | Inside `flush_loop()` | Prevents starvation during multi-drive flush |

---

---