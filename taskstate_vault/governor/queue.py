from __future__ import annotations

from typing import Any

from taskstate_vault.core.db import sync_execution_queue
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import read_jsonl, rewrite_jsonl
from taskstate_vault.core.schema import QueueItem
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_db, queue_path
from taskstate_vault.governor.graph import read_graph, ready_task_nodes


def score_node(node: dict[str, Any]) -> tuple[float, dict[str, float]]:
    dependency_unblocked = 1.0
    project_impact = float(node.get("project_impact", 0.5))
    unlocks_future_work = min(1.0, len(node.get("unlocks", [])) * 0.25 + 0.4)
    verification_clarity = float(node.get("verification_clarity", 0.5))
    implementation_confidence = float(node.get("implementation_confidence", 0.5))
    user_priority = float(node.get("priority", 0.5))
    rework_risk = float(node.get("rework_risk", 0.2))
    blocker_strength = 1.0 if node.get("blockers") else 0.0
    context_missing_penalty = 0.0 if node.get("acceptance_criteria") else 0.4
    score = (
        0.25 * dependency_unblocked
        + 0.25 * project_impact
        + 0.15 * unlocks_future_work
        + 0.15 * verification_clarity
        + 0.10 * implementation_confidence
        + 0.10 * user_priority
        - 0.20 * rework_risk
        - 0.15 * blocker_strength
        - 0.10 * context_missing_penalty
    )
    breakdown = {
        "dependency_unblocked": dependency_unblocked,
        "project_impact": project_impact,
        "unlocks_future_work": unlocks_future_work,
        "verification_clarity": verification_clarity,
        "implementation_confidence": implementation_confidence,
        "user_priority": user_priority,
        "rework_risk_penalty": -rework_risk,
        "blocker_strength_penalty": -blocker_strength,
        "context_missing_penalty": -context_missing_penalty,
    }
    return round(score, 4), breakdown


def schedule_queue(paths, project_id: str) -> list[dict[str, Any]]:
    graph = read_graph(paths, project_id)
    ready = ready_task_nodes(graph)
    scored = []
    timestamp = now_iso()
    for node in ready:
        score, breakdown = score_node(node)
        scored.append((score, node, breakdown))
    scored.sort(key=lambda item: item[0], reverse=True)

    queue: list[dict[str, Any]] = []
    for rank, (score, node, breakdown) in enumerate(scored, start=1):
        queue.append(
            QueueItem(
                queue_id=make_id("queue", node["node_id"]),
                task_id=node["node_id"],
                rank=rank,
                status="ready" if node.get("status") != "active" else "active",
                why_now=f"{node['title']} 当前可执行，项目收益 {node.get('project_impact', 0.5)}，验证清晰度 {node.get('verification_clarity', 0.5)}",
                score=score,
                score_breakdown=breakdown,
                required_context_refs=["PROJECT_INTENT.yaml", "PROJECT_PROGRESS.yaml", f"TASK_GRAPH:{node['node_id']}"],
                expected_outputs=node.get("expected_artifacts", []),
                created_at=timestamp,
                updated_at=timestamp,
            ).to_record()
        )

    rewrite_jsonl(queue_path(paths, project_id), queue)
    sync_execution_queue(project_db(paths, project_id), queue)
    return queue


def read_queue(paths, project_id: str) -> list[dict[str, Any]]:
    return read_jsonl(queue_path(paths, project_id))


def reschedule_queue(paths, project_id: str) -> dict[str, Any]:
    queue = schedule_queue(paths, project_id)
    return {"project_id": project_id, "queue_size": len(queue), "top": queue[:3]}


def get_next_action(paths, project_id: str) -> dict[str, Any]:
    queue = read_queue(paths, project_id)
    if not queue:
        queue = schedule_queue(paths, project_id)
    if not queue:
        return {"project_id": project_id, "status": "empty", "message": "No ready tasks in execution queue."}
    return queue[0]

