from __future__ import annotations

from pathlib import Path
from typing import Any

from taskstate_vault.core import yamlish
from taskstate_vault.core.db import init_kernel_db, init_project_db, upsert_project
from taskstate_vault.core.events import append_event
from taskstate_vault.core.ids import make_id, slugify
from taskstate_vault.core.io import append_jsonl, read_jsonl, read_text, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths, TASKSTATE_VAULT_DIR
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import ensure_project_layout, project_db, project_dir, project_event_log
from taskstate_vault.governor.graph import build_initial_graph
from taskstate_vault.governor.intent import build_project_intent
from taskstate_vault.governor.model import build_project_model
from taskstate_vault.governor.progress import project_progress
from taskstate_vault.governor.queue import schedule_queue
from taskstate_vault.kernel.init import init_workspace
from taskstate_vault.modes.router import detect_mode
from taskstate_vault.workspaces.registry import register_project_ref, register_workspace


def read_input(input_path: str | None) -> str:
    return Path(input_path).read_text(encoding="utf-8") if input_path else ""


def create_project(
    paths: TaskStateVaultPaths,
    title: str,
    input_path: str | None = None,
    execution_mode: str | None = None,
    project_id: str | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    if not paths.os_dir.exists():
        init_workspace(paths.workspace)
    input_text = read_input(input_path)
    mode = execution_mode or detect_mode(f"{title}\n{input_text}").execution_mode
    pid = project_id or make_id("project", slugify(title, "project"))
    root = ensure_project_layout(paths, pid)
    timestamp = now_iso()
    init_kernel_db(paths.kernel_db)
    init_project_db(project_db(paths, pid))

    manifest = {
        "schema_version": 1,
        "project_id": pid,
        "title": title,
        "status": "active",
        "execution_mode": mode,
        "created_at": timestamp,
        "updated_at": timestamp,
        "paths": {
            "project_root": str(root),
            "governor": str(root / "GOVERNOR"),
            "external_workspace": str(Path(workspace_path).resolve()) if workspace_path else None,
        },
    }
    yamlish.write(root / "PROJECT_MANIFEST.yaml", manifest)
    upsert_project(
        paths.kernel_db,
        {
            "project_id": pid,
            "portfolio_id": None,
            "program_id": None,
            "domain_id": None,
            "status": "active",
            "title": title,
            "path": str(root),
            "execution_mode": mode,
            "current_task_id": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    append_jsonl(paths.os_dir / "project_registry.jsonl", manifest)
    project_ref = register_project_ref(paths, pid, title, root, mode, workspace_path=workspace_path)
    workspace_ref = None
    if workspace_path:
        workspace_ref = register_workspace(
            paths,
            workspace_path,
            project_id=pid,
            summary=f"Workspace for project {pid}: {title}",
            initialized_taskstate_vault=_workspace_has_taskfs(Path(workspace_path).resolve()),
        )
    append_event(project_event_log(paths, pid), "project_created", f"project/{pid}", f"Project created: {title}", execution_mode=mode)
    result = {
        "project_id": pid,
        "execution_mode": mode,
        "path": str(root),
        "project_ref": project_ref["pointer_uri"],
        "workspace_ref": workspace_ref["pointer_uri"] if workspace_ref else None,
    }
    if mode in {"complex_project", "program_scale"}:
        result["governor"] = init_governor(paths, pid, input_text=input_text or title)
    return result


def init_governor(paths: TaskStateVaultPaths, project_id: str, input_path: str | None = None, input_text: str | None = None) -> dict[str, Any]:
    root = ensure_project_layout(paths, project_id)
    manifest = yamlish.read(root / "PROJECT_MANIFEST.yaml", default={})
    title = manifest.get("title", project_id)
    text = input_text if input_text is not None else read_input(input_path)
    mode = manifest.get("execution_mode", "complex_project")
    intent = build_project_intent(project_id, title, text, mode)
    model = build_project_model(project_id, title, text)
    yamlish.write(root / "PROJECT_INTENT.yaml", intent)
    yamlish.write(root / "PROJECT_MODEL.yaml", model)
    graph = build_initial_graph(paths, project_id, title, model)
    queue = schedule_queue(paths, project_id)
    progress = project_progress(paths, project_id)
    append_event(project_event_log(paths, project_id), "governor_initialized", f"project/{project_id}", "Project Governor initialized", queue_size=len(queue))
    return {
        "project_id": project_id,
        "intent": str(root / "PROJECT_INTENT.yaml"),
        "model": str(root / "PROJECT_MODEL.yaml"),
        "task_graph_records": len(graph),
        "queue_size": len(queue),
        "progress": progress,
    }


def project_status(paths: TaskStateVaultPaths, project_id: str | None = None) -> dict[str, Any]:
    if project_id:
        root = project_dir(paths, project_id)
        return {
            "project_id": project_id,
            "manifest": yamlish.read(root / "PROJECT_MANIFEST.yaml", default={}),
            "project_progress": yamlish.read(root / "PROJECT_PROGRESS.yaml", default={}),
            "queue": read_jsonl(root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")[:5],
        }
    projects = []
    if paths.projects_dir.exists():
        for candidate in paths.projects_dir.iterdir():
            if candidate.is_dir():
                projects.append(yamlish.read(candidate / "PROJECT_MANIFEST.yaml", default={"project_id": candidate.name}))
    return {"workspace": str(paths.workspace), "taskfs": str(paths.os_dir), "projects": projects}


def _workspace_has_taskfs(workspace: Path) -> bool:
    return (workspace / TASKSTATE_VAULT_DIR).exists()
