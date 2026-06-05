from __future__ import annotations


ENTRYPOINT = """# TaskState Vault Entrypoint

Start here when a workspace contains `.taskstate-vault`.

1. Detect execution mode: `simple_task`, `managed_task`, `complex_project`, or `program_scale`.
2. ContextKernel keeps simple tasks lightweight.
3. For managed tasks, ContextKernel loads the current task state and next action.
4. For complex projects, use Project Governor before implementation.
5. Complex projects must read project intent, project model, task graph, execution queue, blockers, project progress, and current task state.
6. Stable project intent is not silently rewritten.
7. Local task objectives may be split, merged, deferred, replaced, or bypassed when that improves project progress, but every change must be recorded in `OBJECTIVE_CHANGE_LOG.jsonl`.
8. After every complex project run, update TaskFS records, TaskDB indexes, task graph, execution queue, project progress, blockers, artifacts, errors, and next action.
9. TaskState Vault does not implement Codex sandbox, approvals, command permissions, network permissions, or project-outside file protection.
"""


GOVERNOR_PROTOCOL = """# Project Governor Protocol

Complex projects are governed by this loop:

project input -> PROJECT_INTENT -> PROJECT_MODEL -> TASK_GRAPH -> EXECUTION_QUEUE -> current task -> run -> project progress update -> queue reschedule

Required complex project files:

- PROJECT_INTENT.yaml
- PROJECT_MODEL.yaml
- PROJECT_PROGRESS.yaml
- GOVERNOR/TASK_GRAPH.jsonl
- GOVERNOR/EXECUTION_QUEUE.jsonl
- GOVERNOR/BLOCKERS.jsonl
- GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl
"""


READ_PROTOCOL = """# Read Protocol

simple_task:
- Load only the current user request and directly relevant files.

managed_task:
- Load TASK_MANIFEST.yaml.
- Load CURRENT/TASK_STATE.yaml.
- Load CURRENT/NEXT_ACTION.md.

complex_project:
- Load PROJECT_INTENT.yaml.
- Load PROJECT_MODEL.yaml.
- Load PROJECT_PROGRESS.yaml.
- Load GOVERNOR/EXECUTION_QUEUE.jsonl top ready items.
- Load GOVERNOR/TASK_GRAPH.jsonl relevant subgraph.
- Load GOVERNOR/BLOCKERS.jsonl active relevant items.
- Load GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl recent entries.
- Load current TASK_STATE and NEXT_ACTION.
"""


WRITE_PROTOCOL = """# Write Protocol

Every complex project run must write back:

- task state
- next action
- run record
- evidence / artifact / error records
- task graph status patch
- blocker changes
- objective changes if the local task objective changed
- project progress
- execution queue reschedule
"""


EXECUTION_MODES = {
    "schema_version": 1,
    "execution_modes": {
        "simple_task": {
            "governor": False,
            "task_graph_required": False,
            "context_profile": "minimal",
        },
        "managed_task": {
            "governor": False,
            "task_graph_required": False,
            "context_profile": "task_state",
        },
        "complex_project": {
            "governor": True,
            "task_graph_required": True,
            "context_profile": "project_governor",
        },
        "program_scale": {
            "governor": True,
            "task_graph_required": True,
            "context_profile": "program_governor",
        },
    },
}


ROUTER_RULES = {
    "schema_version": 1,
    "simple_task_keywords": ["修改一个文件", "运行命令", "解释", "修复小问题"],
    "complex_project_keywords": [
        "完整项目",
        "复杂项目",
        "大型项目",
        "多模块",
        "长期",
        "任务图",
        "执行队列",
        "Project Governor",
        "主导",
        "系统",
    ],
}


SCHEMA = """# TaskState Vault Schema Index

Core records:

- project intent
- project model
- task graph node / edge
- execution queue item
- blocker
- objective change
- task state
- event
- artifact
- error
"""


CODEX_USAGE_GUIDE_ACCOUNT = """# Codex 使用 TaskState Vault 说明

## 固定入口

每次任务开始先读取自定义指令给出的固定使用说明。入口由用户安装 TaskState Vault 后填写：

```text
<TASKSTATE_VAULT_REPO>/docs/CODEX_USAGE_GUIDE.md
```

中央 TaskState Vault 根目录为：

```text
<TASKSTATE_VAULT_REPO>
```

任务工作区可以是任意目录。当前工作区若参与 TaskState Vault 管理，应注册到中央账户索引；需要本地任务级结构时，创建该工作区自己的 `.taskstate-vault/TASK_WORKSPACE.yaml` 链接文件。

## 基本流程

1. 使用中央根目录运行 CLI。
2. 读取账户初始状态、项目状态、任务状态和相关索引。
3. 判断 execution_mode。
4. simple_task 保持轻量。
5. complex_project 使用 Project Governor、任务图、执行队列和项目回写。
6. 对当前任务有用的账户/领域长期信息复制到任务级副本，并保留源指针。
7. 新项目、外部工作区、项目文件变化都同步到对应索引。

## 关键命令

```powershell
cd <TASKSTATE_VAULT_REPO>
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> project create --title "<title>" --mode complex_project --project-id <project_id> --workspace <project_workspace>
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> workspace init-task --workspace <current_workdir> --project <project_id> --task <task_id>
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> index project-files --project <project_id> --path <project_workspace>
python -m taskstate_vault.cli.main --root <TASKSTATE_VAULT_REPO> layer import-account --query <query> --project <project_id> --task <task_id>
```
"""

