from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
