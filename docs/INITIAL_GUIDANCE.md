# TaskState Vault Initial Guidance

TaskState Vault routes work by execution mode:

- `simple_task`: short work that does not need persistent project governance.
- `managed_task`: work that needs continuing state, evidence, errors, or artifacts.
- `complex_project`: multi-stage work managed through project intent, a task graph, an execution queue, and progress records.
- `program_scale`: coordinated work spanning multiple projects or workstreams.

For a complex project, inspect these files before selecting work:

```text
PROJECT_INTENT.yaml
PROJECT_MODEL.yaml
PROJECT_PROGRESS.yaml
GOVERNOR/TASK_GRAPH.jsonl
GOVERNOR/EXECUTION_QUEUE.jsonl
GOVERNOR/BLOCKERS.jsonl
GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl
TASK_STATE.yaml
NEXT_ACTION.md
```

Use the execution queue to select the next ready task, record results and errors during the run, then update task state, project progress, and the next action.
