from __future__ import annotations

from taskstate_vault.core.timeutil import now_iso


DEFAULT_WORKSTREAMS = [
    {
        "id": "ws_governor",
        "name": "Project Governor",
        "objective": "把复杂项目输入转为项目意图、项目模型、任务图、执行队列和项目回写闭环",
        "modules": ["mod_intent", "mod_task_graph", "mod_execution_queue", "mod_progress"],
    },
    {
        "id": "ws_memory_kernel",
        "name": "ContextKernel",
        "objective": "维护任务态对象、事件、证据、错误、产物和可恢复上下文",
        "modules": ["mod_task_state", "mod_events", "mod_run_records", "mod_artifacts"],
    },
    {
        "id": "ws_context",
        "name": "Context Loader",
        "objective": "按执行模式构造最小但充分的启动上下文，并记录 why-loaded",
        "modules": ["mod_context_profiles", "mod_context_ledger"],
    },
]


def build_project_model(project_id: str, title: str, input_text: str) -> dict:
    timestamp = now_iso()
    return {
        "schema_version": 1,
        "project_id": project_id,
        "updated_at": timestamp,
        "domains": [
            {
                "id": "domain_agent_infra",
                "name": "Agent Infrastructure",
                "description": "本地 agent 任务态、项目治理、长期上下文和经验晋升基础设施",
            }
        ],
        "workstreams": DEFAULT_WORKSTREAMS,
        "modules": [
            {
                "id": "mod_intent",
                "name": "Project Intent Manager",
                "responsibilities": ["维护稳定项目意图", "防止复杂目标降级"],
                "expected_artifacts": ["PROJECT_INTENT.yaml"],
                "quality_bars": ["包含 success_criteria、non_goals、anti_degradation_rules"],
            },
            {
                "id": "mod_task_graph",
                "name": "Task Graph Manager",
                "responsibilities": ["维护 epic/module/task/run 节点", "维护依赖、阻塞、解锁关系"],
                "expected_artifacts": ["TASK_GRAPH.jsonl"],
                "quality_bars": ["任务节点必须包含验收标准、依赖和可验证产物"],
            },
            {
                "id": "mod_execution_queue",
                "name": "Execution Queue Scheduler",
                "responsibilities": ["按项目收益和可执行性排序", "记录 why_now 和 score_breakdown"],
                "expected_artifacts": ["EXECUTION_QUEUE.jsonl"],
                "quality_bars": ["任务选择不能只按用户输入顺序"],
            },
            {
                "id": "mod_task_state",
                "name": "ContextKernel Task State",
                "responsibilities": ["维护 TASK_STATE、NEXT_ACTION、event log、evidence、artifact、error"],
                "expected_artifacts": ["TASK_STATE.yaml", "NEXT_ACTION.md"],
                "quality_bars": ["错误不能进入 facts；run 后必须回写状态"],
            },
        ],
        "core_entities": [
            "ProjectIntent",
            "ProjectModel",
            "TaskNode",
            "TaskEdge",
            "ExecutionQueueItem",
            "Blocker",
            "ObjectiveChange",
            "TaskState",
            "RunRecord",
            "PromotionCandidate",
        ],
        "flows": [
            {
                "id": "flow_complex_project_start",
                "name": "复杂项目启动",
                "steps": ["create_project_intent", "build_project_model", "build_task_graph", "schedule_execution_queue"],
            },
            {
                "id": "flow_run_writeback",
                "name": "复杂项目执行回写",
                "steps": ["record_run", "update_task_graph", "update_project_progress", "reschedule_execution_queue"],
            },
        ],
        "source_input_excerpt": input_text[:2000],
        "open_questions": [],
        "assumptions": [],
    }
