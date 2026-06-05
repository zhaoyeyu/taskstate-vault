from __future__ import annotations

from typing import Any

from taskstate_vault.core import yamlish
from taskstate_vault.core.io import read_jsonl
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import blockers_path, project_dir, queue_path
from taskstate_vault.governor.graph import nodes, read_graph


def project_progress_path(paths, project_id: str):
    return project_dir(paths, project_id) / "PROJECT_PROGRESS.yaml"


def project_progress(paths, project_id: str) -> dict[str, Any]:
    graph = read_graph(paths, project_id)
    task_nodes = [node for node in nodes(graph) if node.get("node_type") == "task"]
    completed = [node["node_id"] for node in task_nodes if node.get("status") == "completed"]
    active = [node["node_id"] for node in task_nodes if node.get("status") == "active"]
    blocked = [node["node_id"] for node in task_nodes if node.get("status") == "blocked"]
    queue = read_jsonl(queue_path(paths, project_id))
    blockers = [record for record in read_jsonl(blockers_path(paths, project_id)) if record.get("status") == "active"]
    progress_score = len(completed) / len(task_nodes) if task_nodes else 0.0
    confidence_values = [float(node.get("implementation_confidence", 0.5)) for node in task_nodes]
    confidence_score = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    data = {
        "schema_version": 1,
        "project_id": project_id,
        "updated_at": now_iso(),
        "overall_status": "completed" if task_nodes and len(completed) == len(task_nodes) else "active",
        "health": {
            "progress_score": round(progress_score, 4),
            "blocker_score": len(blockers),
            "confidence_score": round(confidence_score, 4),
            "rework_risk_score": round(sum(float(node.get("rework_risk", 0.0)) for node in task_nodes) / len(task_nodes), 4) if task_nodes else 0.0,
        },
        "active_focus": {
            "current_task": active[0] if active else (queue[0]["task_id"] if queue else None),
            "reason": queue[0]["why_now"] if queue else "",
        },
        "completed": {"tasks": completed},
        "blocked": {"tasks": blocked, "blockers": [item.get("blocker_id") for item in blockers]},
        "next_best_actions": [
            {
                "task_id": item["task_id"],
                "reason": item.get("why_now", ""),
                "expected_impact": item.get("score", 0),
            }
            for item in queue[:5]
        ],
        "recent_objective_changes": read_jsonl(project_dir(paths, project_id) / "GOVERNOR" / "OBJECTIVE_CHANGE_LOG.jsonl")[-5:],
    }
    yamlish.write(project_progress_path(paths, project_id), data)
    return data

