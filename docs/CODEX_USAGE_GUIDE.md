# Codex Usage Guide For TaskState Vault

## Fixed Entry

At the start of each task, read this file from the cloned repository:

```text
<TASKSTATE_VAULT_REPO>/docs/CODEX_USAGE_GUIDE.md
```

Use the cloned repository path as the central TaskState Vault root:

```text
<TASKSTATE_VAULT_REPO>
```

Run the CLI from that root:

```powershell
cd <TASKSTATE_VAULT_REPO>
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> <command>
```

The current working directory is only the project/source/data workspace for the current task. It is not the discovery location for this guide. Project-level source files and task artifacts may live outside the central root, but those workspaces must be registered into the central index.

## Layer Names

```text
TaskState Vault:
  The overall project and user-facing tool.

ContextKernel:
  Execution modes, Project Governor, task graph, execution queue,
  objective changes, run state, and context loading.

TaskFS:
  .taskstate-vault files for account, domain, project, task, and run state.

TaskDB:
  SQLite indexes, FTS, pointers, import-copy records, and project-file indexes.
```

## Startup Steps

```text
1. Read this fixed usage guide.
2. Use <TASKSTATE_VAULT_REPO> as the account-level and global index root.
3. If the central root is not initialized, run init.
4. Read .taskstate-vault/SYSTEM/ENTRYPOINT.md.
5. Read .taskstate-vault/ACCOUNT/PROFILE/initial_state.yaml.
6. Detect execution_mode.
7. Keep simple_task lightweight; use task state for managed_task; use Project Governor for complex_project/program_scale.
8. If the current workspace participates in the task, register it; for complex tasks, initialize a task workspace link.
9. Search task/project/domain/account indexes and copy useful long-term information into task scope.
10. After work, write back task, run, project, index, and queue state.
```

Initialize the central root:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> init
```

## Execution Modes

```text
simple_task:
  Short, clear, single-step or few-step work. Keep it lightweight.

managed_task:
  Needs continuing state, evidence, errors, or artifacts, but is not a complex project.

complex_project:
  Multi-module, multi-stage, long-running, dependency-heavy, or easy to drift.
  Use Project Governor.

program_scale:
  Multi-project, multi-workflow, roadmap-like work with cross-project dependencies.
```

## Central Index And Workspaces

Create a complex project and bind it to a real source workspace:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> project create --title "<project title>" --mode complex_project --project-id <project_id> --workspace <PROJECT_WORKSPACE>
```

This updates:

```text
.taskstate-vault/kernel.sqlite
.taskstate-vault/project_registry.jsonl
.taskstate-vault/PROJECTS/<project_id>/
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/project_refs.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/workspace_refs.jsonl
.taskstate-vault/ACCOUNT/ACCOUNT_INDEX/account.sqlite
```

Register an existing external workspace:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> workspace register --workspace <PROJECT_WORKSPACE> --project <project_id> --summary "<purpose>"
```

Create a task-level TaskFS link in a workspace:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> workspace init-task --workspace <PROJECT_WORKSPACE> --project <project_id> --task <task_id> --summary "<task workspace>"
```

Index source files into the project TaskDB:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> index project-files --project <project_id> --path <PROJECT_WORKSPACE>
```

Record an important artifact:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> artifact add --project <project_id> --task <task_id> --path <artifact_path> --summary "<artifact summary>"
```

## Account-Level Information

Global reusable information from user context should be stored at account layer and indexed.

Common account-level types:

```text
VPS configs
local machine parameters
email accounts
service accounts
long-term user preferences
stable constraints
global tools
global templates
long-term playbooks
project references
workspace references
```

Storage slots:

```text
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/vps_configs.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/local_machines.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/email_accounts.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/service_accounts.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/user_preferences.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/stable_constraints.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/tool_manifests.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/templates.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/playbooks.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/project_refs.jsonl
.taskstate-vault/ACCOUNT/GLOBAL_OBJECTS/workspace_refs.jsonl
.taskstate-vault/ACCOUNT/ACCOUNT_INDEX/account.sqlite
```

Examples:

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> account add --type vps_config --summary "VPS build host" --content "host=... user=... purpose=..." --tag vps --tag build
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> account add --type local_machine --summary "Windows workstation" --content "cpu=... ram=... path=..." --tag local_machine
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> account search --query vps
```

## Layered Indexes And Pointers

```text
Account objects
  -> ACCOUNT/ACCOUNT_INDEX/account.sqlite
  -> pointer: tsv://account/<object_id>

Domain objects
  -> DOMAINS/<domain_id>/DOMAIN_INDEX/domain.sqlite
  -> pointer: tsv://domain/<domain_id>/<object_id>

Project objects
  -> PROJECTS/<project_id>/PROJECT_INDEX/project.sqlite
  -> pointer: tsv://project/<project_id>/<object_id>

Task objects
  -> TASKS/<task_id>/INDEX/task.sqlite
  -> local object or copied object

Run records
  -> TASKS/<task_id>/RUNS/<run_id>/
  -> root run registry and task run state
```

Search order:

```text
task index
project index
domain index
account index
```

Useful long-term information should be copied into task scope and keep its source pointer.

```powershell
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> layer import-account --query vps --project <project_id> --task <task_id> --reason "current task needs build host config"
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> layer import-domain --domain general --query playbook --project <project_id> --task <task_id> --reason "current task needs domain experience"
```

Task-level copies are stored in:

```text
TASKS/<task_id>/OBJECTS/layer_imports.jsonl
TASKS/<task_id>/OBJECTS/resources.jsonl
TASKS/<task_id>/INDEX/task.sqlite
```

## Complex Project Required Reads

```text
PROJECT_INTENT.yaml
PROJECT_MODEL.yaml
PROJECT_PROGRESS.yaml
GOVERNOR/TASK_GRAPH.jsonl
GOVERNOR/EXECUTION_QUEUE.jsonl
GOVERNOR/BLOCKERS.jsonl
GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl
current TASK_STATE.yaml
current NEXT_ACTION.md
task-level layer_imports.jsonl
```

## Complex Project Loop

```text
1. Read account initial state and this guide.
2. Read PROJECT_INTENT and confirm the top-level objective.
3. Read PROJECT_PROGRESS.
4. Read EXECUTION_QUEUE and choose the best current task.
5. Read relevant TASK_GRAPH subgraph.
6. Search task/project/domain/account indexes.
7. Copy useful long-term information into task scope.
8. Open current TASK_STATE and NEXT_ACTION.
9. Do the work.
10. Record evidence, artifacts, errors, and decisions.
11. Update task graph node status.
12. Write OBJECTIVE_CHANGE_LOG if the task objective changed.
13. Update PROJECT_PROGRESS.
14. Reschedule EXECUTION_QUEUE.
15. Update NEXT_ACTION.
16. Sync project file indexes and key artifact indexes.
```

## Objective Changes

Stable:

```text
PROJECT_INTENT
```

Dynamically adjustable:

```text
TASK_OBJECTIVE
TASK_GRAPH
EXECUTION_QUEUE
PROJECT_PROGRESS
```

Allowed changes:

```text
split
merge
defer
replace path
bypass blocker
insert new task
```

Required record:

```text
GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl
```

## Writeback Rules

```text
simple_task:
  Record only necessary results.

managed_task:
  Update TASK_STATE.
  Update NEXT_ACTION.
  Record evidence/artifact/error as needed.
  Sync project files if relevant.

complex_project:
  Update TASK_STATE.
  Update NEXT_ACTION.
  Record run.
  Record evidence/artifact/error.
  Update TASK_GRAPH.
  Update BLOCKERS.
  Update PROJECT_PROGRESS.
  Reschedule EXECUTION_QUEUE.
  Write OBJECTIVE_CHANGE_LOG when needed.
  Sync workspace/project file indexes.
  Propose promotion candidates when useful.
```

## Operating Principles

```text
Do not downgrade complex projects into short toy tasks.
Do not replace project state with chat history.
Do not silently change PROJECT_INTENT.
Do not write errors into facts.
Do not keep useful account-level information only in the chat context.
Do copy useful long-term information into task scope and preserve source pointers.
The current working directory is not necessarily the central root.
Register external workspaces in the central index.
Sync indexes when projects, workspaces, or project files change.
TaskState Vault does not replace Codex native execution capabilities.
```

