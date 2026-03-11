---
description: How to safely develop and implement new DriveWire features or opcodes.
---

# Feature Development Workflow

Follow this workflow whenever adding new opcodes, REST API endpoints, or core features to the DriveWire project.

## 1. Impact Assessment
- [ ] Determine if the feature requires a new opcode (DriveWire protocol) or a new API endpoint (Web UI).
- [ ] Evaluate memory impact (Heap usage/Fragmentation).
- [ ] Check if the operation will block for >1s (If yes, WDT feeding is REQUIRED).

## 2. Implementation Phase
- [ ] Implement core logic in the appropriate module (`drivewire.py`, `web_server.py`, etc.).
- [ ] Adhere to [code-quality.md](../rules/code-quality.md).
- [ ] Use `resilience.log()` for all new state transitions or errors.
- [ ] Ensure any new background task yields using `await asyncio.sleep(0)`.

## 3. Verification Phase
- [ ] Write a host-side unit test in `micropython/tests/`.
- [ ] Perform hardware verification on the Pico if hardware is involved.
- [ ] Verify that the change does not adversely affect UART responsiveness.

## 4. Documentation Phase
- [ ] Update `micropython/docs/api.md` for new REST endpoints.
- [ ] Update `DriveWire Specification.md` for any protocol changes.
- [ ] Update [drivewire_codebase.md](../knowledge/drivewire_codebase.md) if the architecture changes.
- [ ] Run `python verify_links.py` to ensure documentation integrity.

## 5. Peer Review Ready
- [ ] Create a `walkthrough.md` artifact showing the feature in action.
- [ ] Include any relevant logs or screenshots.
