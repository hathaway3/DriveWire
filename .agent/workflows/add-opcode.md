1. **Identify Opcode**: Check `DriveWire Specification.md` for cmd byte/payload len.
2. **Define Constant**: Add to `micropython/drivewire.py` using `micropython.const()`.
3. **Locate Handler**: Search for `DriveWireServer.run` in `drivewire.py`.
4. **Implement**: Add `elif opcode == OP_NEW:`. Use `read_bytes(N)`, `uart.write()`, and `WDT().feed()`.
5. **Verify**: Add test case to `tests/test_opcodes.py`.
