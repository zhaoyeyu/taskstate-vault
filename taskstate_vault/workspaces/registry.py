from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from taskstate_vault.core import yamlish
from taskstate_vault.core.paths import TaskStateVaultPaths, TASKSTATE_VAULT_DIR
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.layers.index import add_account_object


def register_project_ref(
    paths: TaskStateVaultPaths,
    project_id: str,
    title: str,
    project_path: str | Path,
    execution_mode: str,
    workspace_path: str | Path | None = None,
) -> dict[str, Any]:
    project_abs = Path(project_path).resolve()
    workspace_abs = Path(workspace_path).resolve() if workspace_path else None
    content = {
        "schema_version": 1,
        "ref_type": "project",
        "project_id": project_id,
        "title": title,
        "execution_mode": execution_mode,
        "central_project_path": str(project_abs),
        "workspace_path": str(workspace_abs) if workspace_abs else None,
        "registered_at": now_iso(),
    }
    return add_account_object(
        paths,
        "project_ref",
        f"Project {project_id}: {title}",
        json.dumps(content, ensure_ascii=False, sort_keys=True),
        tags=["project", project_id, execution_mode],
        ttl="account",
    )


def register_workspace(
    paths: TaskStateVaultPaths,
    workspace_path: str | Path,
    project_id: str | None = None,
    task_id: str | None = None,
    summary: str = "",
    initialized_taskstate_vault: bool = False,
) -> dict[str, Any]:
    workspace_abs = Path(workspace_path).resolve()
    content = {
        "schema_version": 1,
        "ref_type": "workspace",
        "workspace_path": str(workspace_abs),
        "taskfs_path": str(workspace_abs / TASKSTATE_VAULT_DIR),
        "central_root": str(paths.workspace),
        "project_id": project_id,
        "task_id": task_id,
        "initialized_taskstate_vault": initialized_taskstate_vault,
        "registered_at": now_iso(),
    }
    tags = ["workspace"]
    if project_id:
        tags.append(project_id)
    if task_id:
        tags.append(task_id)
    return add_account_object(
        paths,
        "workspace_ref",
        summary or f"Workspace {workspace_abs}",
        json.dumps(content, ensure_ascii=False, sort_keys=True),
        tags=tags,
        ttl="account",
    )


def init_task_workspace(
    central_paths: TaskStateVaultPaths,
    workspace_path: str | Path,
    project_id: str,
    task_id: str | None = None,
    summary: str = "",
) -> dict[str, Any]:
    from taskstate_vault.kernel.init import init_workspace

    workspace_abs = Path(workspace_path).resolve()
    local_init = init_workspace(workspace_abs)
    link_path = Path(local_init["taskfs"]) / "TASK_WORKSPACE.yaml"
    link = {
        "schema_version": 1,
        "central_root": str(central_paths.workspace),
        "central_taskfs": str(central_paths.os_dir),
        "project_id": project_id,
        "task_id": task_id,
        "workspace_path": str(workspace_abs),
        "created_at": now_iso(),
        "usage_guide": str(_usage_guide_path(central_paths)),
    }
    yamlish.write(link_path, link)
    ref = register_workspace(
        central_paths,
        workspace_abs,
        project_id=project_id,
        task_id=task_id,
        summary=summary or f"Task workspace for {project_id}",
        initialized_taskstate_vault=True,
    )
    return {
        "workspace": str(workspace_abs),
        "local_taskfs": local_init["taskfs"],
        "task_workspace_link": str(link_path),
        "central_workspace_ref": ref,
    }


def _usage_guide_path(paths: TaskStateVaultPaths) -> Path:
    repo_guide = paths.workspace / "docs" / "CODEX_USAGE_GUIDE.md"
    if repo_guide.exists():
        return repo_guide
    return paths.account_dir / "PROFILE" / "CODEX_USAGE_GUIDE.md"
