# Contributing

TaskState Vault is early-stage software. Contributions should keep the project focused on task-state, context, file, and index management for Codex-style agents.

## Development Setup

```powershell
python -m pip install -e .
python -B -m unittest discover -s tests -v
```

## Guidelines

- Keep runtime state out of git.
- Prefer standard-library implementations unless a dependency clearly earns its weight.
- Keep TaskFS, ContextKernel, and TaskDB responsibilities separate.
- Do not add a second permission, sandbox, approval, or network-policy system.
- Update docs when CLI behavior changes.

