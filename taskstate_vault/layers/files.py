from __future__ import annotations

from pathlib import Path

from taskstate_vault.core.io import ensure_dir, touch
from taskstate_vault.core.paths import TaskStateVaultPaths


ACCOUNT_OBJECT_FILES = [
    "global_facts.jsonl",
    "project_refs.jsonl",
    "workspace_refs.jsonl",
    "user_preferences.jsonl",
    "stable_constraints.jsonl",
    "vps_configs.jsonl",
    "local_machines.jsonl",
    "email_accounts.jsonl",
    "service_accounts.jsonl",
    "tool_manifests.jsonl",
    "templates.jsonl",
    "playbooks.jsonl",
    "known_errors.jsonl",
]

DOMAIN_OBJECT_FILES = [
    "domain_facts.jsonl",
    "playbooks.jsonl",
    "known_errors.jsonl",
    "templates.jsonl",
    "tool_manifests.jsonl",
    "reusable_facts.jsonl",
]


def ensure_account_layout(paths: TaskStateVaultPaths) -> None:
    for directory in [
        paths.account_dir / "PROFILE",
        paths.account_dir / "GLOBAL_OBJECTS",
        paths.account_dir / "GLOBAL_INDEX",
        paths.account_dir / "GLOBAL_LOGS",
        paths.account_dir / "GLOBAL_TOOLS" / "manifests",
        paths.account_dir / "GLOBAL_TOOLS" / "scripts",
        paths.account_dir / "GLOBAL_TEMPLATES",
        paths.account_dir / "ACCOUNT_INDEX",
    ]:
        ensure_dir(directory)
    for rel in [
        "PROFILE/initial_state.yaml",
        "PROFILE/user_preferences.yaml",
        "PROFILE/stable_constraints.yaml",
        "PROFILE/communication_policy.yaml",
        "GLOBAL_LOGS/event_log.jsonl",
        "GLOBAL_LOGS/import_log.jsonl",
    ]:
        touch(paths.account_dir / rel)
    for filename in ACCOUNT_OBJECT_FILES:
        touch(paths.account_dir / "GLOBAL_OBJECTS" / filename)


def ensure_domain_layout(paths: TaskStateVaultPaths, domain_id: str = "general") -> Path:
    root = paths.domain_dir(domain_id)
    for directory in [
        root,
        root / "DOMAIN_OBJECTS",
        root / "DOMAIN_INDEX",
        root / "DOMAIN_LOGS",
        root / "tools",
        root / "templates",
        root / "playbooks",
    ]:
        ensure_dir(directory)
    for rel in ["DOMAIN_STATE.yaml", "DOMAIN_LOGS/event_log.jsonl"]:
        touch(root / rel)
    for filename in DOMAIN_OBJECT_FILES:
        touch(root / "DOMAIN_OBJECTS" / filename)
    return root


def account_objects_path(paths: TaskStateVaultPaths, object_type: str) -> Path:
    mapping = {
        "project_ref": "project_refs.jsonl",
        "workspace_ref": "workspace_refs.jsonl",
        "vps_config": "vps_configs.jsonl",
        "local_machine": "local_machines.jsonl",
        "email_account": "email_accounts.jsonl",
        "service_account": "service_accounts.jsonl",
        "preference": "user_preferences.jsonl",
        "constraint": "stable_constraints.jsonl",
        "tool": "tool_manifests.jsonl",
        "template": "templates.jsonl",
        "playbook": "playbooks.jsonl",
        "known_error": "known_errors.jsonl",
    }
    return paths.account_dir / "GLOBAL_OBJECTS" / mapping.get(object_type, "global_facts.jsonl")


def domain_objects_path(paths: TaskStateVaultPaths, domain_id: str, object_type: str) -> Path:
    mapping = {
        "playbook": "playbooks.jsonl",
        "known_error": "known_errors.jsonl",
        "template": "templates.jsonl",
        "tool": "tool_manifests.jsonl",
        "fact": "domain_facts.jsonl",
        "reusable_fact": "reusable_facts.jsonl",
    }
    return paths.domain_dir(domain_id) / "DOMAIN_OBJECTS" / mapping.get(object_type, "domain_facts.jsonl")
