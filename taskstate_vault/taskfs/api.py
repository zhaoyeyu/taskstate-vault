from __future__ import annotations

from pathlib import Path
from typing import Any

from taskstate_vault.core.paths import TaskStateVaultPaths, resolve_workspace
from taskstate_vault.governor.manager import project_status
from taskstate_vault.kernel.init import init_workspace
from taskstate_vault.workspaces.registry import init_task_workspace, register_workspace


class TaskFS:
    """Public facade for TaskState Vault's on-disk state layout."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = resolve_workspace(root)
        self.paths = TaskStateVaultPaths(self.root)

    def init(self) -> dict[str, str]:
        return init_workspace(self.root)

    def status(self, project_id: str | None = None) -> dict[str, Any]:
        return project_status(self.paths, project_id)

    def register_workspace(
        self,
        workspace_path: str | Path,
        project_id: str | None = None,
        task_id: str | None = None,
        summary: str = "",
        initialized_taskstate_vault: bool = False,
    ) -> dict[str, Any]:
        return register_workspace(
            self.paths,
            workspace_path,
            project_id=project_id,
            task_id=task_id,
            summary=summary,
            initialized_taskstate_vault=initialized_taskstate_vault,
        )

    def init_task_workspace(
        self,
        workspace_path: str | Path,
        project_id: str,
        task_id: str | None = None,
        summary: str = "",
    ) -> dict[str, Any]:
        return init_task_workspace(self.paths, workspace_path, project_id, task_id, summary)
