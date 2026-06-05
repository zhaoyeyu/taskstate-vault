from __future__ import annotations

from typing import Any

from taskstate_vault.core import yamlish
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl, read_jsonl
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_dir
from taskstate_vault.governor.graph import find_node, read_graph
from taskstate_vault.governor.queue import read_queue
from taskstate_vault.modes.profiles import MODE_TO_PROFILE


def build_context(paths, project_id: str | None = None, task_id: str | None = None, mode: str | None = None) -> dict[str, Any]:
    if not project_id:
        return {
            "schema_version": 1,
            "execution_mode": mode or "simple_task",
            "profile": "minimal",
            "loaded": [{"ref": "current_user_request", "reason": "simple_task keeps context lightweight"}],
            "context": {},
        }
    root = project_dir(paths, project_id)
    manifest = yamlish.read(root / "PROJECT_MANIFEST.yaml", default={})
    execution_mode = mode or manifest.get("execution_mode", "managed_task")
    profile = MODE_TO_PROFILE.get(execution_mode, "task_state")
    loaded: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    context: dict[str, Any] = {}

    if profile == "minimal":
        loaded.append({"ref": "current_user_request", "reason": "simple task"})
    elif profile == "task_state":
        if task_id:
            task_root = paths.task_dir(project_id, task_id)
            context["task_state"] = yamlish.read(task_root / "CURRENT" / "TASK_STATE.yaml", default={})
            context["next_action"] = (task_root / "CURRENT" / "NEXT_ACTION.md").read_text(encoding="utf-8") if (task_root / "CURRENT" / "NEXT_ACTION.md").exists() else ""
            loaded.append({"ref": f"TASKS/{task_id}/CURRENT", "reason": "managed task startup state"})
    else:
        context["account_initial_state"] = yamlish.read(paths.account_dir / "PROFILE" / "initial_state.yaml", default={})
        context["project_intent"] = yamlish.read(root / "PROJECT_INTENT.yaml", default={})
        context["project_model"] = yamlish.read(root / "PROJECT_MODEL.yaml", default={})
        context["project_progress"] = yamlish.read(root / "PROJECT_PROGRESS.yaml", default={})
        queue = read_queue(paths, project_id)
        graph = read_graph(paths, project_id)
        context["execution_queue_top"] = queue[:5]
        context["blockers"] = read_jsonl(root / "GOVERNOR" / "BLOCKERS.jsonl")[-10:]
        context["recent_objective_changes"] = read_jsonl(root / "GOVERNOR" / "OBJECTIVE_CHANGE_LOG.jsonl")[-10:]
        if not task_id and queue:
            task_id = queue[0]["task_id"]
        if task_id:
            context["current_task_node"] = find_node(graph, task_id)
            task_root = paths.task_dir(project_id, task_id)
            context["task_state"] = yamlish.read(task_root / "CURRENT" / "TASK_STATE.yaml", default={})
            context["next_action"] = (task_root / "CURRENT" / "NEXT_ACTION.md").read_text(encoding="utf-8") if (task_root / "CURRENT" / "NEXT_ACTION.md").exists() else ""
            context["task_layer_imports"] = read_jsonl(task_root / "OBJECTS" / "layer_imports.jsonl")[-10:]
        loaded.extend(
            [
                {"ref": "ACCOUNT/PROFILE/initial_state.yaml", "reason": "account-level initial state and global info slots"},
                {"ref": "PROJECT_INTENT.yaml", "reason": "stable project objective"},
                {"ref": "PROJECT_MODEL.yaml", "reason": "project structure"},
                {"ref": "PROJECT_PROGRESS.yaml", "reason": "current project state"},
                {"ref": "GOVERNOR/EXECUTION_QUEUE.jsonl", "reason": "next best actions"},
                {"ref": "GOVERNOR/TASK_GRAPH.jsonl", "reason": "dependencies and acceptance criteria"},
                {"ref": "GOVERNOR/BLOCKERS.jsonl", "reason": "active blockers and workarounds"},
                {"ref": "GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl", "reason": "recent autonomous objective changes"},
            ]
        )
        skipped.append({"ref": "closed_tasks", "reason": "not needed for active governor context"})

    result = {
        "schema_version": 1,
        "execution_mode": execution_mode,
        "profile": profile,
        "project_id": project_id,
        "task_id": task_id,
        "loaded": loaded,
        "skipped": skipped,
        "context": context,
        "created_at": now_iso(),
    }
    if project_id:
        ledger = {
            "schema_version": 1,
            "ledger_id": make_id("ctx", project_id),
            "run_id": None,
            "execution_mode": execution_mode,
            "loaded": loaded,
            "skipped": skipped,
            "created_at": result["created_at"],
        }
        append_jsonl(root / "GOVERNOR" / "CONTEXT_LOAD_LEDGER.jsonl", ledger)
        if task_id and (paths.task_dir(project_id, task_id) / "CURRENT").exists():
            yamlish.write(paths.task_dir(project_id, task_id) / "CURRENT" / "ACTIVE_CONTEXT.yaml", result)
    return result


def explain_context(paths, project_id: str, run_id: str | None = None) -> dict[str, Any]:
    root = project_dir(paths, project_id)
    ledger = read_jsonl(root / "GOVERNOR" / "CONTEXT_LOAD_LEDGER.jsonl")
    if run_id:
        ledger = [item for item in ledger if item.get("run_id") == run_id]
    return {"project_id": project_id, "entries": ledger[-10:]}
