from __future__ import annotations

from pathlib import Path

from taskstate_vault.core import yamlish
from taskstate_vault.core.db import init_kernel_db, init_layer_index_db
from taskstate_vault.core.io import ensure_dir, read_text, touch, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths, resolve_workspace
from taskstate_vault.layers.files import ensure_account_layout, ensure_domain_layout
from taskstate_vault.templates.system import (
    CODEX_USAGE_GUIDE_ACCOUNT,
    ENTRYPOINT,
    EXECUTION_MODES,
    GOVERNOR_PROTOCOL,
    READ_PROTOCOL,
    ROUTER_RULES,
    SCHEMA,
    WRITE_PROTOCOL,
)


def init_workspace(root: str | Path | None = None) -> dict[str, str]:
    workspace = resolve_workspace(root)
    paths = TaskStateVaultPaths(workspace)

    for directory in [
        paths.os_dir,
        paths.system_dir,
        paths.account_dir,
        paths.domains_dir,
        paths.portfolios_dir,
        paths.programs_dir,
        paths.projects_dir,
        paths.archive_dir,
        paths.trash_dir,
        paths.system_dir / "MIGRATIONS",
        paths.system_dir / "TEMPLATES",
    ]:
        ensure_dir(directory)

    write_text(paths.system_dir / "ENTRYPOINT.md", ENTRYPOINT)
    write_text(paths.system_dir / "GOVERNOR_PROTOCOL.md", GOVERNOR_PROTOCOL)
    write_text(paths.system_dir / "READ_PROTOCOL.md", READ_PROTOCOL)
    write_text(paths.system_dir / "WRITE_PROTOCOL.md", WRITE_PROTOCOL)
    write_text(paths.system_dir / "SCHEMA.md", SCHEMA)
    yamlish.write(paths.system_dir / "EXECUTION_MODES.yaml", EXECUTION_MODES)
    yamlish.write(paths.system_dir / "ROUTER_RULES.yaml", ROUTER_RULES)

    touch(paths.os_dir / "task_registry.jsonl")
    touch(paths.os_dir / "project_registry.jsonl")
    touch(paths.os_dir / "run_registry.jsonl")
    init_kernel_db(paths.kernel_db)
    ensure_account_layout(paths)
    ensure_domain_layout(paths, "general")
    init_layer_index_db(paths.account_index_db)
    init_layer_index_db(paths.domain_index_db("general"))
    _write_initial_profile_files(paths)

    return {
        "workspace": str(workspace),
        "taskfs": str(paths.os_dir),
        "kernel_db": str(paths.kernel_db),
    }


def _write_initial_profile_files(paths: TaskStateVaultPaths) -> None:
    initial = paths.account_dir / "PROFILE" / "initial_state.yaml"
    if not read_text(initial).strip():
        yamlish.write(
            initial,
            {
                "schema_version": 1,
                "purpose": "Account-level initial state for TaskState Vault.",
                "global_info_slots": {
                    "project_refs": "ACCOUNT/GLOBAL_OBJECTS/project_refs.jsonl",
                    "workspace_refs": "ACCOUNT/GLOBAL_OBJECTS/workspace_refs.jsonl",
                    "vps_configs": "ACCOUNT/GLOBAL_OBJECTS/vps_configs.jsonl",
                    "local_machines": "ACCOUNT/GLOBAL_OBJECTS/local_machines.jsonl",
                    "email_accounts": "ACCOUNT/GLOBAL_OBJECTS/email_accounts.jsonl",
                    "service_accounts": "ACCOUNT/GLOBAL_OBJECTS/service_accounts.jsonl",
                    "user_preferences": "ACCOUNT/GLOBAL_OBJECTS/user_preferences.jsonl",
                    "stable_constraints": "ACCOUNT/GLOBAL_OBJECTS/stable_constraints.jsonl",
                    "tool_manifests": "ACCOUNT/GLOBAL_OBJECTS/tool_manifests.jsonl",
                    "templates": "ACCOUNT/GLOBAL_OBJECTS/templates.jsonl",
                    "playbooks": "ACCOUNT/GLOBAL_OBJECTS/playbooks.jsonl",
                },
                "index": "ACCOUNT/ACCOUNT_INDEX/account.sqlite",
                "instruction": "Global facts mentioned by the user, such as VPS configs, local machine parameters, and email accounts, should be stored at account layer and indexed before being imported into task-level copies.",
            },
        )
    usage = paths.account_dir / "PROFILE" / "CODEX_USAGE_GUIDE.md"
    if not read_text(usage).strip():
        write_text(usage, CODEX_USAGE_GUIDE_ACCOUNT)
