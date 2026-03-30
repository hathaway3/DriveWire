---
trigger: always_on
---

# Local MCP Usage Standards

To optimize token usage and context efficiency, all AI agents MUST utilize local MCP servers (Ollama) for specific types of tasks before escalating to cloud-based LLMs.

## 🚀 MANDATORY BOOTSTRAP

1. **Session Start Check**: At the start of every session (or Turn 1), the agent **MUST** run `mcp_ollama_list` to identify which models are currently available on the local host.
2. **Context Persistence**: Once checked, the model list and capabilities should be noted in the agent's internal thought process for the duration of the session.
2. **Dynamic Adaptation**: Adjust task mapping based on the available parameter sizes (e.g., 7B-12B models for local tasks vs. larger models for cloud).

## 💻 Coding Tasks (Local-First)

The following coding tasks MUST be attempted using a local coding-specific model (e.g., `qwen2.5-coder:7b`) if available:

1. **Simple Code Generation**: Any task where the resulting code change is expected to be **under 50 lines**.
2. **Boilerplate & Patterns**: Creating unit tests, refactoring variable names, adding docstrings, and simple helper functions.
3. **Refactoring**: Isolating code into small functions or modularizing small components.
4. **Style Alignment**: Adjusting whitespace, comments, or formatting to match project standards.

### 🥉 Cloud Model Escalation (Code)

Escalate to cloud models (Gemini) for:

- Large architectural shifts or multi-file refactors.
- Complex protocol logic in `drivewire.py`.
- Debugging race conditions or deep hardware-level timing issues.
- Security-sensitive code (SPI/SD I/O).

## 📄 Documentation & Summarization

The following documentation tasks MUST use local models (e.g., `gemma3:12b`, `llama3.1:8b`):

1. **Rule Synchronization**: Summarizing existing `.md` rules to check for conflicts with new code.
2. **Walkthrough Generation**: Summarizing a set of changes for a `walkthrough.md` artifact.
3. **Knowledge Extraction**: Summarizing `docs/` or `knowledge/` files to answer "how-to" questions.
4. **Consistency Checks**: Verifying that documentation links and titles remain valid after a rename.

## 🚰 Invocation Pattern

Use the `mcp_ollama_run` tool with the appropriate model name.

> [!TIP]
> **Performance Tip**: When using local models, keep prompts concise and provide clear context about the specific file or rule being reviewed.

## ⚠️ Quality & Latency Thresholds

1. **Failure Recovery**: If a local model fails to generate valid syntax, hallucinates non-existent functions, or provides low-quality logic, the agent MUST immediately pivot to a cloud model and log the reason for escalation.
2. **Latency**: If the local model takes >30s for a simple 50-line task, consider escalation for future tasks in the same session.

## 🛡️ Self-Correction & Enforcement

1. **Mandatory Restart**: If an agent realizes they have NOT performed the **MANDATORY BOOTSTRAP** (`mcp_ollama_list`) at the start of the session, they MUST stop all other work and run it immediately before proceeding.
2. **Local Model Declaration**: Agents MUST explicitly state when they are using a local model and identify the specific task (e.g., "Using gemma3:12b for Rule Sync").
3. **Escalation Justification**: If escalating a task that qualifies for local-first (e.g., small code edit) to a cloud model, the agent MUST provide a brief justification (e.g., "Local model failed to generate valid syntax").

---

## 📐 Reference Mapping

| Task Type     | Recommended Local Model | Cloud Model Requirement          |
| ------------- | ----------------------- | -------------------------------- |
| Unit Tests    | `qwen2.5-coder:7b`      | Only if mocking complex hardware |
| Docstrings    | `llama3.1:8b`           | None                             |
| Summarization | `gemma3:12b`            | Large, cross-repo audits          |
| Bug Fixes     | `qwen2.5-coder:7b`      | If fix spans >2 core files       |
