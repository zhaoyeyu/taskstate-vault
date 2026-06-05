from __future__ import annotations

from pathlib import Path
from typing import Any

from taskstate_vault.context.loader import build_context, explain_context
from taskstate_vault.core.paths import TaskStateVaultPaths, resolve_workspace
from taskstate_vault.governor.audit import generate_final_audit
from taskstate_vault.governor.manager import create_project, init_governor, project_status
from taskstate_vault.governor.objectives import change_objective
from taskstate_vault.governor.queue import get_next_action, read_queue, reschedule_queue
from taskstate_vault.kernel.records import add_artifact, add_evidence, add_object, log_error, record_run_note
from taskstate_vault.kernel.run import finish_run, start_run
from taskstate_vault.kernel.task import complete_task, create_task_from_queue, open_task
from taskstate_vault.modes.router import detect_mode
from taskstate_vault.promotion.manager import propose_promotion


class ContextKernel:
    """Public facade for execution modes, Project Governor, tasks, runs, and context loading."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = resolve_workspace(root)
        self.paths = TaskStateVaultPaths(self.root)

    def detect_mode(self, text: str) -> dict[str, Any]:
        return detect_mode(text).to_dict()

    def create_project(
        self,
        title: str,
        input_path: str | None = None,
        execution_mode: str | None = None,
        project_id: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        return create_project(self.paths, title, input_path, execution_mode, project_id, workspace_path)

    def project_status(self, project_id: str | None = None) -> dict[str, Any]:
        return project_status(self.paths, project_id)

    def init_governor(self, project_id: str, input_path: str | None = None, input_text: str | None = None) -> dict[str, Any]:
        return init_governor(self.paths, project_id, input_path, input_text)

    def next_action(self, project_id: str) -> dict[str, Any]:
        return get_next_action(self.paths, project_id)

    def queue(self, project_id: str) -> list[dict[str, Any]]:
        return read_queue(self.paths, project_id)

    def reschedule_queue(self, project_id: str) -> list[dict[str, Any]]:
        return reschedule_queue(self.paths, project_id)

    def create_task_from_queue(self, project_id: str, queue_rank: int = 1) -> dict[str, Any]:
        return create_task_from_queue(self.paths, project_id, queue_rank)

    def open_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        return open_task(self.paths, project_id, task_id)

    def complete_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        return complete_task(self.paths, project_id, task_id)

    def change_objective(
        self,
        project_id: str,
        task_id: str,
        change_type: str,
        new_objective: str | None,
        reason: str,
    ) -> dict[str, Any]:
        return change_objective(self.paths, project_id, task_id, change_type, new_objective, reason)

    def start_run(self, project_id: str, task_id: str) -> dict[str, Any]:
        return start_run(self.paths, project_id, task_id)

    def record_run(self, project_id: str, task_id: str, run_id: str, note: str, kind: str = "output") -> dict[str, Any]:
        return record_run_note(self.paths, project_id, task_id, run_id, note, kind)

    def finish_run(self, project_id: str, task_id: str, run_id: str, status: str, summary: str = "") -> dict[str, Any]:
        return finish_run(self.paths, project_id, task_id, run_id, status, summary)

    def add_evidence(self, project_id: str, task_id: str, kind: str, text: str) -> dict[str, Any]:
        return add_evidence(self.paths, project_id, task_id, kind, text)

    def add_artifact(self, project_id: str, task_id: str, path: str | Path, summary: str, run_id: str | None = None) -> dict[str, Any]:
        return add_artifact(self.paths, project_id, task_id, path, summary, run_id)

    def add_object(self, project_id: str, task_id: str, object_type: str, summary: str, source_ref: str | None = None) -> dict[str, Any]:
        return add_object(self.paths, project_id, task_id, object_type, summary, source_ref)

    def log_error(self, project_id: str, task_id: str, summary: str, run_id: str | None = None) -> dict[str, Any]:
        return log_error(self.paths, project_id, task_id, summary, run_id)

    def build_context(self, project_id: str | None = None, task_id: str | None = None, mode: str | None = None) -> dict[str, Any]:
        return build_context(self.paths, project_id, task_id, mode)

    def explain_context(self, project_id: str, run_id: str | None = None) -> dict[str, Any]:
        return explain_context(self.paths, project_id, run_id)

    def propose_promotion(self, project_id: str, kind: str, summary: str, scope: str = "project") -> dict[str, Any]:
        return propose_promotion(self.paths, project_id, kind, summary, scope)

    def final_audit(self, project_id: str) -> dict[str, Any]:
        return generate_final_audit(self.paths, project_id)
