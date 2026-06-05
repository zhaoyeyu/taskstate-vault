from __future__ import annotations

from pathlib import Path
from typing import Any

from taskstate_vault.core.paths import TaskStateVaultPaths, resolve_workspace
from taskstate_vault.indexing.project_files import index_project_files
from taskstate_vault.indexing.rebuild import rebuild_project_index, rebuild_task_index
from taskstate_vault.layers.index import (
    add_account_object,
    add_domain_object,
    import_account_to_task,
    import_domain_to_task,
    layered_search,
    search_account,
    search_domain,
)


class TaskDB:
    """Public facade for TaskState Vault indexes and layered search."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = resolve_workspace(root)
        self.paths = TaskStateVaultPaths(self.root)

    def add_account_object(
        self,
        object_type: str,
        summary: str,
        content: str = "",
        tags: list[str] | None = None,
        ttl: str = "account",
    ) -> dict[str, Any]:
        return add_account_object(self.paths, object_type, summary, content, tags or [], ttl)

    def search_account(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return search_account(self.paths, query, limit)

    def add_domain_object(
        self,
        domain_id: str,
        object_type: str,
        summary: str,
        content: str = "",
        tags: list[str] | None = None,
        ttl: str = "domain",
    ) -> dict[str, Any]:
        return add_domain_object(self.paths, domain_id, object_type, summary, content, tags or [], ttl)

    def search_domain(self, domain_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return search_domain(self.paths, domain_id, query, limit)

    def layered_search(
        self,
        query: str,
        project_id: str | None = None,
        task_id: str | None = None,
        domain_id: str = "general",
        limit: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        return layered_search(self.paths, query, project_id, task_id, domain_id, limit)

    def import_account_to_task(
        self,
        project_id: str,
        task_id: str,
        query: str,
        limit: int = 3,
        reason: str = "",
    ) -> dict[str, Any]:
        return import_account_to_task(self.paths, project_id, task_id, query, limit, reason)

    def import_domain_to_task(
        self,
        project_id: str,
        task_id: str,
        domain_id: str,
        query: str,
        limit: int = 3,
        reason: str = "",
    ) -> dict[str, Any]:
        return import_domain_to_task(self.paths, project_id, task_id, domain_id, query, limit, reason)

    def index_project_files(self, project_id: str, path: str | Path) -> dict[str, Any]:
        return index_project_files(self.paths, project_id, path)

    def rebuild_project_index(self, project_id: str) -> dict[str, Any]:
        return rebuild_project_index(self.paths, project_id)

    def rebuild_task_index(self, project_id: str, task_id: str) -> dict[str, Any]:
        return rebuild_task_index(self.paths, project_id, task_id)
