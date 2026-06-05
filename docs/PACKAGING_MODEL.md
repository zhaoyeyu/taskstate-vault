# Packaging Model

TaskState Vault is packaged as four public surfaces over one local state system:

```text
TaskStateVault
  Unified Python SDK entry point.

CLI
  `tsv` and `taskstate-vault` command-line entry points for Codex, scripts, and manual automation.

Local read-only Web UI
  Browser dashboard for inspecting TaskFS and TaskDB without opening files by hand.

MCP-ready adapter
  Stable JSON-callable tool functions and tool metadata for an MCP wrapper.

TaskFS / TaskDB / ContextKernel
  Core public library facades for filesystem state, indexes, and execution governance.
```

## Python SDK

```python
from taskstate_vault import TaskStateVault

vault = TaskStateVault("<TASKSTATE_VAULT_REPO>")
vault.init()
project = vault.contextkernel.create_project(
    "Complex project",
    execution_mode="complex_project",
    project_id="project_demo",
    workspace_path="<PROJECT_WORKSPACE>",
)
task = vault.contextkernel.create_task_from_queue(project["project_id"])
vault.taskdb.add_account_object("tool", "Build tool", "name=builder", tags=["build"])
context = vault.contextkernel.build_context(project["project_id"], task["task_id"])
```

Direct facades are also available:

```python
from taskstate_vault import ContextKernel, TaskDB, TaskFS

taskfs = TaskFS("<TASKSTATE_VAULT_REPO>")
taskdb = TaskDB("<TASKSTATE_VAULT_REPO>")
kernel = ContextKernel("<TASKSTATE_VAULT_REPO>")
```

## CLI

```powershell
tsv --root <TASKSTATE_VAULT_REPO> init
tsv --root <TASKSTATE_VAULT_REPO> project create --title "Complex project" --mode complex_project --project-id project_demo --workspace <PROJECT_WORKSPACE>
tsv --root <TASKSTATE_VAULT_REPO> task create --project project_demo
tsv --root <TASKSTATE_VAULT_REPO> context build --project project_demo --task <TASK_ID>
```

## Local UI

```powershell
tsv --root <TASKSTATE_VAULT_REPO> ui serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`.

The UI is read-only. It shows account object counts, workspace references, projects, task graph size, queue size, blockers, objective changes, task states, run counts, and selected TaskFS file previews.

## MCP-Ready Adapter

The adapter intentionally has no hard dependency on a specific MCP SDK.

```python
from taskstate_vault.mcp_adapter import call_tool, list_tool_specs

tools = list_tool_specs()
context = call_tool(
    "tsv_get_startup_context",
    {"project_id": "project_demo", "task_id": "<TASK_ID>"},
    root="<TASKSTATE_VAULT_REPO>",
)
```

Wrappers can expose `list_tool_specs()` as their MCP tool schema source and route tool calls to `call_tool()`.

## Core Library Boundaries

TaskFS owns:

- `.taskstate-vault` initialization
- workspace registration
- task workspace link creation
- status over TaskFS paths

TaskDB owns:

- account and domain object indexes
- layered search
- task-level imports of long-term information
- project-file indexing
- index rebuilds

ContextKernel owns:

- execution mode detection
- Project Governor
- project intent/model
- task graph and execution queue
- task instance lifecycle
- run lifecycle
- evidence, artifacts, errors, and context loading
