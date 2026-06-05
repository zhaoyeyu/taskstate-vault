from __future__ import annotations

from dataclasses import dataclass

from taskstate_vault.core.schema import EXECUTION_MODES


@dataclass
class ModeDecision:
    execution_mode: str
    reason: str
    required_governor: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_mode": self.execution_mode,
            "reason": self.reason,
            "required_governor": self.required_governor,
        }


COMPLEX_SIGNALS = {
    "复杂项目",
    "完整项目",
    "大型项目",
    "长期",
    "多模块",
    "任务图",
    "执行队列",
    "Project Governor",
    "项目经理",
    "技术总监",
    "主导",
    "架构",
    "系统",
    "验收",
    "阶段",
    "里程碑",
}

PROGRAM_SIGNALS = {"多个项目", "千人", "组织", "portfolio", "program", "路线图", "跨项目"}

MANAGED_SIGNALS = {"继续", "下次", "记录", "状态", "多轮", "恢复", "归档"}


def detect_mode(text: str) -> ModeDecision:
    normalized = text or ""
    if any(signal.lower() in normalized.lower() for signal in PROGRAM_SIGNALS):
        return ModeDecision("program_scale", "输入包含多项目或组织级治理信号", True)
    if any(signal.lower() in normalized.lower() for signal in COMPLEX_SIGNALS):
        return ModeDecision("complex_project", "输入包含复杂项目、任务图、系统或长期治理信号", True)
    if any(signal.lower() in normalized.lower() for signal in MANAGED_SIGNALS):
        return ModeDecision("managed_task", "输入需要连续任务状态但未达到项目治理规模", False)
    return ModeDecision("simple_task", "输入是短小明确任务，保持轻量流程", False)


def normalize_mode(mode: str) -> str:
    if mode not in EXECUTION_MODES:
        raise ValueError(f"Unknown execution mode: {mode}")
    return mode

