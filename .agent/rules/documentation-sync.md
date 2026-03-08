---
trigger: always_on
---
# Documentation Synchronization Rule

To ensure that the DriveWire codebase and its documentation remain in sync, follow these rules whenever code is modified.

## 📋 Synchronization Requirements

1. **Verify Affected Docs**: Before completing any code change, identify which documentation files are impacted.
2. **Update README**: If a feature's high-level usage or installation steps change, update `micropython/README.md`.
3. **Update Technical Docs**:
    - **API Changes**: If any REST endpoints or data formats change, update `micropython/docs/api.md`.
    - **Hardware Changes**: If GPIO pins or wiring requirements change, update `micropython/docs/wiring.md`.
    - **Protocol/Remote Changes**: If remote sector server or cloning logic changes, update `micropython/docs/remote_drives.md`.
4. **Link Integrity**: Ensure all cross-links between documentation files remain valid. Use standard relative paths.

## 🛠️ Verification Workflow

1. **Grep for Keywords**: Search for code-related terms in the `docs/` folder to ensure no mentions were missed.
2. **Read Docs**: Perform a quick read of the updated documentation to ensure it remains readable and matches the new code behavior.
3. **Run Verification**: If available, use tools like `verify_links.py` to check for broken links.

## 🤝 Atomic Commits

Try to include documentation updates in the **same commit** or task boundary as the code changes. Never leave "doc updates" for a later task unless explicitly instructed.
