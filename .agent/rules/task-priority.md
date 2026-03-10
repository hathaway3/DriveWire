# Task Priority & Non-Blocking Resilience

To ensure that the DriveWire server remains responsive to the CoCo (guest computer), follow these rules regarding task priority and cooperative multitasking.

## 🥇 Protocol Priority

1. **Serial First**: Handing UART serial requests for the DriveWire protocol (`DriveWireServer.run`) is the absolute highest priority. 
2. **Background Tasks**: The following are considered "non-essential" background tasks and must be lower priority:
   - Web interface processing (Microdot)
   - Disk image uploads (`upload_file_endpoint`)
   - Blank disk creation (`create_blank_dsk_endpoint`)
   - Disk cloning (`remote_clone_endpoint`)
   - Config saving (`config.save()`)
   - Disk deletion or filesystem repairs.

## 🚰 Cooperative Multitasking (Yielding)

1. **Frequent Yields**: Any loop in a background task that performs I/O or heavy computation **MUST** call `await asyncio.sleep(0)` frequently.
   - **Uploads/Clones**: Yield after every 4KB chunk (or smaller if necessary for high baud rates).
   - **Iterators**: Yield after every substantial iteration (e.g., scanning large directories).
2. **No Synchronous Blocking**: Avoid `time.sleep()` or `utime.sleep()` in any task; use `await asyncio.sleep()` or `await asyncio.sleep_ms()`.
3. **Watchdog Feeding**: Always feed the watchdog (`resilience.feed_wdt()`) in long-running loops, but remember that feeding the WDT does NOT yield to other tasks.

## 💾 Filesystem & I/O Safety

1. **Avoid `os.sync()` in Loops**: Minimize calls to `os.sync()` in background tasks. While it ensures data integrity, it is a heavy blocking operation that can stall the UART loop.
   - **Logging**: Do not sync the filesystem on every log line in production if high performance is required.
2. **Atomic Writes**: Perform config saves and file renames quickly. For large file operations (creating/cloning), ensure the yielding logic is strictly followed.
3. **Memory Management**: Run `gc.collect()` strategically. Avoid large, frequent garbage collections in background tasks that might cause long "stop-the-world" pauses. Use `resilience.collect_garbage(reason)` which logs the duration/effect.
