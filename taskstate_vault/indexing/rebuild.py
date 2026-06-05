from __future__ import annotations

from typing import Any

from taskstate_vault.core.db import init_task_db, managed_connection, sync_execution_queue, sync_project_graph
from taskstate_vault.core.io import read_jsonl
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.governor.files import project_db, project_dir
from taskstate_vault.governor.graph import read_graph
from taskstate_vault.governor.queue import read_queue


def rebuild_project_index(paths: TaskStateVaultPaths, project_id: str) -> dict[str, Any]:
    graph = read_graph(paths, project_id)
    queue = read_queue(paths, project_id)
    sync_project_graph(project_db(paths, project_id), graph)
    sync_execution_queue(project_db(paths, project_id), queue)
    return {"project_id": project_id, "graph_records": len(graph), "queue_records": len(queue)}


def rebuild_task_index(paths: TaskStateVaultPaths, project_id: str, task_id: str) -> dict[str, Any]:
    task_root = paths.task_dir(project_id, task_id)
    task_db = task_root / "INDEX" / "task.sqlite"
    init_task_db(task_db)
    object_records: list[dict[str, Any]] = []
    for file in (task_root / "OBJECTS").glob("*.jsonl"):
        for record in read_jsonl(file):
            object_records.append({**record, "_source_type": file.stem})
    with managed_connection(task_db) as conn:
        conn.execute("DELETE FROM fts_objects")
        for record in object_records:
            object_id = record.get("object_id") or record.get("artifact_id") or record.get("error_id") or record.get("evidence_id")
            if not object_id:
                continue
            obj_type = record.get("type") or record.get("_source_type", "object")
            summary = record.get("summary", "")
            conn.execute(
                "INSERT INTO fts_objects(object_id, type, summary, content) VALUES (?, ?, ?, ?)",
                (object_id, obj_type, summary, summary),
            )
    return {"project_id": project_id, "task_id": task_id, "indexed_records": len(object_records)}
