---
description: How to verify that MicroPython documentation is in sync with the current code
---

This workflow ensures that recent code changes are properly reflected in the project's documentation.

1. **Identify Changes**: Review the files changed in the current task.
2. **Check Documentation Files**: Look for relevant files in `micropython/docs/` and `micropython/README.md`.
3. **Grep for References**: If core logic changed, grep documentation for keywords:
   - `grep_search -i "keyword" micropython/docs/`
4. **Compare Definitions**: Ensure that API endpoints in `docs/api.md` exactly match the routes defined in `web_server.py`.
5. **Verify Wiring**: Ensure wiring tables in `docs/wiring.md` match default pin assignments in `config.py`.
6. **Run Link Check**:
   - `python verify_links.py` (Verify it scans the correct directories)
7. **Document Sync**: Confirm that all changes are described in the final `walkthrough.md`.
