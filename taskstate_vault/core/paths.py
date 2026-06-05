from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TASKSTATE_VAULT_DIR = ".taskstate-vault"


@dataclass(frozen=True)
class TaskStateVaultPaths:
    workspace: Path

    @property
    def os_dir(self) -> Path:
        return self.workspace / TASKSTATE_VAULT_DIR

    @property
    def system_dir(self) -> Path:
        return self.os_dir / "SYSTEM"

    @property
    def projects_dir(self) -> Path:
        return self.os_dir / "PROJECTS"

    @property
    def account_dir(self) -> Path:
        return self.os_dir / "ACCOUNT"

    @property
    def domains_dir(self) -> Path:
        return self.os_dir / "DOMAINS"

    @property
    def portfolios_dir(self) -> Path:
        return self.os_dir / "PORTFOLIOS"

    @property
    def programs_dir(self) -> Path:
        return self.os_dir / "PROGRAMS"

    @property
    def archive_dir(self) -> Path:
        return self.os_dir / "ARCHIVE"

    @property
    def trash_dir(self) -> Path:
        return self.os_dir / "TRASH"

    @property
    def kernel_db(self) -> Path:
        return self.os_dir / "kernel.sqlite"

    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def domain_dir(self, domain_id: str) -> Path:
        return self.domains_dir / domain_id

    def task_dir(self, project_id: str, task_id: str) -> Path:
        return self.project_dir(project_id) / "TASKS" / task_id

    @property
    def account_index_db(self) -> Path:
        return self.account_dir / "ACCOUNT_INDEX" / "account.sqlite"

    def domain_index_db(self, domain_id: str) -> Path:
        return self.domain_dir(domain_id) / "DOMAIN_INDEX" / "domain.sqlite"


def resolve_workspace(root: str | Path | None = None) -> Path:
    return Path(root).resolve() if root else Path.cwd().resolve()


def find_workspace(start: str | Path | None = None) -> Path:
    current = resolve_workspace(start)
    for candidate in [current, *current.parents]:
        if (candidate / TASKSTATE_VAULT_DIR).exists():
            return candidate
    return current


TaskFSPaths = TaskStateVaultPaths
