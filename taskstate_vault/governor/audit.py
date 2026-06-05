from __future__ import annotations

from taskstate_vault.core import yamlish
from taskstate_vault.core.io import read_jsonl, write_text
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_dir
from taskstate_vault.governor.graph import nodes, read_graph
from taskstate_vault.governor.progress import project_progress


def generate_final_audit(paths, project_id: str) -> dict:
    root = project_dir(paths, project_id)
    intent = yamlish.read(root / "PROJECT_INTENT.yaml", default={})
    progress = project_progress(paths, project_id)
    graph = read_graph(paths, project_id)
    task_nodes = [node for node in nodes(graph) if node.get("node_type") == "task"]
    completed = [node for node in task_nodes if node.get("status") == "completed"]
    artifacts = read_jsonl(root / "PROJECT_OBJECTS" / "artifacts.jsonl")
    promotions = read_jsonl(root / "PROJECT_OBJECTS" / "promotion_candidates.jsonl")
    audit = f"""# FINAL_AUDIT

Generated: {now_iso()}

## Project

- Project ID: `{project_id}`
- Title: {intent.get('title', project_id)}
- Status: {progress.get('overall_status', 'unknown')}

## Intent

{intent.get('mission', {}).get('long_form', intent.get('mission', {}).get('summary', ''))}

## Completion

- Completed task nodes: {len(completed)} / {len(task_nodes)}
- Progress score: {progress.get('health', {}).get('progress_score', 0)}

## Deliverables

{_bullet([item.get('path') or item.get('summary') or item.get('artifact_id') for item in artifacts])}

## Promotion Candidates

{_bullet([item.get('summary') for item in promotions])}

## Remaining Next Best Actions

{_bullet([f"{item.get('task_id')}: {item.get('reason')}" for item in progress.get('next_best_actions', [])])}

## Initial Guidance

Use TaskState Vault `SYSTEM/ENTRYPOINT.md` first. For complex projects, load Project Governor files before implementation, select work from `EXECUTION_QUEUE.jsonl`, and write back TaskFS records and TaskDB indexes after each run.
"""
    write_text(root / "FINAL_AUDIT.md", audit)
    write_text(
        root / "INITIAL_GUIDANCE.md",
        "# INITIAL_GUIDANCE\n\nStart with TaskState Vault `SYSTEM/ENTRYPOINT.md`. For complex projects, read `PROJECT_INTENT.yaml`, `PROJECT_PROGRESS.yaml`, `GOVERNOR/TASK_GRAPH.jsonl`, and `GOVERNOR/EXECUTION_QUEUE.jsonl` before choosing work. After work, update TaskFS records and TaskDB indexes.\n",
    )
    return {"project_id": project_id, "final_audit": str(root / "FINAL_AUDIT.md"), "initial_guidance": str(root / "INITIAL_GUIDANCE.md")}


def _bullet(values: list[str | None]) -> str:
    concrete = [value for value in values if value]
    if not concrete:
        return "- None recorded"
    return "\n".join(f"- {value}" for value in concrete)
