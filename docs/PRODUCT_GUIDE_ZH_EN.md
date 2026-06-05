# TaskState Vault Product Guide / 产品说明

## Part 1: What TaskState Vault Does / 第一部分：最快理解 TaskState Vault 能做什么

### 中文

TaskState Vault 是给 Codex、Claude Code、Cursor、Gemini CLI 等编程 agent 使用的本地任务状态与项目治理系统。它的目标不是替代 agent 写代码，而是让 agent 在复杂项目中拥有更稳定的长期状态、项目结构、任务队列、执行记录和上下文索引。

当一个任务很简单时，TaskState Vault 可以保持轻量；当一个任务变成复杂项目时，它会帮助 agent 先建立项目意图、项目模型、任务图、执行队列、当前任务、运行记录、证据、产物和错误记录，再按优先级推进，而不是把大型目标压缩成一次粗糙实现。

TaskState Vault 可以帮助用户和 agent：

- 保存账户级、领域级、项目级、任务级、运行级信息。
- 把复杂项目拆成任务图和执行队列。
- 记录每次运行的结果、证据、产物和错误。
- 在任务之间保留长期有用的信息。
- 把账户/领域/项目中的相关信息复制到当前任务范围，避免只依赖聊天上下文。
- 通过 SQLite 和 JSONL 建立可检索索引。
- 通过本地只读 Web UI 查看项目、任务、队列、索引和过程内容。
- 通过 CLI、Python SDK 和 MCP-ready adapter 给不同 agent 或自动化工具使用。

一句话概括：TaskState Vault 是一个本地优先的 agent 项目状态库，让 AI 编程助手在长期复杂项目中更像项目经理、技术负责人和持续执行者，而不是只处理一次性指令的临时助手。

### English

TaskState Vault is a local task-state and project-governance system for coding agents such as Codex, Claude Code, Cursor, Gemini CLI, and similar tools. It is not designed to replace the agent that writes code. It gives agents persistent structure: long-term state, project models, task queues, execution records, and searchable context.

For small tasks, TaskState Vault can stay lightweight. For complex projects, it helps the agent create project intent, project model, task graph, execution queue, current task state, run records, evidence, artifacts, and error logs before implementation starts. This prevents large goals from being compressed into one rough pass.

TaskState Vault helps users and agents:

- Store account-level, domain-level, project-level, task-level, and run-level information.
- Decompose complex projects into task graphs and execution queues.
- Record run outcomes, evidence, artifacts, and errors.
- Preserve reusable information across tasks.
- Copy relevant account/domain/project knowledge into task scope instead of relying only on chat history.
- Build searchable SQLite and JSONL indexes.
- Inspect projects, tasks, queues, indexes, and process history through a local read-only Web UI.
- Integrate through CLI, Python SDK, and an MCP-ready adapter.

In one sentence: TaskState Vault is a local-first project-state vault for AI coding agents, helping them act more like project managers, technical leads, and persistent executors in long-running complex projects.

## Part 2: How to Use TaskState Vault / 第二部分：详细使用方法

### 1. Installation / 安装

中文：

克隆仓库并安装：

```powershell
git clone <TASKSTATE_VAULT_REPO_URL> taskstate-vault
cd taskstate-vault
python -m pip install -e .
```

也可以不安装，直接使用模块入口：

```powershell
python -m taskstate_vault.cli.main --help
```

English:

Clone the repository and install it:

```powershell
git clone <TASKSTATE_VAULT_REPO_URL> taskstate-vault
cd taskstate-vault
python -m pip install -e .
```

You can also run it without installation:

```powershell
python -m taskstate_vault.cli.main --help
```

### 2. Initialize a TaskState Vault Root / 初始化 TaskState Vault 根目录

中文：

选择一个目录作为中央 TaskState Vault 根目录，然后初始化：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> init
```

初始化后会创建 `.taskstate-vault/`，其中包括系统协议、账户层信息、领域层信息、项目注册表、SQLite 索引等。

English:

Choose a directory as the central TaskState Vault root and initialize it:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> init
```

This creates `.taskstate-vault/`, including system protocols, account-level data, domain-level data, project registries, and SQLite indexes.

### 3. Create a Complex Project / 创建复杂项目

中文：

创建项目并绑定真实项目工作目录：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> project create `
  --title "My Complex Project" `
  --mode complex_project `
  --project-id project_demo `
  --workspace <PROJECT_WORKSPACE>
```

该命令会创建项目级结构，并在复杂项目模式下初始化 Project Governor，包括：

- `PROJECT_INTENT.yaml`
- `PROJECT_MODEL.yaml`
- `PROJECT_PROGRESS.yaml`
- `GOVERNOR/TASK_GRAPH.jsonl`
- `GOVERNOR/EXECUTION_QUEUE.jsonl`
- `GOVERNOR/BLOCKERS.jsonl`
- `GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl`

English:

Create a project and bind it to the real project workspace:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> project create `
  --title "My Complex Project" `
  --mode complex_project `
  --project-id project_demo `
  --workspace <PROJECT_WORKSPACE>
```

This creates project-level state and initializes Project Governor for complex projects, including:

- `PROJECT_INTENT.yaml`
- `PROJECT_MODEL.yaml`
- `PROJECT_PROGRESS.yaml`
- `GOVERNOR/TASK_GRAPH.jsonl`
- `GOVERNOR/EXECUTION_QUEUE.jsonl`
- `GOVERNOR/BLOCKERS.jsonl`
- `GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl`

### 4. Select and Create the Current Task / 选择并创建当前任务

中文：

查看当前最优先任务：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> governor next --project project_demo
```

从执行队列创建任务实例：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> task create --project project_demo --queue-rank 1
```

English:

Check the highest-priority ready task:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> governor next --project project_demo
```

Create a task instance from the execution queue:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> task create --project project_demo --queue-rank 1
```

### 5. Register a Workspace and Index Files / 注册工作区并索引文件

中文：

将外部项目目录登记到账户级索引：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> workspace register `
  --workspace <PROJECT_WORKSPACE> `
  --project project_demo `
  --summary "Project source workspace"
```

为当前任务创建本地链接结构：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> workspace init-task `
  --workspace <PROJECT_WORKSPACE> `
  --project project_demo `
  --task <TASK_ID>
```

索引项目文件：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> index project-files `
  --project project_demo `
  --path <PROJECT_WORKSPACE>
```

English:

Register an external project directory in the account-level index:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> workspace register `
  --workspace <PROJECT_WORKSPACE> `
  --project project_demo `
  --summary "Project source workspace"
```

Create a local task workspace link:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> workspace init-task `
  --workspace <PROJECT_WORKSPACE> `
  --project project_demo `
  --task <TASK_ID>
```

Index project files:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> index project-files `
  --project project_demo `
  --path <PROJECT_WORKSPACE>
```

### 6. Store and Import Reusable Information / 存储并导入可复用信息

中文：

添加账户级长期信息：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> account add `
  --type tool `
  --summary "Build tool" `
  --content "name=builder; purpose=build automation" `
  --tag build
```

搜索账户级信息：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> account search --query build
```

把相关账户级信息复制到当前任务：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> layer import-account `
  --query build `
  --project project_demo `
  --task <TASK_ID> `
  --reason "Current task needs build automation context"
```

English:

Add reusable account-level information:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> account add `
  --type tool `
  --summary "Build tool" `
  --content "name=builder; purpose=build automation" `
  --tag build
```

Search account-level information:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> account search --query build
```

Copy relevant account-level information into the current task:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> layer import-account `
  --query build `
  --project project_demo `
  --task <TASK_ID> `
  --reason "Current task needs build automation context"
```

### 7. Record Runs, Evidence, Artifacts, and Errors / 记录运行、证据、产物和错误

中文：

启动运行：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> run start --project project_demo --task <TASK_ID>
```

记录证据：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> evidence add `
  --project project_demo `
  --task <TASK_ID> `
  --kind command_output `
  --text "Tests passed"
```

记录产物：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> artifact add `
  --project project_demo `
  --task <TASK_ID> `
  --path <ARTIFACT_PATH> `
  --summary "Generated build report"
```

完成运行：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> run finish <RUN_ID> `
  --project project_demo `
  --task <TASK_ID> `
  --status success `
  --summary "Task completed"
```

English:

Start a run:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> run start --project project_demo --task <TASK_ID>
```

Record evidence:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> evidence add `
  --project project_demo `
  --task <TASK_ID> `
  --kind command_output `
  --text "Tests passed"
```

Record an artifact:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> artifact add `
  --project project_demo `
  --task <TASK_ID> `
  --path <ARTIFACT_PATH> `
  --summary "Generated build report"
```

Finish a run:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> run finish <RUN_ID> `
  --project project_demo `
  --task <TASK_ID> `
  --status success `
  --summary "Task completed"
```

### 8. Build Context for an Agent / 为 Agent 构建上下文

中文：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> context build --project project_demo --task <TASK_ID>
```

该命令会根据执行模式加载相应上下文，例如项目意图、项目模型、执行队列、任务状态、下一步动作和任务级导入信息。

English:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> context build --project project_demo --task <TASK_ID>
```

This loads context according to the execution mode, including project intent, project model, execution queue, task state, next action, and task-level imported information.

### 9. Use the Local Read-Only Web UI / 使用本地只读 Web UI

中文：

启动 UI：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> ui serve --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```

UI 可以查看账户对象、workspace 引用、项目、任务图数量、队列数量、阻塞项、目标变更、任务状态、运行数量和 TaskFS 文件预览。

English:

Start the UI:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> ui serve --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

The UI shows account objects, workspace references, projects, task graph size, queue size, blockers, objective changes, task states, run counts, and TaskFS file previews.

### 10. Use the Python SDK / 使用 Python SDK

中文：

```python
from taskstate_vault import TaskStateVault

vault = TaskStateVault("<TASKSTATE_VAULT_ROOT>")
vault.init()

project = vault.contextkernel.create_project(
    "My Complex Project",
    execution_mode="complex_project",
    project_id="project_demo",
    workspace_path="<PROJECT_WORKSPACE>",
)

task = vault.contextkernel.create_task_from_queue(project["project_id"])
vault.taskdb.add_account_object("tool", "Build tool", "name=builder", tags=["build"])
context = vault.contextkernel.build_context(project["project_id"], task["task_id"])
```

English:

```python
from taskstate_vault import TaskStateVault

vault = TaskStateVault("<TASKSTATE_VAULT_ROOT>")
vault.init()

project = vault.contextkernel.create_project(
    "My Complex Project",
    execution_mode="complex_project",
    project_id="project_demo",
    workspace_path="<PROJECT_WORKSPACE>",
)

task = vault.contextkernel.create_task_from_queue(project["project_id"])
vault.taskdb.add_account_object("tool", "Build tool", "name=builder", tags=["build"])
context = vault.contextkernel.build_context(project["project_id"], task["task_id"])
```

### 11. Use the MCP-Ready Adapter / 使用 MCP-ready Adapter

中文：

查看可包装成 MCP 工具的 JSON 工具清单：

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> mcp tools
```

Python 调用：

```python
from taskstate_vault.mcp_adapter import call_tool, list_tool_specs

tools = list_tool_specs()
context = call_tool(
    "tsv_get_startup_context",
    {"project_id": "project_demo", "task_id": "<TASK_ID>"},
    root="<TASKSTATE_VAULT_ROOT>",
)
```

English:

List JSON-callable tools that can be wrapped by an MCP server:

```powershell
tsv --root <TASKSTATE_VAULT_ROOT> mcp tools
```

Python call:

```python
from taskstate_vault.mcp_adapter import call_tool, list_tool_specs

tools = list_tool_specs()
context = call_tool(
    "tsv_get_startup_context",
    {"project_id": "project_demo", "task_id": "<TASK_ID>"},
    root="<TASKSTATE_VAULT_ROOT>",
)
```

### 12. Recommended Codex Setup / 推荐 Codex 配置

中文：

将 `docs/CODEX_CUSTOM_INSTRUCTIONS_DRAFT.md` 中的 `<TASKSTATE_VAULT_REPO>` 替换为本地仓库绝对路径，然后放入 Codex 自定义指令。Codex 每次任务开始时会先读取 `docs/CODEX_USAGE_GUIDE.md`，再按照 TaskState Vault 的结构管理复杂任务。

English:

Replace `<TASKSTATE_VAULT_REPO>` in `docs/CODEX_CUSTOM_INSTRUCTIONS_DRAFT.md` with the absolute path to your local repository, then place the result in Codex custom instructions. At task start, Codex reads `docs/CODEX_USAGE_GUIDE.md` and uses TaskState Vault for complex task state management.

