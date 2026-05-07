---
trigger: always_on
---

# MicroPython Code Quality Standards

To ensure the DriveWire project remains performant and reliable on the RP2040 and RP2350, all code must adhere to these MicroPython-specific quality standards.

## 💾 Memory Optimization

1. **Use `const()` for Integers**: Always wrap integer constants and bit-flags in `micropython.const()` to save RAM.
   ```python
   from micropython import const
   OP_READ = const(0x52)
   ```
2. **Avoid Large String Concatenation**: Use `f-strings` or `.format()` for simple formatting. For complex logs or long strings, use `write()` directly to a file or stream to avoid large intermediate allocations.
3. **Pre-allocate Buffers**: For any loop doing I/O, pre-allocate a `bytearray` or `memoryview` outside the loop.
4. **Explicit GC**: Call `gc.collect()` after significant memory-intensive operations (e.g., loading a large JSON config or initializing a network interface).
5. **RAM Monitoring**: Use `resilience.log_mem_info(label)` to baseline performance during development and check for leaks in new features.

## ⚡ Performance

1. **Avoid `import` within Loops**: Ensure all necessary modules are imported at the top of the file.
2. **Minimize Global Lookups**: In performance-critical loops (like the UART reader), cache global functions or constants in local variables.
3. **Use `memoryview`**: When slicing large buffers, use `memoryview` to avoid creating copies of the data.

## 🛡️ Resilience & Error Handling

1. **Specific Exceptions**: Never use bare `except:`. Always catch specific errors like `OSError` or `RuntimeError`.
2. **Log Every Exception**: All caught exceptions must be logged using `resilience.log(msg, level=N)`.
3. **Hardware Isolation**: Hardware-interacting code must be wrapped in `try...except` to prevent a single component failure (e.g., a bad SD card) from crashing the entire server.

## 🚰 Async Resilience

1. **Yielding vs. WDT**: `await asyncio.sleep(0)` yields to the scheduler, allowing other tasks (like the UART loop) to run. `resilience.feed_wdt()` only prevents a hardware reset.
2. **High-Latency Loops**: Any loop performing SD or Network I/O MUST call both `await asyncio.sleep(0)` for responsiveness and `resilience.feed_wdt()` for stability.
3. **Non-Blocking I/O**: Use `stream.read()` and `stream.write()` with `await` instead of blocking `file.read()`.

## 📖 Documentation & Readability

1. **Type Hints**: Use standard Python type hints. Use the `try...except ImportError` pattern for `typing` to ensure compatibility and save memory on the device.
2. **Docstrings**: Provide concise docstrings for all public classes and methods.
3. **No Dead Code**: Remove all commented-out code or unused debug prints before merging.

## 🌐 Microdot 1.3.4 Compatibility

The web server uses Microdot 1.3.4 (`microdot_asyncio.py`). Its async `Response.write()` passes `str` bodies directly to MicroPython's `StreamWriter.write()`, which **only accepts `bytes`**. A monkey-patch in `web_server.py` handles this globally, but follow these rules to avoid edge cases:

1. **Never use `Response(body, headers={...})`**: Microdot 1.x does not support the `headers` keyword argument on `Response()` or `send_file()`. Create the Response first, then set headers:
   ```python
   res = Response(body)
   res.headers['Content-Type'] = 'application/json'
   return res
   ```
2. **Never use async generators for Response bodies**: Microdot 1.3.4 only iterates sync generators (`__next__`). Async generators (`async def` with `yield`) silently fall through to the `else` write branch and crash. For small responses (<4KB), return a dict or build the JSON in memory. For large responses, use a sync generator.
3. **Prefer returning dicts**: Let Microdot handle `json.dumps()` automatically. The monkey-patch encodes the resulting `str` body to `bytes`.
4. **`collections.deque` has no slicing**: MicroPython's `deque` does not support `deque[idx:]`. Use manual iteration (see `_deque_to_list()` helper in `web_server.py`).
5. **No `os.path` module**: Use `os.stat()` for existence checks, manual `.split('/')` for path manipulation.
6. **`import asyncio` → `import uasyncio as asyncio`**: MicroPython uses `uasyncio`, not `asyncio`.

## 📐 Microdot Compatibility Reference

| Pattern | Status | Alternative |
|---------|--------|-------------|
| `Response(body, headers={})` | ❌ Forbidden | `res = Response(body); res.headers[k] = v` |
| `send_file(path, headers={})` | ❌ Forbidden | `res = send_file(path); res.headers[k] = v` |
| `async def gen(): yield ...` as Response body | ❌ Forbidden | Use sync generator or return dict |
| `deque[idx:]` | ❌ Forbidden | `_deque_to_list(dq, skip=idx)` |
| `os.path.exists()` / `os.path.basename()` | ❌ Forbidden | `resilience.file_exists()` / `.split('/')[-1]` |
| `import asyncio` | ❌ Forbidden | `import uasyncio as asyncio` |
