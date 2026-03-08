---
description: How to safely update documentation and verify link integrity
---

1. **Modify Content**: Update the relevant `.md` files in `micropython/docs/` or the root `README.md`.
2. **Relative Link Requirement**:
   - **IMPORTANT**: Always use relative paths for internal links to ensure compatibility with GitHub Pages.
   - Example: `[Wiring Documentation](docs/wiring.md)` instead of `/docs/wiring.md`.
3. **Verify Links**:
   // turbo
   `python verify_links.py`
4. **MkDocs Preview (Optional)**:
   - If `mkdocs` is installed on the host:
     `mkdocs serve`
   - Check `http://127.0.0.1:8000` to see the rendered site.
5. **Protocol Sync**: If the change affects a protocol feature, ensure `drivewire_codebase.md` is also updated.
