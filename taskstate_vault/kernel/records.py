from __future__ import annotations

from pathlib import Path
from typing import Any

from taskstate_vault.core.db import init_task_db, managed_connection, upsert_index_entry
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_dir


OBJECT_FILE_BY_TYPE = {
    "fact": "facts.jsonl",
    "assumption": "assumptions.jsonl",
    "constraint": "constraints.jsonl",
    "decision": "decisions.jsonl",
    "entity": "entities.jsonl",
    "resource": "resources.jsonl",
    "artifact": "artifacts.jsonl",
    "tool": "tools.jsonl",
    "error": "errors.jsonl",
}


def add_object(paths: TaskStateVaultPaths, project_id: str, task_id: str, object_type: str, summary: str, source_ref: str | None = None) -> dict[str, Any]:
    object_id = make_id("obj", object_type)
    created = now_iso()
    record = {
        "schema_version": 1,
        "object_id": object_id,
        "namespace": f"project/{project_id}/task/{task_id}",
        "type": object_type,
        "arena": "task",
        "status": "active",
        "confidence": 0.8 if source_ref else 0.5,
        "salience": 0.5,
        "ttl": "task",
        "content_hash": None,
        "path": None,
        "summary": summary,
        "source_refs": [source_ref] if source_ref else [],
        "derived_from": [],
        "supersedes": [],
        "invalidated_by": [],
        "access_policy": "on_query",
        "import_policy": "local_only",
        "created_at": created,
        "updated_at": created,
    }
    filename = OBJECT_FILE_BY_TYPE.get(object_type, f"{object_type}s.jsonl")
    task_root = paths.task_dir(project_id, task_id)
    append_jsonl(task_root / "OBJECTS" / filename, record)
    _index_object(task_root / "INDEX" / "task.sqlite", record)
    return record


def add_evidence(paths: TaskStateVaultPaths, project_id: str, task_id: str, kind: str, text: str) -> dict[str, Any]:
    evidence_id = make_id("evidence", kind)
    rel = Path("EVIDENCE") / kind / f"{evidence_id}.txt"
    task_root = paths.task_dir(project_id, task_id)
    write_text(task_root / rel, text)
    record = {
        "schema_version": 1,
        "evidence_id": evidence_id,
        "kind": kind,
        "task_id": task_id,
        "project_id": project_id,
        "path": str(rel),
        "summary": text[:240],
        "created_at": now_iso(),
    }
    append_jsonl(task_root / "OBJECTS" / "resources.jsonl", record)
    return record


def add_artifact(paths: TaskStateVaultPaths, project_id: str, task_id: str, path: str, summary: str, run_id: str | None = None) -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "artifact_id": make_id("artifact", task_id),
        "project_id": project_id,
        "task_id": task_id,
        "run_id": run_id,
        "path": path,
        "summary": summary,
        "status": "draft",
        "created_at": now_iso(),
    }
    append_jsonl(paths.task_dir(project_id, task_id) / "OBJECTS" / "artifacts.jsonl", record)
    append_jsonl(project_dir(paths, project_id) / "PROJECT_OBJECTS" / "artifacts.jsonl", record)
    _index_generic(paths.task_dir(project_id, task_id) / "INDEX" / "task.sqlite", record["artifact_id"], f"project/{project_id}/task/{task_id}", "task", "artifact", summary, path)
    _index_generic(project_dir(paths, project_id) / "PROJECT_INDEX" / "project.sqlite", record["artifact_id"], f"project/{project_id}", "project", "artifact", summary, path)
    return record


def log_error(paths: TaskStateVaultPaths, project_id: str, task_id: str, summary: str, run_id: str | None = None) -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "error_id": make_id("err", task_id),
        "project_id": project_id,
        "task_id": task_id,
        "run_id": run_id,
        "summary": summary,
        "created_at": now_iso(),
    }
    task_root = paths.task_dir(project_id, task_id)
    append_jsonl(task_root / "LOGS" / "error_log.jsonl", record)
    append_jsonl(task_root / "LOGS" / "negative_cache.jsonl", {**record, "negative_cache_id": make_id("neg", task_id)})
    append_jsonl(task_root / "OBJECTS" / "errors.jsonl", record)
    _index_generic(task_root / "INDEX" / "task.sqlite", record["error_id"], f"project/{project_id}/task/{task_id}", "task", "error", summary, "")
    return record


def record_run_note(paths: TaskStateVaultPaths, project_id: str, task_id: str, run_id: str, note: str, kind: str = "output") -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "record_id": make_id("run_record", run_id),
        "project_id": project_id,
        "task_id": task_id,
        "run_id": run_id,
        "kind": kind,
        "note": note,
        "created_at": now_iso(),
    }
    append_jsonl(paths.task_dir(project_id, task_id) / "RUNS" / run_id / "records.jsonl", record)
    return record


def _index_object(task_db, record: dict[str, Any]) -> None:
    init_task_db(task_db)
    layer_entry = {
        "entry_id": record["object_id"],
        "object_id": record["object_id"],
        "scope": record["namespace"],
        "layer": "task",
        "object_type": record["type"],
        "status": record["status"],
        "arena": record["arena"],
        "ttl": record["ttl"],
        "summary": record["summary"],
        "content": record["summary"],
        "storage_path": record.get("path") or "",
        "pointer_uri": f"tsv://{record['namespace']}/{record['object_id']}",
        "tags_json": "[]",
        "source_refs_json": "[]",
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }
    upsert_index_entry(task_db, layer_entry)
    with managed_connection(task_db) as conn:
        conn.execute(
            """
            INSERT INTO objects(object_id, namespace, type, arena, status, confidence, salience, ttl, content_hash, path, summary,
              source_refs_json, derived_from_json, supersedes_json, invalidated_by_json, access_policy, import_policy, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(object_id) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at
            """,
            (
                record["object_id"],
                record["namespace"],
                record["type"],
                record["arena"],
                record["status"],
                record["confidence"],
                record["salience"],
                record["ttl"],
                record["content_hash"],
                record["path"],
                record["summary"],
                "[]",
                "[]",
                "[]",
                "[]",
                record["access_policy"],
                record["import_policy"],
                record["created_at"],
                record["updated_at"],
            ),
        )
        conn.execute(
            "INSERT INTO fts_objects(object_id, type, summary, content) VALUES (?, ?, ?, ?)",
            (record["object_id"], record["type"], record["summary"], record["summary"]),
        )


def _index_generic(task_db, object_id: str, scope: str, layer: str, object_type: str, summary: str, storage_path: str) -> None:
    now = now_iso()
    upsert_index_entry(
        task_db,
        {
            "entry_id": object_id,
            "object_id": object_id,
            "scope": scope,
            "layer": layer,
            "object_type": object_type,
            "status": "active",
            "arena": layer,
            "ttl": layer,
            "summary": summary,
            "content": summary,
            "storage_path": storage_path,
            "pointer_uri": f"tsv://{scope}/{object_id}",
            "tags_json": "[]",
            "source_refs_json": "[]",
            "created_at": now,
            "updated_at": now,
        },
    )
