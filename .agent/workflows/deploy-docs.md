1. **Modify Content**: Update `.md` in `micropython/docs/` or `README.md`.
2. **Relative Links**: **REQUIRED**. Use `[doc](docs/file.md)`.
3. **Verify Links**: // turbo
   `python verify_links.py`
4. **Preview**: `mkdocs serve` -> `http://127.0.0.1:8000`.
5. **Protocol Sync**: Update `drivewire_codebase.md` if protocol changed.
