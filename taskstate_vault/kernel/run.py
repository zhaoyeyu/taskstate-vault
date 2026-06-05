from __future__ import annotations

from typing import Any

from taskstate_vault.core import yamlish
from taskstate_vault.core.db import managed_connection
from taskstate_vault.core.events import append_event
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl, ensure_dir, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_dir, project_event_log
from taskstate_vault.governor.progress import project_progress
from taskstate_vault.governor.queue import schedule_queue


def start_run(paths: TaskStateVaultPaths, project_id: str, task_id: str) -> dict[str, Any]:
    run_id = make_id("run", task_id)
    root = paths.task_dir(project_id, task_id) / "RUNS" / run_id
    ensure_dir(root)
    timestamp = now_iso()
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "task_id": task_id,
        "project_id": project_id,
        "execution_mode": "complex_project",
        "started_at": timestamp,
        "ended_at": None,
        "status": "active",
        "inputs": [],
        "outputs": [],
        "artifacts": [],
        "errors": [],
        "project_updates": [],
    }
    yamlish.write(root / "run_manifest.yaml", manifest)
    write_text(root / "commands.log", "")
    write_text(root / "stdout.log", "")
    write_text(root / "stderr.log", "")
    append_event(paths.task_dir(project_id, task_id) / "LOGS" / "event_log.jsonl", "run_started", f"project/{project_id}/task/{task_id}/run/{run_id}", "Run started")
    append_event(project_event_log(paths, project_id), "run_started", f"project/{project_id}/task/{task_id}/run/{run_id}", "Run started")
    _upsert_run(paths, project_id, task_id, run_id, "active", timestamp, None, root)
    return {"run_id": run_id, "path": str(root), "manifest": manifest}


def finish_run(paths: TaskStateVaultPaths, project_id: str, task_id: str, run_id: str, status: str, summary: str = "") -> dict[str, Any]:
    root = paths.task_dir(project_id, task_id) / "RUNS" / run_id
    manifest_path = root / "run_manifest.yaml"
    manifest = yamlish.read(manifest_path, default={})
    ended = now_iso()
    manifest.update({"status": status, "ended_at": ended, "summary": summary})
    yamlish.write(manifest_path, manifest)
    task_root = paths.task_dir(project_id, task_id)
    if status == "failed":
        err = {
            "schema_version": 1,
            "error_id": make_id("err", task_id),
            "run_id": run_id,
            "task_id": task_id,
            "summary": summary,
            "created_at": ended,
        }
        append_jsonl(task_root / "LOGS" / "error_log.jsonl", err)
        append_jsonl(task_root / "LOGS" / "negative_cache.jsonl", {**err, "negative_cache_id": make_id("neg", task_id)})
    else:
        artifact = {
            "schema_version": 1,
            "artifact_id": make_id("artifact", task_id),
            "run_id": run_id,
            "task_id": task_id,
            "summary": summary or "Run completed",
            "path": str(root),
            "status": "accepted" if status == "success" else "draft",
            "created_at": ended,
        }
        append_jsonl(task_root / "OBJECTS" / "artifacts.jsonl", artifact)
        append_jsonl(project_dir(paths, project_id) / "PROJECT_OBJECTS" / "artifacts.jsonl", artifact)
    append_event(task_root / "LOGS" / "event_log.jsonl", f"run_{status}", f"project/{project_id}/task/{task_id}/run/{run_id}", summary or f"Run finished: {status}")
    append_event(project_event_log(paths, project_id), f"run_{status}", f"project/{project_id}/task/{task_id}/run/{run_id}", summary or f"Run finished: {status}")
    queue = schedule_queue(paths, project_id)
    progress = project_progress(paths, project_id)
    _upsert_run(paths, project_id, task_id, run_id, status, manifest.get("started_at"), ended, root)
    return {"run_id": run_id, "status": status, "queue_size": len(queue), "project_progress": progress}


def _upsert_run(paths: TaskStateVaultPaths, project_id: str, task_id: str, run_id: str, status: str, started_at: str | None, ended_at: str | None, root) -> None:
    with managed_connection(paths.kernel_db) as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, project_id, task_id, status, started_at, ended_at, path)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              status=excluded.status,
              ended_at=excluded.ended_at,
              path=excluded.path
            """,
            (run_id, project_id, task_id, status, started_at, ended_at, str(root)),
        )
