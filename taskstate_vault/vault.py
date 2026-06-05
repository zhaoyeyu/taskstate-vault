from __future__ import annotations

from pathlib import Path

from taskstate_vault.contextkernel import ContextKernel
from taskstate_vault.core.paths import TaskStateVaultPaths, resolve_workspace
from taskstate_vault.taskdb import TaskDB
from taskstate_vault.taskfs import TaskFS
from taskstate_vault.ui.server import serve_ui


class TaskStateVault:
    """Unified SDK entry point for CLI, UI, MCP adapters, and Python users."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = resolve_workspace(root)
        self.paths = TaskStateVaultPaths(self.root)
        self.taskfs = TaskFS(self.root)
        self.taskdb = TaskDB(self.root)
        self.contextkernel = ContextKernel(self.root)

    def init(self) -> dict[str, str]:
        return self.taskfs.init()

    def status(self, project_id: str | None = None) -> dict:
        return self.taskfs.status(project_id)

    def serve_ui(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        serve_ui(self.paths, host, port)
