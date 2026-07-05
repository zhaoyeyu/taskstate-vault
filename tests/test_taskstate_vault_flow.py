from __future__ import annotations

import tempfile
import unittest
import shutil
import uuid
from pathlib import Path

_TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp-test"
_TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


class _WorkspaceTemporaryDirectory:
    def __init__(self) -> None:
        self.name = str(_TEST_TMP_ROOT / f"tmp-{uuid.uuid4().hex}")

    def __enter__(self) -> str:
        Path(self.name).mkdir(parents=True, exist_ok=False)
        return self.name

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.name, ignore_errors=True)


tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory

from taskstate_vault import ContextKernel, TaskDB, TaskFS, TaskStateVault
from taskstate_vault.cli.main import main as taskstate_vault_main
from taskstate_vault.context.loader import build_context
from taskstate_vault.core import yamlish
from taskstate_vault.core.io import read_jsonl
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.governor.audit import generate_final_audit
from taskstate_vault.governor.manager import create_project
from taskstate_vault.governor.objectives import change_objective
from taskstate_vault.governor.queue import get_next_action
from taskstate_vault.indexing.project_files import index_project_files
from taskstate_vault.kernel.init import init_workspace
from taskstate_vault.kernel.run import finish_run, start_run
from taskstate_vault.kernel.task import complete_task, create_task_from_queue
from taskstate_vault.layers.index import add_account_object, import_account_to_task, layered_search, search_account
from taskstate_vault.mcp_adapter import call_tool, list_tool_specs
from taskstate_vault.modes.router import detect_mode
from taskstate_vault.promotion.manager import propose_promotion
from taskstate_vault.ui.server import (
    add_dependency,
    add_task_record,
    archive_project,
    archive_project_group,
    archive_task,
    build_summary,
    cleanup_taskfs_backups,
    collect_log_records,
    create_child_task,
    create_project_from_ui,
    create_project_group,
    graph_backups,
    insert_queue_item,
    permanent_delete_task,
    permanent_delete_project,
    promote_log_record,
    project_impact_preview,
    render_dashboard,
    render_editor,
    render_file_diff_preview,
    render_impact_preview,
    render_archive,
    render_logs,
    render_hidden_area,
    render_project,
    render_project_impact_preview,
    render_settings,
    render_task,
    restore_project,
    restore_graph_backup,
    restore_taskfs_backup,
    save_taskfs_file,
    task_impact_preview,
    taskfs_backups,
    rename_project_group,
    restore_project_group,
    set_project_group_hidden,
    update_preferences,
    update_log_record_state,
    update_project_structured,
    update_queue_item,
    update_task_parent,
    update_task_structured,
    _localized_exception_message,
    t,
)
from taskstate_vault.workspaces.registry import init_task_workspace, register_workspace


class TaskStateVaultFlowTests(unittest.TestCase):
    def test_full_complex_project_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = TaskStateVaultPaths(root)

            init_result = init_workspace(root)
            self.assertTrue((root / ".taskstate-vault" / "SYSTEM" / "ENTRYPOINT.md").exists())
            self.assertTrue((root / ".taskstate-vault" / "kernel.sqlite").exists())
            self.assertTrue((root / ".taskstate-vault" / "ACCOUNT" / "PROFILE" / "initial_state.yaml").exists())
            self.assertTrue((root / ".taskstate-vault" / "ACCOUNT" / "PROFILE" / "CODEX_USAGE_GUIDE.md").exists())
            self.assertTrue((root / ".taskstate-vault" / "ACCOUNT" / "GLOBAL_OBJECTS" / "project_refs.jsonl").exists())
            self.assertTrue((root / ".taskstate-vault" / "ACCOUNT" / "GLOBAL_OBJECTS" / "workspace_refs.jsonl").exists())
            self.assertTrue((root / ".taskstate-vault" / "ACCOUNT" / "GLOBAL_OBJECTS" / "vps_configs.jsonl").exists())
            self.assertTrue((root / ".taskstate-vault" / "ACCOUNT" / "ACCOUNT_INDEX" / "account.sqlite").exists())
            self.assertTrue((root / ".taskstate-vault" / "DOMAINS" / "general" / "DOMAIN_INDEX" / "domain.sqlite").exists())
            self.assertIn(".taskstate-vault", init_result["taskfs"])
            self.assertTrue(callable(taskstate_vault_main))

            mode = detect_mode("Build a complex multi-module project with Project Governor, task graph, execution queue, and project state writeback.")
            self.assertEqual(mode.execution_mode, "complex_project")
            self.assertTrue(mode.required_governor)

            project = create_project(
                paths,
                "TaskState Vault Validation Project",
                execution_mode="complex_project",
                project_id="project_validation",
            )
            self.assertEqual(project["project_id"], "project_validation")
            project_root = root / ".taskstate-vault" / "PROJECTS" / "project_validation"
            self.assertTrue((project_root / "PROJECT_INTENT.yaml").exists())
            self.assertTrue((project_root / "PROJECT_MODEL.yaml").exists())
            self.assertTrue((project_root / "GOVERNOR" / "TASK_GRAPH.jsonl").exists())
            self.assertTrue((project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl").exists())
            self.assertGreaterEqual(len(search_account(paths, "Validation")), 1)

            intent = yamlish.read(project_root / "PROJECT_INTENT.yaml")
            self.assertTrue(intent["anti_degradation_rules"])
            queue = read_jsonl(project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
            self.assertGreaterEqual(len(queue), 1)
            self.assertIn("why_now", queue[0])
            self.assertIn("score_breakdown", queue[0])

            next_action = get_next_action(paths, "project_validation")
            self.assertEqual(next_action["rank"], 1)

            task = create_task_from_queue(paths, "project_validation", 1)
            task_id = task["task_id"]
            task_root = project_root / "TASKS" / task_id
            self.assertTrue((task_root / "CURRENT" / "TASK_STATE.yaml").exists())
            self.assertTrue((task_root / "CURRENT" / "NEXT_ACTION.md").exists())

            external_workspace = root / "external_workspace"
            external_workspace.mkdir()
            (external_workspace / "notes.md").write_text("Indexed external workspace signal", encoding="utf-8")
            workspace_ref = register_workspace(paths, external_workspace, "project_validation", task_id, "External source workspace")
            self.assertEqual(workspace_ref["object_type"], "workspace_ref")
            local_task_workspace = init_task_workspace(paths, external_workspace, "project_validation", task_id)
            self.assertTrue((external_workspace / ".taskstate-vault" / "TASK_WORKSPACE.yaml").exists())
            self.assertIn("central_workspace_ref", local_task_workspace)
            indexed_files = index_project_files(paths, "project_validation", external_workspace)
            self.assertGreaterEqual(indexed_files["indexed_files"], 1)
            project_file_hits = layered_search(paths, "external", "project_validation")
            self.assertGreaterEqual(len(project_file_hits["project"]), 1)

            account_obj = add_account_object(
                paths,
                "vps_config",
                "VPS Singapore build host",
                "host=vps-sg.example; user=deploy; purpose=build",
                tags=["vps", "singapore", "build"],
            )
            self.assertEqual(account_obj["layer"], "account")
            account_hits = search_account(paths, "vps")
            self.assertGreaterEqual(len(account_hits), 1)
            imported = import_account_to_task(paths, "project_validation", task_id, "vps", reason="task needs build host")
            self.assertGreaterEqual(len(imported["imported"]), 1)
            layer_imports = read_jsonl(task_root / "OBJECTS" / "layer_imports.jsonl")
            self.assertGreaterEqual(len(layer_imports), 1)
            self.assertEqual(layer_imports[0]["copied_from_layer"], "account")
            layered = layered_search(paths, "vps", "project_validation", task_id)
            self.assertGreaterEqual(len(layered["account"]), 1)
            self.assertGreaterEqual(len(layered["task"]), 1)

            run = start_run(paths, "project_validation", task_id)
            finished = finish_run(paths, "project_validation", task_id, run["run_id"], "success", "Validated run writeback.")
            self.assertEqual(finished["status"], "success")
            artifacts = read_jsonl(task_root / "OBJECTS" / "artifacts.jsonl")
            self.assertEqual(len(artifacts), 1)

            changed = change_objective(
                paths,
                "project_validation",
                task_id,
                "split",
                "First complete the verifiable schema and queue scheduling loop.",
                "Reduce rework risk while preserving project intent.",
            )
            self.assertIn("objective_change", changed)
            objective_log = read_jsonl(project_root / "GOVERNOR" / "OBJECTIVE_CHANGE_LOG.jsonl")
            self.assertEqual(len(objective_log), 1)
            self.assertEqual(objective_log[0]["parent_project_objective"], "project/project_validation")

            context = build_context(paths, project_id="project_validation", task_id=task_id)
            self.assertEqual(context["profile"], "project_governor")
            refs = [item["ref"] for item in context["loaded"]]
            self.assertIn("PROJECT_INTENT.yaml", refs)
            self.assertIn("GOVERNOR/EXECUTION_QUEUE.jsonl", refs)

            promotion = propose_promotion(paths, "project_validation", "task_pattern", "Task graph before single-task execution")
            self.assertEqual(promotion["status"], "candidate")

            completed = complete_task(paths, "project_validation", task_id)
            self.assertEqual(completed["status"], "completed")
            audit = generate_final_audit(paths, "project_validation")
            self.assertTrue(Path(audit["final_audit"]).exists())
            self.assertTrue(Path(audit["initial_guidance"]).exists())

            adapter_context = call_tool(
                "tsv_get_startup_context",
                {"project_id": "project_validation", "task_id": task_id},
                root=str(root),
            )
            self.assertEqual(adapter_context["profile"], "project_governor")
            tool_names = {tool["name"] for tool in list_tool_specs()}
            self.assertIn("tsv_get_startup_context", tool_names)
            self.assertIn("tsv_index_project_files", tool_names)

    def test_public_facades(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault = TaskStateVault(root)
            self.assertIsInstance(vault.taskfs, TaskFS)
            self.assertIsInstance(vault.taskdb, TaskDB)
            self.assertIsInstance(vault.contextkernel, ContextKernel)
            self.assertIn(".taskstate-vault", vault.init()["taskfs"])

            project = vault.contextkernel.create_project(
                "Facade API Project",
                execution_mode="complex_project",
                project_id="project_facade",
            )
            self.assertEqual(project["project_id"], "project_facade")
            task = vault.contextkernel.create_task_from_queue("project_facade")
            account_object = vault.taskdb.add_account_object("tool", "Facade test tool", "name=facade-tool", tags=["facade"])
            self.assertEqual(account_object["layer"], "account")
            imported = vault.taskdb.import_account_to_task("project_facade", task["task_id"], "facade", reason="facade test")
            self.assertGreaterEqual(len(imported["imported"]), 1)
            context = vault.contextkernel.build_context("project_facade", task["task_id"])
            self.assertEqual(context["profile"], "project_governor")

    def test_ui_groups_projects_hides_sensitive_and_shows_task_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = TaskStateVaultPaths(root)
            init_workspace(root)
            create_project(paths, "Visible Operations Console", execution_mode="complex_project", project_id="ops_console")
            create_project(paths, "Sensitive Materials Demo", execution_mode="complex_project", project_id="sensitive_materials_demo")
            create_project(
                paths,
                "Confidential Planning Demo",
                execution_mode="program_scale",
                project_id="confidential_planning_demo",
            )

            task = create_task_from_queue(paths, "ops_console", 1)
            task_id = task["task_id"]
            (root / ".taskstate-vault/PROJECTS/ops_console/TASKS" / task_id / "EVIDENCE" / "user_messages").mkdir(parents=True, exist_ok=True)
            register_workspace(paths, root / "ops_workspace", "ops_console", task_id, "Visible operations workspace")
            register_workspace(paths, root / "sensitive_workspace", "sensitive_materials_demo", None, "Sensitive source workspace")

            update_preferences(
                paths,
                {
                    "hidden_keywords": ["sensitive\nconfidential\nrestricted"],
                    "advanced_editor_enabled": ["1"],
                    "backup_retention": ["5"],
                    "default_landing": ["/"],
                },
            )

            from taskstate_vault.kernel.records import add_artifact, add_evidence, log_error

            add_evidence(paths, "ops_console", task_id, "user_messages", "Request asked for task-local evidence display.")
            add_artifact(paths, "ops_console", task_id, str(root / "artifact.txt"), "UI grouping artifact")
            log_error(paths, "ops_console", task_id, "UI grouping correction log")

            summary = build_summary(paths)
            visible_project_ids = {project["project_id"] for project in summary["visible_projects"]}
            self.assertIn("ops_console", visible_project_ids)
            self.assertNotIn("sensitive_materials_demo", visible_project_ids)
            self.assertTrue(summary["workspace_groups"])
            self.assertTrue(all("sensitive" not in str(item.get("summary", "")).lower() for item in summary["workspaces"]))

            dashboard = render_dashboard(paths)
            self.assertIn("项目地图", dashboard)
            self.assertIn("工作区地图", dashboard)
            self.assertIn("ops_console", dashboard)
            self.assertNotIn("sensitive_materials_demo", dashboard)
            self.assertNotIn("Confidential Planning Demo", dashboard)
            self.assertNotIn("confidential_planning_demo", dashboard)
            filtered_dashboard = render_dashboard(paths, {"q": ["ops_console"], "visibility": ["active"]})
            self.assertIn('name="q"', filtered_dashboard)
            self.assertIn("ops_console", filtered_dashboard)
            self.assertNotIn("sensitive_materials_demo", filtered_dashboard)
            self.assertIn("隐藏区", dashboard)
            self.assertIn("登录", dashboard)

            advanced_ctx = {"lang": "zh", "authenticated": True, "advanced": True, "username": "admin"}
            advanced_dashboard = render_dashboard(paths, advanced_ctx)
            self.assertIn("Confidential Planning Demo", advanced_dashboard)
            self.assertIn("sensitive_materials_demo", advanced_dashboard)
            self.assertIn("/actions/project-group/create", advanced_dashboard)

            create_project_group(paths, "Experimental Group", "Lab", "tester")
            group_dashboard = render_dashboard(paths, advanced_ctx)
            self.assertIn("Experimental Group", group_dashboard)
            rename_project_group(paths, "Other Projects", "General Renamed", "tester")
            renamed_manifest = yamlish.read(root / ".taskstate-vault/PROJECTS/ops_console/PROJECT_MANIFEST.yaml")
            self.assertEqual(renamed_manifest["project_group"], "General Renamed")
            set_project_group_hidden(paths, "General Renamed", True, "tester")
            normal_after_group_hide = build_summary(paths, {"lang": "zh", "authenticated": False, "advanced": False})
            self.assertNotIn("ops_console", {project["project_id"] for project in normal_after_group_hide["visible_projects"]})
            hidden_area = render_dashboard(paths, advanced_ctx)
            self.assertIn("General Renamed", hidden_area)
            hidden_filter_page = render_hidden_area(paths, ctx=advanced_ctx, query={"q": ["sensitive"], "type": ["project"]})
            self.assertIn('action="/hidden-area"', hidden_filter_page)
            self.assertIn("sensitive_materials_demo", hidden_filter_page)
            self.assertNotIn("ops_console", hidden_filter_page)
            hidden_workspace_page = render_hidden_area(paths, ctx=advanced_ctx, query={"q": ["sensitive"], "type": ["workspace"]})
            self.assertIn("隐藏工作区引用", hidden_workspace_page)
            self.assertIn("sensitive_materials_demo", hidden_workspace_page)
            self.assertIn("Sensitive source workspace", hidden_workspace_page)
            set_project_group_hidden(paths, "General Renamed", False, "tester")
            archive_project_group(paths, "General Renamed", "test group archive", "tester")
            archived_group_summary = build_summary(paths, advanced_ctx)
            self.assertNotIn("ops_console", {project["project_id"] for project in archived_group_summary["visible_projects"]})
            archived_workspace_page = render_archive(paths, ctx=advanced_ctx, query={"type": ["workspace"]})
            self.assertIn("归档工作区引用", archived_workspace_page)
            self.assertIn("ops_console", archived_workspace_page)
            archived_group_evidence_page = render_archive(paths, ctx=advanced_ctx, query={"type": ["evidence"], "q": ["Request asked"]})
            self.assertIn("Request asked for task-local evidence display.", archived_group_evidence_page)
            archived_group_artifact_page = render_archive(paths, ctx=advanced_ctx, query={"type": ["artifact"], "q": ["UI grouping artifact"]})
            self.assertIn("UI grouping artifact", archived_group_artifact_page)
            archived_group_log_page = render_archive(paths, ctx=advanced_ctx, query={"type": ["log"], "q": ["UI grouping correction"]})
            self.assertIn("UI grouping correction log", archived_group_log_page)
            restore_project_group(paths, "General Renamed", "tester")
            restored_group_summary = build_summary(paths, advanced_ctx)
            self.assertIn("ops_console", {project["project_id"] for project in restored_group_summary["visible_projects"]})
            created_project_id = create_project_from_ui(
                paths,
                {
                    "title": ["UI Created Project"],
                    "display_title": ["UI Created Display"],
                    "project_id": ["ui_created_project"],
                    "execution_mode": ["complex_project"],
                    "project_group": ["Lifecycle Group"],
                    "workspace": [""],
                },
                "tester",
            )
            self.assertEqual(created_project_id, "ui_created_project")
            created_project_page = render_project(paths, "ui_created_project", ctx=advanced_ctx)
            self.assertIn("/actions/project/archive", created_project_page)
            self.assertIn("/actions/project/permanent-delete", created_project_page)
            self.assertIn("project-permanent-delete", created_project_page)
            archive_project(paths, "ui_created_project", "project lifecycle test", "tester")
            archived_project_summary = build_summary(paths, advanced_ctx)
            self.assertNotIn("ui_created_project", {project["project_id"] for project in archived_project_summary["visible_projects"]})
            archive_page = render_archive(paths, ctx=advanced_ctx)
            self.assertIn("ui_created_project", archive_page)
            self.assertIn("/actions/project/restore", archive_page)
            archive_filter_page = render_archive(paths, ctx=advanced_ctx, query={"q": ["ui_created_project"], "type": ["project"]})
            self.assertIn('action="/archive"', archive_filter_page)
            self.assertIn("ui_created_project", archive_filter_page)
            project_impact = project_impact_preview(paths, "ui_created_project")
            self.assertTrue(project_impact["repair_required"])
            project_impact_page = render_project_impact_preview(paths, "ui_created_project", "project-permanent-delete", advanced_ctx)
            self.assertIn("ui_created_project", project_impact_page)
            self.assertIn("repair references", project_impact_page)
            restore_project(paths, "ui_created_project", "active", "tester")
            restored_project_summary = build_summary(paths, advanced_ctx)
            self.assertIn("ui_created_project", {project["project_id"] for project in restored_project_summary["visible_projects"]})
            archive_project(paths, "ui_created_project", "delete project lifecycle test", "tester")
            with self.assertRaises(ValueError):
                permanent_delete_project(paths, "ui_created_project", "ui_created_project", "", "tester")
            permanent_delete_project(paths, "ui_created_project", "ui_created_project", "repair references", "tester")
            self.assertFalse((root / ".taskstate-vault/PROJECTS/ui_created_project").exists())
            registry_after_project_delete = read_jsonl(root / ".taskstate-vault/project_registry.jsonl")
            self.assertFalse(any(record.get("project_id") == "ui_created_project" for record in registry_after_project_delete))

            create_project(paths, "Restricted Ledger Project", execution_mode="complex_project", project_id="restricted_ops_project")
            update_preferences(
                paths,
                {
                    "hidden_keywords": ["restricted\nconfidential"],
                    "deletion_confirmation_strength": ["strict"],
                    "backup_retention": ["20"],
                    "advanced_editor_enabled": ["1"],
                    "default_landing": ["/"],
                },
            )
            settings_page = render_settings(paths, ctx=advanced_ctx)
            self.assertIn("自动隐藏关键词", settings_page)
            self.assertIn("restricted", settings_page)
            self.assertIn("删除确认强度", settings_page)
            self.assertEqual(t(advanced_ctx, "msg_project_archived"), "项目已归档。")
            self.assertEqual(_localized_exception_message(advanced_ctx, ValueError("Project title is required.")), "项目标题不能为空。")
            self.assertEqual(_localized_exception_message({"lang": "en"}, ValueError("Project title is required.")), "Project title is required.")
            restricted_normal = build_summary(paths, {"lang": "zh", "authenticated": False, "advanced": False})
            self.assertNotIn("restricted_ops_project", {project["project_id"] for project in restricted_normal["visible_projects"]})
            restricted_advanced = build_summary(paths, advanced_ctx)
            self.assertIn("restricted_ops_project", {project["project_id"] for project in restricted_advanced["visible_projects"]})

            orphan_task = "task_orphan_delete"
            orphan_root = root / f".taskstate-vault/PROJECTS/ops_console/TASKS/{orphan_task}/CURRENT"
            orphan_root.mkdir(parents=True, exist_ok=True)
            (orphan_root / "TASK_STATE.yaml").write_text('{"status":"planned","task_objective":{"current":"orphan"}}\n', encoding="utf-8")
            archive_task(paths, "ops_console", orphan_task, "strict delete test", "tester")
            with self.assertRaises(ValueError):
                permanent_delete_task(paths, "ops_console", orphan_task, orphan_task, "", "tester")
            permanent_delete_task(paths, "ops_console", orphan_task, orphan_task, "repair references", "tester")
            self.assertFalse((root / f".taskstate-vault/PROJECTS/ops_console/TASKS/{orphan_task}").exists())

            project_page = render_project(paths, "ops_console")
            self.assertIn("Task DAG", project_page)
            self.assertIn("有向无环图", project_page)
            self.assertIn("data-dag-zoom", project_page)
            self.assertIn("data-dag-fit", project_page)
            self.assertIn("data-dag-status", project_page)
            self.assertIn("data-dag-focus", project_page)
            self.assertIn("data-dag-trace", project_page)
            self.assertIn("任务与本地日志", project_page)
            self.assertIn("evidence", project_page)
            self.assertIn("纠错日志", project_page)
            self.assertIn("多级任务图", project_page)
            self.assertIn("执行队列", project_page)
            self.assertIn("重排队列", project_page)
            self.assertIn("/actions/project/update", project_page)
            self.assertIn("/actions/queue/insert", project_page)
            filtered_project_page = render_project(paths, "ops_console", query={"task_q": [task_id], "queue_status": ["all"]})
            self.assertIn('name="task_q"', filtered_project_page)
            self.assertIn(task_id, filtered_project_page)

            update_project_structured(
                paths,
                "ops_console",
                {"title": ["Ops Console Edited"], "display_title": ["Ops Console Display"], "execution_mode": ["complex_project"], "project_group": ["Core Product"]},
                "tester",
            )
            updated_manifest = yamlish.read(root / ".taskstate-vault/PROJECTS/ops_console/PROJECT_MANIFEST.yaml")
            self.assertEqual(updated_manifest["title"], "Ops Console Edited")
            self.assertEqual(updated_manifest["project_group"], "Core Product")
            update_preferences(
                paths,
                {
                    "show_internal_ids": ["1"],
                    "show_raw_paths": ["1"],
                    "show_archived": ["1"],
                    "advanced_editor_enabled": ["1"],
                    "backup_retention": ["5"],
                    "default_landing": ["/projects"],
                },
            )

            task_page = render_task(paths, "ops_console", task_id)
            self.assertIn("任务操作", task_page)
            self.assertIn("添加记录", task_page)
            self.assertIn("当前状态文件", task_page)
            self.assertIn("开始运行", task_page)
            self.assertIn("结构化编辑", task_page)
            self.assertIn("/actions/task/create-child", task_page)
            self.assertIn("/actions/task/record", task_page)

            update_task_structured(
                paths,
                "ops_console",
                task_id,
                {
                    "title": ["Edited task title"],
                    "objective": ["Edited structured objective"],
                    "status": ["blocked"],
                    "priority": ["0.42"],
                    "parent_id": [""],
                    "acceptance_criteria": ["criterion one\ncriterion two"],
                    "next_action": ["Continue with structured editing verification."],
                },
                "tester",
            )
            updated_state = yamlish.read(root / f".taskstate-vault/PROJECTS/ops_console/TASKS/{task_id}/CURRENT/TASK_STATE.yaml")
            self.assertEqual(updated_state["status"], "blocked")
            self.assertEqual(updated_state["task_objective"]["current"], "Edited structured objective")
            self.assertEqual(updated_state["acceptance_criteria"], ["criterion one", "criterion two"])

            child_id = create_child_task(
                paths,
                "ops_console",
                task_id,
                {
                    "child_id": ["task_ui_child"],
                    "child_title": ["UI child task"],
                    "child_objective": ["Verify child creation"],
                    "child_acceptance_criteria": ["child criterion"],
                    "child_next_action": ["Open child task."],
                },
                "tester",
            )
            self.assertEqual(child_id, "task_ui_child")
            self.assertTrue((root / ".taskstate-vault/PROJECTS/ops_console/TASKS/task_ui_child/CURRENT/TASK_STATE.yaml").exists())
            add_task_record(paths, "ops_console", task_id, "decision", "Keep structured editing primary", "Raw editing is fallback only.", "tester")
            decisions = read_jsonl(root / f".taskstate-vault/PROJECTS/ops_console/TASKS/{task_id}/OBJECTS/decisions.jsonl")
            self.assertTrue(any(record.get("summary") == "Keep structured editing primary" for record in decisions))
            add_task_record(paths, "ops_console", task_id, "correction", "Reusable correction", "Promote this correction.", "tester")
            correction_records = collect_log_records(paths, advanced_ctx, {"type": "correction", "q": "Reusable correction"})
            self.assertTrue(correction_records)
            correction_id = correction_records[0]["record_id"]
            logs_page = render_logs(paths, {"type": ["correction"], "q": ["Reusable correction"]}, ctx=advanced_ctx)
            self.assertIn("/actions/log/update", logs_page)
            self.assertIn("/actions/log/promote", logs_page)
            update_log_record_state(paths, correction_id, "handled", "tester")
            handled_records = collect_log_records(paths, advanced_ctx, {"status": "handled", "q": "Reusable correction"})
            self.assertTrue(any(record["record_id"] == correction_id for record in handled_records))
            update_log_record_state(paths, correction_id, "hide", "tester")
            normal_records = collect_log_records(paths, {"lang": "zh", "authenticated": False, "advanced": False}, {"q": "Reusable correction"})
            self.assertFalse(any(record["record_id"] == correction_id for record in normal_records))
            update_log_record_state(paths, correction_id, "archive", "tester")
            archived_records = collect_log_records(paths, advanced_ctx, {"status": "archived", "q": "Reusable correction"})
            self.assertTrue(any(record["record_id"] == correction_id for record in archived_records))
            update_log_record_state(paths, correction_id, "restore", "tester")
            promote_log = promote_log_record(paths, correction_id, "tester")
            self.assertEqual(promote_log["object_type"], "correction")

            insert_queue_item(
                paths,
                "ops_console",
                "task_ui_child",
                "1",
                "Manual queue insert from test.",
                "tester",
                "queue-output.md\nreport.json",
                "PROJECT_PROGRESS.yaml",
            )
            inserted_queue = read_jsonl(root / ".taskstate-vault/PROJECTS/ops_console/GOVERNOR/EXECUTION_QUEUE.jsonl")
            inserted_item = next(item for item in inserted_queue if item.get("task_id") == "task_ui_child" and "queue-output.md" in item.get("expected_outputs", []))
            self.assertIn("queue-output.md", inserted_item["expected_outputs"])
            self.assertIn("PROJECT_PROGRESS.yaml", inserted_item["required_context_refs"])
            update_queue_item(paths, "ops_console", inserted_item.get("queue_id", ""), "task_ui_child", "pause", "tester")
            paused_queue = read_jsonl(root / ".taskstate-vault/PROJECTS/ops_console/GOVERNOR/EXECUTION_QUEUE.jsonl")
            self.assertEqual(next(item for item in paused_queue if item.get("task_id") == "task_ui_child")["status"], "paused")
            queue_explain_page = render_project(paths, "ops_console", ctx=advanced_ctx, query={"queue_q": ["task_ui_child"], "queue_status": ["all"]})
            self.assertIn("依赖就绪", queue_explain_page)
            self.assertIn("预期产物", queue_explain_page)
            self.assertIn("queue-output.md", queue_explain_page)
            self.assertIn("评分明细", queue_explain_page)
            self.assertIn("队列历史", queue_explain_page)
            self.assertIn("queue_update", queue_explain_page)

            impact = task_impact_preview(paths, "ops_console", task_id)
            self.assertTrue(impact["incoming_edges"] or impact["outgoing_edges"] or impact["queue_items"])
            impact_page = render_impact_preview(paths, "ops_console", task_id, "permanent-delete", advanced_ctx)
            self.assertIn("影响预览", impact_page)
            self.assertIn("repair references", impact_page)

            with self.assertRaises(ValueError):
                update_task_parent(paths, "ops_console", "task_project_governor_core", "task_project_governor_core", "tester")
            with self.assertRaises(ValueError):
                add_dependency(paths, "ops_console", "task_freeze_intent_and_schema", "task_project_governor_core", "tester")
            add_dependency(paths, "ops_console", "task_final_audit_and_guidance", "task_project_governor_core", "tester")
            backups_after_graph_edit = graph_backups(paths, "ops_console")
            self.assertTrue(backups_after_graph_edit)
            graph_with_added_dependency = read_jsonl(root / ".taskstate-vault/PROJECTS/ops_console/GOVERNOR/TASK_GRAPH.jsonl")
            self.assertTrue(
                any(
                    record.get("record_type") == "edge"
                    and record.get("src") == "task_final_audit_and_guidance"
                    and record.get("dst") == "task_project_governor_core"
                    for record in graph_with_added_dependency
                )
            )
            restore_graph_backup(paths, "ops_console", backups_after_graph_edit[0].resolve().relative_to(root.resolve()).as_posix())
            restored_graph = read_jsonl(root / ".taskstate-vault/PROJECTS/ops_console/GOVERNOR/TASK_GRAPH.jsonl")
            self.assertFalse(
                any(
                    record.get("record_type") == "edge"
                    and record.get("src") == "task_final_audit_and_guidance"
                    and record.get("dst") == "task_project_governor_core"
                    for record in restored_graph
                )
            )

            state_rel = f".taskstate-vault/PROJECTS/ops_console/TASKS/{task_id}/CURRENT/TASK_STATE.yaml"
            editor = render_editor(paths, state_rel, ctx=advanced_ctx)
            self.assertIn("高级文件编辑", editor)
            self.assertIn("/actions/file/save", editor)
            state_path = root / state_rel
            original_state = state_path.read_text(encoding="utf-8")
            diff_preview = render_file_diff_preview(paths, state_rel, original_state.replace("blocked", "active"), advanced_ctx)
            self.assertIn("@@", diff_preview)
            self.assertIn("/actions/file/save", diff_preview)
            self.assertIn('name="confirm" value="1"', diff_preview)
            save_taskfs_file(paths, state_rel, original_state.replace('"status": "active"', '"status": "active"'))
            save_taskfs_file(paths, state_rel, original_state.replace('"status": "blocked"', '"status": "blocked"'))
            backups = list((root / ".taskstate-vault" / "UI_BACKUPS").rglob("TASK_STATE.yaml"))
            self.assertGreaterEqual(len(backups), 1)
            self.assertTrue(taskfs_backups(paths, state_rel))
            restored_rel = restore_taskfs_backup(paths, backups[0].resolve().relative_to(root.resolve()).as_posix())
            self.assertEqual(restored_rel, state_rel)
            update_preferences(paths, {"backup_retention": ["1"], "advanced_editor_enabled": ["1"]})
            cleanup_taskfs_backups(paths, state_rel)
            self.assertLessEqual(len(taskfs_backups(paths, state_rel, 20)), 1)
            with self.assertRaises(ValueError):
                save_taskfs_file(paths, "../outside.txt", "nope")

            archive_task(paths, "ops_console", task_id, "test archive", "tester")
            with self.assertRaises(ValueError):
                permanent_delete_task(paths, "ops_console", task_id, task_id, "", "tester")
            permanent_delete_task(paths, "ops_console", task_id, task_id, "repair references", "tester")
            self.assertFalse((root / f".taskstate-vault/PROJECTS/ops_console/TASKS/{task_id}").exists())


if __name__ == "__main__":
    unittest.main()
