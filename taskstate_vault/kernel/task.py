from __future__ import annotations

from typing import Any

from taskstate_vault.core import yamlish
from taskstate_vault.core.db import init_task_db, upsert_task
from taskstate_vault.core.events import append_event
from taskstate_vault.core.io import ensure_dir, touch, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_event_log
from taskstate_vault.governor.graph import find_node, read_graph, update_node
from taskstate_vault.governor.progress import project_progress
from taskstate_vault.governor.queue import read_queue, schedule_queue


TASK_DIRS = [
    "CURRENT",
    "OBJECTS",
    "LOGS",
    "RUNS",
    "EVIDENCE/user_messages",
    "EVIDENCE/files",
    "EVIDENCE/command_outputs",
    "EVIDENCE/web",
    "EVIDENCE/screenshots",
    "ARTIFACTS",
    "TOOLS",
    "INDEX",
    "CACHE",
    "DEPRECATED",
    "ARCHIVE",
]

TASK_JSONL = [
    "OBJECTS/facts.jsonl",
    "OBJECTS/assumptions.jsonl",
    "OBJECTS/constraints.jsonl",
    "OBJECTS/decisions.jsonl",
    "OBJECTS/entities.jsonl",
    "OBJECTS/resources.jsonl",
    "OBJECTS/artifacts.jsonl",
    "OBJECTS/tools.jsonl",
    "OBJECTS/errors.jsonl",
    "LOGS/event_log.jsonl",
    "LOGS/input_diffs.jsonl",
    "LOGS/error_log.jsonl",
    "LOGS/negative_cache.jsonl",
    "LOGS/audit_log.jsonl",
]


def ensure_task_layout(paths: TaskStateVaultPaths, project_id: str, task_id: str):
    root = paths.task_dir(project_id, task_id)
    for rel in TASK_DIRS:
        ensure_dir(root / rel)
    for rel in TASK_JSONL:
        touch(root / rel)
    init_task_db(root / "INDEX" / "task.sqlite")
    return root


def create_task_from_queue(paths: TaskStateVaultPaths, project_id: str, queue_rank: int = 1) -> dict[str, Any]:
    queue = read_queue(paths, project_id)
    if not queue:
        queue = schedule_queue(paths, project_id)
    selected = next((item for item in queue if int(item.get("rank", 0)) == queue_rank), None)
    if not selected:
        raise ValueError(f"No execution queue item at rank {queue_rank}")
    task_id = selected["task_id"]
    graph = read_graph(paths, project_id)
    node = find_node(graph, task_id)
    if not node:
        raise ValueError(f"Queue item points to missing task graph node: {task_id}")
    root = ensure_task_layout(paths, project_id, task_id)
    timestamp = now_iso()
    manifest = {
        "schema_version": 1,
        "task_id": task_id,
        "project_id": project_id,
        "task_graph_node": task_id,
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "execution_mode": "complex_project",
        "startup_load": [
            "TASK_MANIFEST.yaml",
            "CURRENT/TASK_STATE.yaml",
            "CURRENT/NEXT_ACTION.md",
        ],
    }
    state = {
        "schema_version": 1,
        "task_id": task_id,
        "project_id": project_id,
        "execution_mode": "complex_project",
        "status": "active",
        "updated_at": timestamp,
        "task_objective": {
            "current": node.get("objective"),
            "parent_project_objective": f"project/{project_id}",
            "last_changed_by": None,
        },
        "acceptance_criteria": node.get("acceptance_criteria", []),
        "active_constraints": [],
        "current_facts": [],
        "active_assumptions": [],
        "active_decisions": [],
        "current_blockers": node.get("blockers", []),
        "next_action_ref": "CURRENT/NEXT_ACTION.md",
        "project_refs": {
            "task_graph_node": task_id,
            "execution_queue_item": selected.get("queue_id"),
        },
    }
    yamlish.write(root / "TASK_MANIFEST.yaml", manifest)
    yamlish.write(root / "CURRENT" / "TASK_STATE.yaml", state)
    write_text(
        root / "CURRENT" / "NEXT_ACTION.md",
        f"# NEXT_ACTION\n\n{selected.get('why_now', node.get('title'))}\n\n## Acceptance Criteria\n\n"
        + "\n".join(f"- {item}" for item in node.get("acceptance_criteria", []))
        + "\n",
    )
    update_node(paths, project_id, task_id, status="active")
    upsert_task(
        paths.kernel_db,
        {
            "task_id": task_id,
            "project_id": project_id,
            "parent_node_id": node.get("parent_id"),
            "status": "active",
            "title": node.get("title"),
            "path": str(root),
            "queue_rank": selected.get("rank"),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    append_event(root / "LOGS" / "event_log.jsonl", "task_opened", f"project/{project_id}/task/{task_id}", f"Task opened from execution queue: {node.get('title')}")
    append_event(project_event_log(paths, project_id), "task_opened", f"project/{project_id}/task/{task_id}", f"Task opened: {task_id}")
    project_progress(paths, project_id)
    return {"project_id": project_id, "task_id": task_id, "path": str(root), "state": state}


def open_task(paths: TaskStateVaultPaths, project_id: str, task_id: str) -> dict[str, Any]:
    root = paths.task_dir(project_id, task_id)
    if not root.exists():
        return create_task_from_queue(paths, project_id, 1)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "manifest": yamlish.read(root / "TASK_MANIFEST.yaml"),
        "state": yamlish.read(root / "CURRENT" / "TASK_STATE.yaml"),
        "next_action": (root / "CURRENT" / "NEXT_ACTION.md").read_text(encoding="utf-8") if (root / "CURRENT" / "NEXT_ACTION.md").exists() else "",
    }


def complete_task(paths: TaskStateVaultPaths, project_id: str, task_id: str) -> dict[str, Any]:
    root = paths.task_dir(project_id, task_id)
    timestamp = now_iso()
    state = yamlish.read(root / "CURRENT" / "TASK_STATE.yaml", default={})
    state["status"] = "completed"
    state["updated_at"] = timestamp
    yamlish.write(root / "CURRENT" / "TASK_STATE.yaml", state)
    write_text(root / "CURRENT" / "NEXT_ACTION.md", "# NEXT_ACTION\n\nTask completed. Select the next ready item from EXECUTION_QUEUE.\n")
    update_node(paths, project_id, task_id, status="completed")
    append_event(root / "LOGS" / "event_log.jsonl", "task_completed", f"project/{project_id}/task/{task_id}", "Task completed")
    append_event(project_event_log(paths, project_id), "task_completed", f"project/{project_id}/task/{task_id}", f"Task completed: {task_id}")
    queue = schedule_queue(paths, project_id)
    progress = project_progress(paths, project_id)
    upsert_task(
        paths.kernel_db,
        {
            "task_id": task_id,
            "project_id": project_id,
            "parent_node_id": None,
            "status": "completed",
            "title": task_id,
            "path": str(root),
            "queue_rank": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return {"task_id": task_id, "status": "completed", "queue_size": len(queue), "project_progress": progress}

