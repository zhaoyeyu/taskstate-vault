from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from taskstate_vault.context.loader import build_context, explain_context
from taskstate_vault.core.paths import TaskStateVaultPaths, find_workspace, resolve_workspace
from taskstate_vault.governor.audit import generate_final_audit
from taskstate_vault.governor.files import project_dir
from taskstate_vault.governor.graph import read_graph
from taskstate_vault.governor.manager import create_project, init_governor, project_status
from taskstate_vault.governor.objectives import change_objective
from taskstate_vault.governor.queue import get_next_action, read_queue, reschedule_queue
from taskstate_vault.indexing.project_files import index_project_files
from taskstate_vault.indexing.rebuild import rebuild_project_index, rebuild_task_index
from taskstate_vault.kernel.init import init_workspace
from taskstate_vault.kernel.records import add_artifact, add_evidence, add_object, log_error, record_run_note
from taskstate_vault.kernel.run import finish_run, start_run
from taskstate_vault.kernel.task import complete_task, create_task_from_queue, open_task
from taskstate_vault.layers.index import (
    add_account_object,
    add_domain_object,
    import_account_to_task,
    import_domain_to_task,
    layered_search,
    search_account,
    search_domain,
)
from taskstate_vault.modes.router import detect_mode
from taskstate_vault.mcp_adapter import list_tool_specs
from taskstate_vault.promotion.manager import propose_promotion
from taskstate_vault.ui.app_server import serve_ui
from taskstate_vault.ui.server import DEFAULT_ADMIN_USERNAME, reset_admin_password
from taskstate_vault.workspaces.registry import init_task_workspace, register_workspace


def emit(data: Any) -> None:
    if isinstance(data, str):
        text = data
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tsv", description="TaskState Vault CLI")
    parser.add_argument("--root", default=None, help="Workspace root. Defaults to current directory or detected .taskstate-vault parent.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    sub.add_parser("status")

    ui = sub.add_parser("ui")
    ui_sub = ui.add_subparsers(dest="ui_command", required=True)
    ui_serve = ui_sub.add_parser("serve")
    ui_serve.add_argument("--host", default="127.0.0.1")
    ui_serve.add_argument("--port", type=int, default=8765)
    ui_serve.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly allow a non-loopback bind. Use only behind a trusted TLS-capable proxy.",
    )
    ui_sub.add_parser("reset-admin-password")

    mcp = sub.add_parser("mcp")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("tools")

    account = sub.add_parser("account")
    account_sub = account.add_subparsers(dest="account_command", required=True)
    account_add = account_sub.add_parser("add")
    account_add.add_argument("--type", required=True, help="vps_config, local_machine, email_account, preference, constraint, tool, template, playbook, etc.")
    account_add.add_argument("--summary", required=True)
    account_add.add_argument("--content", default="")
    account_add.add_argument("--tag", action="append", default=[])
    account_add.add_argument("--ttl", default="account")
    account_search = account_sub.add_parser("search")
    account_search.add_argument("--query", required=True)
    account_search.add_argument("--limit", type=int, default=10)

    domain = sub.add_parser("domain")
    domain_sub = domain.add_subparsers(dest="domain_command", required=True)
    domain_add = domain_sub.add_parser("add")
    domain_add.add_argument("--domain", default="general")
    domain_add.add_argument("--type", required=True, help="playbook, known_error, template, tool, fact, reusable_fact")
    domain_add.add_argument("--summary", required=True)
    domain_add.add_argument("--content", default="")
    domain_add.add_argument("--tag", action="append", default=[])
    domain_add.add_argument("--ttl", default="domain")
    domain_search = domain_sub.add_parser("search")
    domain_search.add_argument("--domain", default="general")
    domain_search.add_argument("--query", required=True)
    domain_search.add_argument("--limit", type=int, default=10)

    workspace_cmd = sub.add_parser("workspace")
    workspace_sub = workspace_cmd.add_subparsers(dest="workspace_command", required=True)
    workspace_register = workspace_sub.add_parser("register")
    workspace_register.add_argument("--workspace", required=True)
    workspace_register.add_argument("--project", default=None)
    workspace_register.add_argument("--task", default=None)
    workspace_register.add_argument("--summary", default="")
    workspace_register.add_argument("--initialized-taskstate-vault", action="store_true")
    workspace_init_task = workspace_sub.add_parser("init-task")
    workspace_init_task.add_argument("--workspace", required=True)
    workspace_init_task.add_argument("--project", required=True)
    workspace_init_task.add_argument("--task", default=None)
    workspace_init_task.add_argument("--summary", default="")

    layer = sub.add_parser("layer")
    layer_sub = layer.add_subparsers(dest="layer_command", required=True)
    layer_search_cmd = layer_sub.add_parser("search")
    layer_search_cmd.add_argument("--query", required=True)
    layer_search_cmd.add_argument("--project", default=None)
    layer_search_cmd.add_argument("--task", default=None)
    layer_search_cmd.add_argument("--domain", default="general")
    layer_search_cmd.add_argument("--limit", type=int, default=10)
    layer_import_acct = layer_sub.add_parser("import-account")
    layer_import_acct.add_argument("--query", required=True)
    layer_import_acct.add_argument("--project", required=True)
    layer_import_acct.add_argument("--task", required=True)
    layer_import_acct.add_argument("--limit", type=int, default=3)
    layer_import_acct.add_argument("--reason", default="")
    layer_import_domain = layer_sub.add_parser("import-domain")
    layer_import_domain.add_argument("--query", required=True)
    layer_import_domain.add_argument("--project", required=True)
    layer_import_domain.add_argument("--task", required=True)
    layer_import_domain.add_argument("--domain", default="general")
    layer_import_domain.add_argument("--limit", type=int, default=3)
    layer_import_domain.add_argument("--reason", default="")

    mode = sub.add_parser("mode")
    mode_sub = mode.add_subparsers(dest="mode_command", required=True)
    detect = mode_sub.add_parser("detect")
    detect.add_argument("--text", default="")
    detect.add_argument("--input", default=None)
    set_mode = mode_sub.add_parser("set")
    set_mode.add_argument("execution_mode")
    set_mode.add_argument("--project", required=True)

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    create = project_sub.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--input", default=None)
    create.add_argument("--mode", default=None)
    create.add_argument("--project-id", default=None)
    create.add_argument("--workspace", default=None)
    open_p = project_sub.add_parser("open")
    open_p.add_argument("project_id")
    project_sub.add_parser("progress").add_argument("project_id")
    project_sub.add_parser("audit").add_argument("project_id")
    project_sub.add_parser("context").add_argument("project_id")

    governor = sub.add_parser("governor")
    gov_sub = governor.add_subparsers(dest="governor_command", required=True)
    gov_init = gov_sub.add_parser("init")
    gov_init.add_argument("--project", required=True)
    gov_init.add_argument("--input", default=None)
    gov_sub.add_parser("model").add_argument("--project", required=True)
    gov_sub.add_parser("graph").add_argument("--project", required=True)
    gov_sub.add_parser("queue").add_argument("--project", required=True)
    gov_sub.add_parser("next").add_argument("--project", required=True)
    gov_sub.add_parser("reschedule").add_argument("--project", required=True)
    gov_sub.add_parser("complete").add_argument("--project", required=True)

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_create = task_sub.add_parser("create")
    task_create.add_argument("--project", required=True)
    task_create.add_argument("--queue-rank", type=int, default=1)
    task_open = task_sub.add_parser("open")
    task_open.add_argument("task_id")
    task_open.add_argument("--project", required=True)
    for name in ["split", "merge", "defer", "replace-objective"]:
        p = task_sub.add_parser(name)
        p.add_argument("task_id")
        p.add_argument("--project", required=True)
        p.add_argument("--new", default=None)
        p.add_argument("--reason", required=True)
    task_complete = task_sub.add_parser("complete")
    task_complete.add_argument("task_id")
    task_complete.add_argument("--project", required=True)

    run = sub.add_parser("run")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    run_start = run_sub.add_parser("start")
    run_start.add_argument("--project", required=True)
    run_start.add_argument("--task", required=True)
    run_finish = run_sub.add_parser("finish")
    run_finish.add_argument("run_id")
    run_finish.add_argument("--project", required=True)
    run_finish.add_argument("--task", required=True)
    run_finish.add_argument("--status", required=True, choices=["success", "failed", "partial"])
    run_finish.add_argument("--summary", default="")
    run_record = run_sub.add_parser("record")
    run_record.add_argument("run_id")
    run_record.add_argument("--project", required=True)
    run_record.add_argument("--task", required=True)
    run_record.add_argument("--kind", default="output")
    run_record.add_argument("--note", required=True)

    obj = sub.add_parser("object")
    obj_sub = obj.add_subparsers(dest="object_command", required=True)
    obj_add = obj_sub.add_parser("add")
    obj_add.add_argument("--project", required=True)
    obj_add.add_argument("--task", required=True)
    obj_add.add_argument("--type", required=True)
    obj_add.add_argument("--summary", required=True)
    obj_add.add_argument("--source-ref", default=None)

    evidence = sub.add_parser("evidence")
    ev_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    ev_add = ev_sub.add_parser("add")
    ev_add.add_argument("--project", required=True)
    ev_add.add_argument("--task", required=True)
    ev_add.add_argument("--kind", default="user_messages")
    ev_add.add_argument("--text", required=True)

    artifact = sub.add_parser("artifact")
    art_sub = artifact.add_subparsers(dest="artifact_command", required=True)
    art_add = art_sub.add_parser("add")
    art_add.add_argument("--project", required=True)
    art_add.add_argument("--task", required=True)
    art_add.add_argument("--path", required=True)
    art_add.add_argument("--summary", required=True)
    art_add.add_argument("--run", default=None)

    error = sub.add_parser("error")
    err_sub = error.add_subparsers(dest="error_command", required=True)
    err_log = err_sub.add_parser("log")
    err_log.add_argument("--project", required=True)
    err_log.add_argument("--task", required=True)
    err_log.add_argument("--summary", required=True)
    err_log.add_argument("--run", default=None)

    context = sub.add_parser("context")
    ctx_sub = context.add_subparsers(dest="context_command", required=True)
    ctx_build = ctx_sub.add_parser("build")
    ctx_build.add_argument("--project", default=None)
    ctx_build.add_argument("--task", default=None)
    ctx_build.add_argument("--mode", default=None)
    ctx_explain = ctx_sub.add_parser("explain")
    ctx_explain.add_argument("--project", required=True)
    ctx_explain.add_argument("--run", default=None)

    promote = sub.add_parser("promote")
    promote_sub = promote.add_subparsers(dest="promote_command", required=True)
    propose = promote_sub.add_parser("propose")
    propose.add_argument("--project", required=True)
    propose.add_argument("--kind", required=True)
    propose.add_argument("--summary", required=True)
    propose.add_argument("--scope", default="project")

    index = sub.add_parser("index")
    index_sub = index.add_subparsers(dest="index_command", required=True)
    rebuild = index_sub.add_parser("rebuild")
    rebuild.add_argument("--project", required=True)
    rebuild.add_argument("--task", default=None)
    project_files = index_sub.add_parser("project-files")
    project_files.add_argument("--project", required=True)
    project_files.add_argument("--path", required=True)

    return parser


def workspace_from_args(args: argparse.Namespace) -> Path:
    if args.root:
        return resolve_workspace(args.root)
    return find_workspace()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = workspace_from_args(args)
    paths = TaskStateVaultPaths(workspace)

    if args.command == "init":
        emit(init_workspace(workspace))
        return 0

    if args.command == "status":
        emit(project_status(paths))
        return 0

    if args.command == "ui":
        if args.ui_command == "serve":
            serve_ui(paths, args.host, args.port, allow_network=args.allow_network)
            return 0
        if args.ui_command == "reset-admin-password":
            emit(
                {
                    "username": DEFAULT_ADMIN_USERNAME,
                    "temporary_password": reset_admin_password(paths),
                    "message": "Sign in with this generated password and change it from Settings.",
                }
            )
            return 0

    if args.command == "mcp":
        if args.mcp_command == "tools":
            emit(list_tool_specs())
            return 0

    if args.command == "account":
        if args.account_command == "add":
            emit(add_account_object(paths, args.type, args.summary, args.content, args.tag, args.ttl))
            return 0
        if args.account_command == "search":
            emit(search_account(paths, args.query, args.limit))
            return 0

    if args.command == "domain":
        if args.domain_command == "add":
            emit(add_domain_object(paths, args.domain, args.type, args.summary, args.content, args.tag, args.ttl))
            return 0
        if args.domain_command == "search":
            emit(search_domain(paths, args.domain, args.query, args.limit))
            return 0

    if args.command == "workspace":
        if args.workspace_command == "register":
            emit(register_workspace(paths, args.workspace, args.project, args.task, args.summary, args.initialized_taskstate_vault))
            return 0
        if args.workspace_command == "init-task":
            emit(init_task_workspace(paths, args.workspace, args.project, args.task, args.summary))
            return 0

    if args.command == "layer":
        if args.layer_command == "search":
            emit(layered_search(paths, args.query, args.project, args.task, args.domain, args.limit))
            return 0
        if args.layer_command == "import-account":
            emit(import_account_to_task(paths, args.project, args.task, args.query, args.limit, args.reason))
            return 0
        if args.layer_command == "import-domain":
            emit(import_domain_to_task(paths, args.project, args.task, args.domain, args.query, args.limit, args.reason))
            return 0

    if args.command == "mode":
        if args.mode_command == "detect":
            text = args.text
            if args.input:
                text += "\n" + Path(args.input).read_text(encoding="utf-8")
            emit(detect_mode(text).to_dict())
            return 0
        if args.mode_command == "set":
            from taskstate_vault.core import yamlish
            from taskstate_vault.modes.router import normalize_mode

            normalized = normalize_mode(args.execution_mode)
            manifest_path = paths.project_dir(args.project) / "PROJECT_MANIFEST.yaml"
            manifest = yamlish.read(manifest_path, default={})
            manifest["execution_mode"] = normalized
            yamlish.write(manifest_path, manifest)
            emit({"project_id": args.project, "execution_mode": normalized})
            return 0

    if args.command == "project":
        if args.project_command == "create":
            emit(create_project(paths, args.title, input_path=args.input, execution_mode=args.mode, project_id=args.project_id, workspace_path=args.workspace))
            return 0
        if args.project_command == "open":
            emit(project_status(paths, args.project_id))
            return 0
        if args.project_command == "progress":
            emit(project_status(paths, args.project_id).get("project_progress", {}))
            return 0
        if args.project_command == "audit":
            emit(generate_final_audit(paths, args.project_id))
            return 0
        if args.project_command == "context":
            emit(build_context(paths, project_id=args.project_id))
            return 0

    if args.command == "governor":
        if args.governor_command == "init":
            emit(init_governor(paths, args.project, input_path=args.input))
            return 0
        if args.governor_command == "model":
            from taskstate_vault.core import yamlish

            emit(yamlish.read(project_dir(paths, args.project) / "PROJECT_MODEL.yaml", default={}))
            return 0
        if args.governor_command == "graph":
            emit(read_graph(paths, args.project))
            return 0
        if args.governor_command == "queue":
            emit(read_queue(paths, args.project))
            return 0
        if args.governor_command == "next":
            emit(get_next_action(paths, args.project))
            return 0
        if args.governor_command == "reschedule":
            emit(reschedule_queue(paths, args.project))
            return 0
        if args.governor_command == "complete":
            emit(generate_final_audit(paths, args.project))
            return 0

    if args.command == "task":
        if args.task_command == "create":
            emit(create_task_from_queue(paths, args.project, args.queue_rank))
            return 0
        if args.task_command == "open":
            emit(open_task(paths, args.project, args.task_id))
            return 0
        if args.task_command in {"split", "merge", "defer", "replace-objective"}:
            emit(change_objective(paths, args.project, args.task_id, args.task_command, args.new, args.reason))
            return 0
        if args.task_command == "complete":
            emit(complete_task(paths, args.project, args.task_id))
            return 0

    if args.command == "run":
        if args.run_command == "start":
            emit(start_run(paths, args.project, args.task))
            return 0
        if args.run_command == "finish":
            emit(finish_run(paths, args.project, args.task, args.run_id, args.status, args.summary))
            return 0
        if args.run_command == "record":
            emit(record_run_note(paths, args.project, args.task, args.run_id, args.note, args.kind))
            return 0

    if args.command == "object":
        if args.object_command == "add":
            emit(add_object(paths, args.project, args.task, args.type, args.summary, args.source_ref))
            return 0

    if args.command == "evidence":
        if args.evidence_command == "add":
            emit(add_evidence(paths, args.project, args.task, args.kind, args.text))
            return 0

    if args.command == "artifact":
        if args.artifact_command == "add":
            emit(add_artifact(paths, args.project, args.task, args.path, args.summary, args.run))
            return 0

    if args.command == "error":
        if args.error_command == "log":
            emit(log_error(paths, args.project, args.task, args.summary, args.run))
            return 0

    if args.command == "context":
        if args.context_command == "build":
            emit(build_context(paths, project_id=args.project, task_id=args.task, mode=args.mode))
            return 0
        if args.context_command == "explain":
            emit(explain_context(paths, args.project, args.run))
            return 0

    if args.command == "promote":
        if args.promote_command == "propose":
            emit(propose_promotion(paths, args.project, args.kind, args.summary, args.scope))
            return 0

    if args.command == "index":
        if args.index_command == "rebuild":
            if args.task:
                emit(rebuild_task_index(paths, args.project, args.task))
            else:
                emit(rebuild_project_index(paths, args.project))
            return 0
        if args.index_command == "project-files":
            emit(index_project_files(paths, args.project, args.path))
            return 0

    parser.error("Unhandled command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
