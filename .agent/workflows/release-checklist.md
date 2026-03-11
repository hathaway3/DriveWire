---
description: Final checklist before a release or major commit.
---

# Release & Finalization Checklist

Complete this checklist before finalizing a task boundary or pushing changes to the main repository.

## 🏗️ Code Health
- [ ] All code adheres to [code-quality.md](../rules/code-quality.md).
- [ ] No unused imports or debug `print()` statements remain.
- [ ] `gc.collect()` is called after large allocations.

## 🧪 Testing Verify
- [ ] All host-side unit tests pass: `python -m unittest discover tests`.
- [ ] On-device verification completed for hardware changes.
- [ ] Memory baseline checked: `resilience.log_mem_info("Pre-Release")`.

## 📖 Documentation Sync
- [ ] All new features documented in `docs/`.
- [ ] Internal links updated and verified with `verify_links.py`.
- [ ] `mkdocs.yml` updated if new pages were added.
- [ ] [drivewire_codebase.md](../knowledge/drivewire_codebase.md) reflects current state.

## 🛡️ Security & Performance
- [ ] Path traversal protections verified for any new file I/O.
- [ ] Background tasks yield correctly with `await asyncio.sleep(0)`.
- [ ] Watchdog is fed in all new loops.

## 🚀 Final Snapshot
- [ ] `walkthrough.md` created with proof of work.
- [ ] System log checked for any unexpected errors or warnings during verification.
