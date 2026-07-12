# Contributing

TaskState Vault is early-stage software. Contributions should keep the project focused on task-state, context, file, and index management for Codex-style agents.

## Development Setup

```powershell
python -m pip install -e ".[dev]"
ruff check taskstate_vault tests scripts
python -B -m unittest discover -s tests -v
cd frontend
npm ci
npm test
npm run build
```

## Guidelines

- Keep runtime state out of git.
- Prefer standard-library implementations unless a dependency clearly earns its weight.
- Keep TaskFS, ContextKernel, and TaskDB responsibilities separate.
- Keep one console permission model and one explicit loopback/network exposure boundary; do not duplicate either in feature code.
- Update docs when CLI behavior changes.

