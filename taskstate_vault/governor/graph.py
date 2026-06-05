from __future__ import annotations

from typing import Any

from taskstate_vault.core.db import sync_project_graph
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import read_jsonl, rewrite_jsonl
from taskstate_vault.core.schema import TaskEdge, TaskNode
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import graph_path, project_db


def build_initial_graph(paths, project_id: str, title: str, project_model: dict[str, Any]) -> list[dict[str, Any]]:
    timestamp = now_iso()
    project_node = TaskNode(
        node_id=f"project_{project_id}",
        node_type="project",
        title=title,
        objective=project_model.get("source_input_excerpt") or title,
        status="active",
        priority=1.0,
        project_impact=1.0,
        implementation_confidence=0.7,
        verification_clarity=0.8,
        rework_risk=0.2,
        created_at=timestamp,
        updated_at=timestamp,
    )

    records: list[dict[str, Any]] = [project_node.to_record()]
    previous_task_id: str | None = None
    task_ids: list[str] = []

    task_specs = [
        (
            "task_freeze_intent_and_schema",
            "冻结项目意图与核心 schema",
            "建立 PROJECT_INTENT、PROJECT_MODEL、任务图、执行队列和状态内核 schema，防止项目降级",
            ["PROJECT_INTENT.yaml 含 anti_degradation_rules", "schema 覆盖 Project Governor 和 Memory Kernel"],
            ["SYSTEM/SCHEMA.md", "PROJECT_INTENT.yaml"],
            0.95,
            0.9,
        ),
        (
            "task_project_governor_core",
            "实现 Project Governor 核心闭环",
            "从项目输入生成项目模型、任务图、执行队列，并支持项目进度回写",
            ["complex_project 初始化生成 governor 文件组", "run 后能更新 PROJECT_PROGRESS"],
            ["PROJECT_MODEL.yaml", "TASK_GRAPH.jsonl", "EXECUTION_QUEUE.jsonl", "PROJECT_PROGRESS.yaml"],
            0.95,
            0.75,
        ),
        (
            "task_execution_queue_scheduler",
            "实现执行队列调度器",
            "基于依赖、项目收益、解锁价值、验证清晰度、实现信心和返工风险排序",
            ["队列项包含 why_now", "队列项包含 score_breakdown", "blocked 任务不排在 ready 第一"],
            ["EXECUTION_QUEUE.jsonl"],
            0.9,
            0.8,
        ),
        (
            "task_memory_kernel",
            "实现任务态 Memory Kernel",
            "维护 TASK_STATE、NEXT_ACTION、event log、evidence、artifact、error 和 run",
            ["当前任务能从队列打开", "错误进入 error_log/negative_cache", "产物有 artifact record"],
            ["TASK_STATE.yaml", "NEXT_ACTION.md", "event_log.jsonl"],
            0.85,
            0.75,
        ),
        (
            "task_objective_change_manager",
            "实现局部目标自主改写",
            "支持 split、merge、defer、replace，并记录 OBJECTIVE_CHANGE_LOG 后重排队列",
            ["目标改写记录 old/new objective", "记录 parent_project_objective", "改写后队列重排"],
            ["OBJECTIVE_CHANGE_LOG.jsonl"],
            0.85,
            0.8,
        ),
        (
            "task_context_loader",
            "实现上下文装载与解释",
            "按 execution_mode 构造 simple_task、managed_task、complex_project 上下文，并记录加载原因",
            ["simple_task 上下文轻量", "complex_project 包含项目意图、队列、阻塞、当前任务", "可解释 why-loaded"],
            ["ACTIVE_CONTEXT.yaml", "CONTEXT_LOAD_LEDGER.jsonl"],
            0.8,
            0.8,
        ),
        (
            "task_final_audit_and_guidance",
            "实现最终审计与初始指引",
            "项目完成时生成 FINAL_AUDIT 和 INITIAL_GUIDANCE，并汇总交付物、经验、未完成项",
            ["FINAL_AUDIT 说明项目意图达成度", "INITIAL_GUIDANCE 可指导后续使用"],
            ["FINAL_AUDIT.md", "INITIAL_GUIDANCE.md"],
            0.75,
            0.85,
        ),
    ]

    for index, (node_id, node_title, objective, criteria, artifacts, impact, clarity) in enumerate(task_specs, start=1):
        task = TaskNode(
            node_id=node_id,
            node_type="task",
            parent_id=f"project_{project_id}",
            title=node_title,
            objective=objective,
            status="ready" if index == 1 else "planned",
            acceptance_criteria=criteria,
            expected_artifacts=artifacts,
            dependencies=[previous_task_id] if previous_task_id else [],
            priority=1.0 - index * 0.04,
            project_impact=impact,
            implementation_confidence=0.75,
            verification_clarity=clarity,
            rework_risk=0.2 + index * 0.02,
            parallelizable=index > 2,
            created_at=timestamp,
            updated_at=timestamp,
        )
        records.append(task.to_record())
        task_ids.append(node_id)
        records.append(
            TaskEdge(
                edge_id=make_id("edge", f"project_to_{node_id}"),
                src=f"project_{project_id}",
                dst=node_id,
                relation="decomposes_to",
                reason="复杂项目任务图分解",
                created_at=timestamp,
            ).to_record()
        )
        if previous_task_id:
            records.append(
                TaskEdge(
                    edge_id=make_id("edge", f"{previous_task_id}_to_{node_id}"),
                    src=node_id,
                    dst=previous_task_id,
                    relation="depends_on",
                    reason="后续任务依赖前序基础设施",
                    created_at=timestamp,
                ).to_record()
            )
        previous_task_id = node_id

    if len(task_ids) >= 4:
        # Context loader and final audit can proceed once the governor and kernel exist.
        records.append(
            TaskEdge(
                edge_id=make_id("edge", "context_depends_memory"),
                src="task_context_loader",
                dst="task_memory_kernel",
                relation="depends_on",
                reason="上下文装载需要任务态和项目态文件稳定存在",
                created_at=timestamp,
            ).to_record()
        )
    write_graph(paths, project_id, records)
    return records


def read_graph(paths, project_id: str) -> list[dict[str, Any]]:
    return read_jsonl(graph_path(paths, project_id))


def write_graph(paths, project_id: str, records: list[dict[str, Any]]) -> None:
    rewrite_jsonl(graph_path(paths, project_id), records)
    sync_project_graph(project_db(paths, project_id), records)


def nodes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("record_type") == "node"]


def edges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("record_type") == "edge"]


def find_node(records: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    return next((record for record in records if record.get("record_type") == "node" and record.get("node_id") == node_id), None)


def update_node(paths, project_id: str, node_id: str, **updates: Any) -> dict[str, Any]:
    records = read_graph(paths, project_id)
    target = find_node(records, node_id)
    if not target:
        raise ValueError(f"Task graph node not found: {node_id}")
    target.update(updates)
    target["updated_at"] = now_iso()
    write_graph(paths, project_id, records)
    return target


def ready_task_nodes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_nodes = {node["node_id"]: node for node in nodes(records)}
    ready: list[dict[str, Any]] = []
    for node in nodes(records):
        if node.get("node_type") != "task":
            continue
        if node.get("status") not in {"planned", "ready", "active"}:
            continue
        deps = node.get("dependencies", [])
        if all(all_nodes.get(dep, {}).get("status") == "completed" for dep in deps):
            ready.append(node)
    return ready

