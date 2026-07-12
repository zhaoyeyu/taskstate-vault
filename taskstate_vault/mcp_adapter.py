"""MCP-ready adapter layer for TaskState Vault.

This module intentionally avoids a hard dependency on a specific MCP SDK. It
exposes stable JSON-callable functions that can be wrapped by an MCP server or
daemon later without changing the core implementation.
"""

from __future__ import annotations

from typing import Any

from taskstate_vault.context.loader import build_context
from taskstate_vault.core.paths import TaskStateVaultPaths, resolve_workspace
from taskstate_vault.governor.manager import create_project, init_governor
from taskstate_vault.governor.objectives import change_objective
from taskstate_vault.governor.queue import get_next_action, reschedule_queue
from taskstate_vault.indexing.project_files import index_project_files
from taskstate_vault.kernel.records import add_artifact, add_evidence, log_error
from taskstate_vault.kernel.run import finish_run, start_run
from taskstate_vault.kernel.task import create_task_from_queue
from taskstate_vault.layers.index import add_account_object, import_account_to_task, layered_search
from taskstate_vault.workspaces.registry import init_task_workspace, register_workspace


def call_tool(tool_name: str, arguments: dict[str, Any], root: str | None = None) -> dict[str, Any]:
    tool_name = _normalize_tool_name(tool_name)
    paths = TaskStateVaultPaths(resolve_workspace(root))
    if tool_name == "taskstate_vault_get_startup_context":
        return build_context(paths, project_id=arguments.get("project_id"), task_id=arguments.get("task_id"), mode=arguments.get("mode"))
    if tool_name == "taskstate_vault_create_project":
        return create_project(
            paths,
            arguments["title"],
            execution_mode=arguments.get("execution_mode"),
            project_id=arguments.get("project_id"),
            workspace_path=arguments.get("workspace_path"),
        )
    if tool_name == "taskstate_vault_init_governor":
        return init_governor(paths, arguments["project_id"], input_text=arguments.get("input_text", ""))
    if tool_name == "taskstate_vault_get_next_action":
        return get_next_action(paths, arguments["project_id"])
    if tool_name == "taskstate_vault_create_task_from_queue":
        return create_task_from_queue(paths, arguments["project_id"], arguments.get("queue_rank", 1))
    if tool_name == "taskstate_vault_start_run":
        return start_run(paths, arguments["project_id"], arguments["task_id"])
    if tool_name == "taskstate_vault_record_run_finished":
        return finish_run(paths, arguments["project_id"], arguments["task_id"], arguments["run_id"], arguments["status"], arguments.get("summary", ""))
    if tool_name == "taskstate_vault_reschedule_queue":
        return reschedule_queue(paths, arguments["project_id"])
    if tool_name == "taskstate_vault_log_objective_change":
        return change_objective(
            paths,
            arguments["project_id"],
            arguments["task_id"],
            arguments["change_type"],
            arguments.get("new_objective"),
            arguments["reason"],
        )
    if tool_name == "taskstate_vault_add_evidence":
        return add_evidence(paths, arguments["project_id"], arguments["task_id"], arguments.get("kind", "user_messages"), arguments["text"])
    if tool_name == "taskstate_vault_add_artifact":
        return add_artifact(paths, arguments["project_id"], arguments["task_id"], arguments["path"], arguments["summary"], arguments.get("run_id"))
    if tool_name == "taskstate_vault_log_error":
        return log_error(paths, arguments["project_id"], arguments["task_id"], arguments["summary"], arguments.get("run_id"))
    if tool_name == "taskstate_vault_add_account_object":
        return add_account_object(
            paths,
            arguments["object_type"],
            arguments["summary"],
            arguments.get("content", ""),
            arguments.get("tags", []),
            arguments.get("ttl", "account"),
        )
    if tool_name == "taskstate_vault_layered_search":
        return layered_search(
            paths,
            arguments["query"],
            arguments.get("project_id"),
            arguments.get("task_id"),
            arguments.get("domain_id", "general"),
            arguments.get("limit", 10),
        )
    if tool_name == "taskstate_vault_import_account_to_task":
        return import_account_to_task(paths, arguments["project_id"], arguments["task_id"], arguments["query"], arguments.get("limit", 3), arguments.get("reason", ""))
    if tool_name == "taskstate_vault_register_workspace":
        return register_workspace(
            paths,
            arguments["workspace_path"],
            arguments.get("project_id"),
            arguments.get("task_id"),
            arguments.get("summary", ""),
            arguments.get("initialized_taskstate_vault", False),
        )
    if tool_name == "taskstate_vault_init_task_workspace":
        return init_task_workspace(
            paths,
            arguments["workspace_path"],
            arguments["project_id"],
            arguments.get("task_id"),
            arguments.get("summary", ""),
        )
    if tool_name == "taskstate_vault_index_project_files":
        return index_project_files(paths, arguments["project_id"], arguments["path"])
    raise ValueError(f"Unknown TaskState Vault tool: {tool_name}")


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        _tool("tsv_get_startup_context", "Build startup context for a project/task.", ["project_id", "task_id", "mode"]),
        _tool("tsv_create_project", "Create a TaskState Vault project and optional Project Governor state.", ["title", "execution_mode", "project_id", "workspace_path"]),
        _tool("tsv_init_governor", "Initialize Project Governor files for an existing project.", ["project_id", "input_text"]),
        _tool("tsv_get_next_action", "Read the highest-priority ready queue item.", ["project_id"]),
        _tool("tsv_create_task_from_queue", "Create a task instance from an execution-queue item.", ["project_id", "queue_rank"]),
        _tool("tsv_start_run", "Start a run record for a task.", ["project_id", "task_id"]),
        _tool("tsv_record_run_finished", "Finish a task run with status and summary.", ["project_id", "task_id", "run_id", "status", "summary"]),
        _tool("tsv_reschedule_queue", "Recompute execution queue order from the task graph.", ["project_id"]),
        _tool("tsv_log_objective_change", "Record a local task objective change under the stable project intent.", ["project_id", "task_id", "change_type", "new_objective", "reason"]),
        _tool("tsv_add_evidence", "Add task evidence.", ["project_id", "task_id", "kind", "text"]),
        _tool("tsv_add_artifact", "Add a task artifact record.", ["project_id", "task_id", "path", "summary", "run_id"]),
        _tool("tsv_log_error", "Log a task error record.", ["project_id", "task_id", "summary", "run_id"]),
        _tool("tsv_add_account_object", "Store reusable account-level information.", ["object_type", "summary", "content", "tags", "ttl"]),
        _tool("tsv_layered_search", "Search task, project, domain, and account indexes.", ["query", "project_id", "task_id", "domain_id", "limit"]),
        _tool("tsv_import_account_to_task", "Copy matching account objects into task scope with source pointers.", ["project_id", "task_id", "query", "limit", "reason"]),
        _tool("tsv_register_workspace", "Register an external workspace in the account index.", ["workspace_path", "project_id", "task_id", "summary", "initialized_taskstate_vault"]),
        _tool("tsv_init_task_workspace", "Create a task workspace link in an external workspace.", ["workspace_path", "project_id", "task_id", "summary"]),
        _tool("tsv_index_project_files", "Index files from a project workspace into TaskDB.", ["project_id", "path"]),
    ]


def _tool(name: str, description: str, fields: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {field: {"type": "string"} for field in fields},
            "additionalProperties": True,
        },
    }


def _normalize_tool_name(tool_name: str) -> str:
    if tool_name.startswith("tsv_"):
        return "taskstate_vault_" + tool_name[4:]
    if tool_name.startswith("taskstate_vault_"):
        return "taskstate_vault_" + tool_name[len("taskstate_vault_") :]
    return tool_name


TOOL_NAMES = [
    "tsv_get_startup_context",
    "tsv_create_project",
    "tsv_init_governor",
    "tsv_get_next_action",
    "tsv_create_task_from_queue",
    "tsv_start_run",
    "tsv_record_run_finished",
    "tsv_reschedule_queue",
    "tsv_log_objective_change",
    "tsv_add_evidence",
    "tsv_add_artifact",
    "tsv_log_error",
    "tsv_add_account_object",
    "tsv_layered_search",
    "tsv_import_account_to_task",
    "tsv_register_workspace",
    "tsv_init_task_workspace",
    "tsv_index_project_files",
    "taskstate_vault_get_startup_context",
    "taskstate_vault_create_project",
    "taskstate_vault_init_governor",
    "taskstate_vault_get_next_action",
    "taskstate_vault_create_task_from_queue",
    "taskstate_vault_start_run",
    "taskstate_vault_record_run_finished",
    "taskstate_vault_reschedule_queue",
    "taskstate_vault_log_objective_change",
    "taskstate_vault_add_evidence",
    "taskstate_vault_add_artifact",
    "taskstate_vault_log_error",
    "taskstate_vault_add_account_object",
    "taskstate_vault_layered_search",
    "taskstate_vault_import_account_to_task",
    "taskstate_vault_register_workspace",
    "taskstate_vault_init_task_workspace",
    "taskstate_vault_index_project_files",
]
