from __future__ import annotations

from typing import Any

from taskstate_vault.core.events import append_event
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import objective_log_path, project_event_log
from taskstate_vault.governor.graph import find_node, read_graph, update_node
from taskstate_vault.governor.progress import project_progress
from taskstate_vault.governor.queue import schedule_queue


def change_objective(paths, project_id: str, task_id: str, change_type: str, new_objective: str | None, reason: str) -> dict[str, Any]:
    graph = read_graph(paths, project_id)
    node = find_node(graph, task_id)
    if not node:
        raise ValueError(f"Task node not found: {task_id}")
    old = node.get("objective", "")
    replacement = new_objective or _default_new_objective(change_type, old)
    record = {
        "schema_version": 1,
        "change_id": make_id("obj_change", task_id),
        "change_type": change_type,
        "task_id": task_id,
        "old_task_objective": old,
        "new_task_objective": replacement,
        "reason": reason,
        "parent_project_objective": f"project/{project_id}",
        "expected_gain": _expected_gain(change_type),
        "risk_or_tradeoff": "局部目标变化需要后续队列重排保持项目意图一致",
        "affected_tasks": node.get("unlocks", []),
        "graph_patch_refs": [task_id],
        "queue_patch_refs": [],
        "created_at": now_iso(),
    }
    append_jsonl(objective_log_path(paths, project_id), record)
    update_node(paths, project_id, task_id, objective=replacement, status="planned" if change_type in {"defer", "split"} else node.get("status", "planned"))
    queue = schedule_queue(paths, project_id)
    progress = project_progress(paths, project_id)
    append_event(project_event_log(paths, project_id), "objective_changed", f"project/{project_id}/task/{task_id}", f"Objective changed for {task_id}", change_id=record["change_id"])
    return {"objective_change": record, "queue_size": len(queue), "project_progress": progress}


def _default_new_objective(change_type: str, old: str) -> str:
    if change_type == "split":
        return f"拆分并优先完成可验证部分：{old}"
    if change_type == "merge":
        return f"合并重复目标后完成：{old}"
    if change_type == "defer":
        return f"延后当前阻塞路径，先保留目标：{old}"
    return old


def _expected_gain(change_type: str) -> str:
    return {
        "split": "降低任务粒度，提高验证清晰度并减少返工",
        "merge": "减少重复任务，集中项目收益",
        "defer": "绕开阻塞项，让项目继续推进",
        "replace-objective": "替换为更高杠杆或更可验证的实现路径",
    }.get(change_type, "提升当前任务与项目意图的匹配度")

