# TaskState Vault

TaskState Vault is a local task-state, context, filesystem, SQLite index, local UI, and adapter layer for Codex-style agents working on complex or long-running projects.

It helps an agent keep track of project intent, task graphs, execution queues, task-local state, evidence, artifacts, errors, and reusable account/domain information. It does not replace Codex command execution, file editing, browser usage, approval modes, sandboxing, or network permissions.

## Core Names

```text
TaskState Vault:
  The overall project and user-facing tool.

ContextKernel:
  Execution-mode routing, Project Governor, task graph, execution queue,
  objective changes, run state, and context loading.

TaskFS:
  The on-disk state layout under .taskstate-vault.

TaskDB:
  SQLite indexes for account, domain, project, task, pointer, import-copy,
  and project-file search records.
```

## Install

Clone the repository, then install it in editable mode:

```powershell
git clone <your-fork-or-repo-url> taskstate-vault
cd taskstate-vault
python -m pip install -e .
```

You can also run it without installing:

```powershell
python -m taskstate_vault.cli.main --help
```

## Quick Start

Use the cloned repository path as the central TaskState Vault root:

```powershell
cd <TASKSTATE_VAULT_REPO>
tsv --root <TASKSTATE_VAULT_REPO> init
tsv --root <TASKSTATE_VAULT_REPO> project create --title "My Complex Project" --mode complex_project --project-id project_demo --workspace <PROJECT_WORKSPACE>
tsv --root <TASKSTATE_VAULT_REPO> governor next --project project_demo
tsv --root <TASKSTATE_VAULT_REPO> task create --project project_demo --queue-rank 1
tsv --root <TASKSTATE_VAULT_REPO> workspace init-task --workspace <PROJECT_WORKSPACE> --project project_demo --task <TASK_ID>
tsv --root <TASKSTATE_VAULT_REPO> index project-files --project project_demo --path <PROJECT_WORKSPACE>
tsv --root <TASKSTATE_VAULT_REPO> context build --project project_demo --task <TASK_ID>
```

Installed script names:

```text
tsv
taskstate-vault
```

Start the local read-only UI:

```powershell
tsv --root <TASKSTATE_VAULT_REPO> ui serve
```

The UI shows the account index, workspace references, projects, task graph size, execution queue size, blockers, objective changes, task states, run counts, and direct previews of TaskFS files.

Python SDK:

```python
from taskstate_vault import TaskStateVault

vault = TaskStateVault("<TASKSTATE_VAULT_REPO>")
vault.init()
project = vault.contextkernel.create_project("My Complex Project", execution_mode="complex_project", project_id="project_demo")
task = vault.contextkernel.create_task_from_queue(project["project_id"])
context = vault.contextkernel.build_context(project["project_id"], task["task_id"])
```

MCP-ready adapter:

```powershell
tsv --root <TASKSTATE_VAULT_REPO> mcp tools
```

## Codex Setup

TaskState Vault is most useful when Codex is told where to find its startup guide.

1. Clone this repository.
2. Replace `<TASKSTATE_VAULT_REPO>` in [docs/CODEX_CUSTOM_INSTRUCTIONS_DRAFT.md](docs/CODEX_CUSTOM_INSTRUCTIONS_DRAFT.md) with the absolute path to your clone.
3. Put the resulting text in Codex custom instructions.
4. Keep [docs/CODEX_USAGE_GUIDE.md](docs/CODEX_USAGE_GUIDE.md) in the repository so Codex can read the operational protocol at task start.

## Repository Structure

```text
taskstate_vault/
  Public Python package, CLI, TaskFS, ContextKernel, TaskDB, MCP adapter, and UI implementation.

docs/
  Usage guide, custom-instruction template, structure reference, and initial guidance.

tests/
  End-to-end flow tests using temporary TaskFS roots.

pyproject.toml
  Package metadata and CLI entry points.
```

Runtime state is created under `.taskstate-vault/` and is intentionally ignored by git.

## Current Capabilities

- Execution modes: `simple_task`, `managed_task`, `complex_project`, `program_scale`
- Project Governor
- Project intent and project model files
- Task graph and execution queue scheduling
- Account/domain/project/task layered indexes
- `tsv://` pointer URIs
- Task-level copies of relevant long-term information
- Task state and next action files
- Run start/record/finish
- Evidence, artifacts, errors, and object records
- Project file indexing
- Context build/explain
- Local read-only UI
- Public Python SDK facades: `TaskStateVault`, `TaskFS`, `TaskDB`, `ContextKernel`
- MCP-ready JSON-callable adapter and tool metadata
- Objective change log
- Promotion candidates
- Final audit and initial guidance generation

## Tests

```powershell
python -B -m unittest discover -s tests -v
```

## Documentation

- [Codex usage guide](docs/CODEX_USAGE_GUIDE.md)
- [Product guide / 产品说明](docs/PRODUCT_GUIDE_ZH_EN.md)
- [Custom instructions draft](docs/CODEX_CUSTOM_INSTRUCTIONS_DRAFT.md)
- [Project structure](docs/PROJECT_STRUCTURE.md)
- [Packaging model](docs/PACKAGING_MODEL.md)
- [Initial guidance](docs/INITIAL_GUIDANCE.md)

## License

MIT. See [LICENSE](LICENSE).

