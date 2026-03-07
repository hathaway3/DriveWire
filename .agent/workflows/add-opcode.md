---
description: How to safely add a new DriveWire opcode to the MicroPython server
---

1. **Identify the Opcode**: Check `DriveWire Specification.md` for the command byte and expected payload length.
2. **Define Constant**: Add the opcode to the top of `micropython/drivewire.py` using `micropython.const()`.
3. **Locate Handler**: Search for `DriveWireServer.run` in `drivewire.py`.
4. **Implement logic**:
   - Add an `elif opcode == OP_NEW:` block.
   - Use `self.read_bytes(N)` for input data.
   - Use `self.uart.write(data)` for responses.
   - **MUST**: Call `machine.WDT().feed()` if the operation is blocking.
5. **Verify**: Add a test case to `tests/test_opcodes.py`.
