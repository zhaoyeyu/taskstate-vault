from __future__ import annotations

from pathlib import Path

from taskstate_vault.core.io import ensure_dir, touch
from taskstate_vault.core.paths import TaskStateVaultPaths


def project_dir(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return paths.project_dir(project_id)


def governor_dir(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return project_dir(paths, project_id) / "GOVERNOR"


def project_index_dir(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return project_dir(paths, project_id) / "PROJECT_INDEX"


def project_db(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return project_index_dir(paths, project_id) / "project.sqlite"


def ensure_project_layout(paths: TaskStateVaultPaths, project_id: str) -> Path:
    root = project_dir(paths, project_id)
    for directory in [
        root,
        governor_dir(paths, project_id),
        root / "PROJECT_OBJECTS",
        root / "PROJECT_INDEX",
        root / "PROJECT_LOGS",
        root / "SHARED_ARTIFACTS",
        root / "PROJECT_TOOLS",
        root / "TASKS",
    ]:
        ensure_dir(directory)

    for rel in [
        "GOVERNOR/TASK_GRAPH.jsonl",
        "GOVERNOR/EXECUTION_QUEUE.jsonl",
        "GOVERNOR/BLOCKERS.jsonl",
        "GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl",
        "GOVERNOR/CONTEXT_LOAD_LEDGER.jsonl",
        "GOVERNOR/DECISION_LOG.jsonl",
        "GOVERNOR/OUTCOME_LOG.jsonl",
        "PROJECT_OBJECTS/facts.jsonl",
        "PROJECT_OBJECTS/assumptions.jsonl",
        "PROJECT_OBJECTS/constraints.jsonl",
        "PROJECT_OBJECTS/decisions.jsonl",
        "PROJECT_OBJECTS/strategies.jsonl",
        "PROJECT_OBJECTS/artifacts.jsonl",
        "PROJECT_OBJECTS/tools.jsonl",
        "PROJECT_OBJECTS/templates.jsonl",
        "PROJECT_OBJECTS/promotion_candidates.jsonl",
        "PROJECT_LOGS/event_log.jsonl",
        "PROJECT_LOGS/audit_log.jsonl",
    ]:
        touch(root / rel)
    return root


def graph_path(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return governor_dir(paths, project_id) / "TASK_GRAPH.jsonl"


def queue_path(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return governor_dir(paths, project_id) / "EXECUTION_QUEUE.jsonl"


def blockers_path(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return governor_dir(paths, project_id) / "BLOCKERS.jsonl"


def objective_log_path(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return governor_dir(paths, project_id) / "OBJECTIVE_CHANGE_LOG.jsonl"


def project_event_log(paths: TaskStateVaultPaths, project_id: str) -> Path:
    return project_dir(paths, project_id) / "PROJECT_LOGS" / "event_log.jsonl"

