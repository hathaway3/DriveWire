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

## 📖 Documentation & Readability

1. **Type Hints**: Use standard Python type hints. Use the `try...except ImportError` pattern for `typing` to ensure compatibility and save memory on the device.
2. **Docstrings**: Provide concise docstrings for all public classes and methods.
3. **No Dead Code**: Remove all commented-out code or unused debug prints before merging.
