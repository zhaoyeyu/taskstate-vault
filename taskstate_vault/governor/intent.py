from __future__ import annotations

from taskstate_vault.core.timeutil import now_iso


def build_project_intent(project_id: str, title: str, input_text: str, execution_mode: str) -> dict:
    mission = input_text.strip() or title
    timestamp = now_iso()
    return {
        "schema_version": 1,
        "project_id": project_id,
        "title": title,
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "execution_mode": execution_mode,
        "mission": {
            "summary": title,
            "long_form": mission,
        },
        "success_criteria": [
            {
                "id": "sc_project_governor",
                "text": "复杂项目必须通过 Project Governor 形成任务图和执行队列",
                "verification": "存在 PROJECT_INTENT / PROJECT_MODEL / TASK_GRAPH / EXECUTION_QUEUE，并在 run 后回写 PROJECT_PROGRESS",
            },
            {
                "id": "sc_task_graph_first",
                "text": "复杂项目任务选择基于任务图和执行队列，而不是用户输入顺序",
                "verification": "EXECUTION_QUEUE 中每个 ready 项包含 why_now 和 score_breakdown",
            },
            {
                "id": "sc_objective_change_recorded",
                "text": "Codex 自主改写局部任务目标时必须记录 OBJECTIVE_CHANGE_LOG",
                "verification": "目标变化有 old/new objective、reason、parent_project_objective",
            },
        ],
        "non_goals": [
            {
                "id": "ng_no_codex_security_shell",
                "text": "不重新实现 Codex 原生 sandbox、approval、命令权限、网络权限或项目外文件保护",
            }
        ],
        "anti_degradation_rules": [
            {
                "id": "ad_no_toy_mvp",
                "text": "不得将完整系统降级为只会记录任务日志或 NEXT_ACTION 的玩具",
            },
            {
                "id": "ad_no_one_shot_complex_project",
                "text": "不得把复杂项目压缩为一次性粗糙实现",
            },
        ],
        "stable_constraints": [
            {
                "id": "c_project_intent_stable",
                "text": "PROJECT_INTENT 是稳定项目意图，不能被局部任务静默改写",
            }
        ],
    }

