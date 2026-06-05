from __future__ import annotations


CONTEXT_PROFILES: dict[str, list[str]] = {
    "minimal": ["current_user_request", "local_files_needed"],
    "task_state": ["TASK_MANIFEST.yaml", "CURRENT/TASK_STATE.yaml", "CURRENT/NEXT_ACTION.md"],
    "project_governor": [
        "PROJECT_INTENT.yaml",
        "PROJECT_MODEL.yaml",
        "PROJECT_PROGRESS.yaml",
        "GOVERNOR/EXECUTION_QUEUE.jsonl",
        "GOVERNOR/TASK_GRAPH.jsonl",
        "GOVERNOR/BLOCKERS.jsonl",
        "GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl",
        "current TASK_STATE",
        "current NEXT_ACTION",
    ],
    "program_governor": ["portfolio state", "program roadmap", "project governor summaries"],
}


MODE_TO_PROFILE = {
    "simple_task": "minimal",
    "managed_task": "task_state",
    "complex_project": "project_governor",
    "program_scale": "program_governor",
}

