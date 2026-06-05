from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ExecutionMode = Literal["simple_task", "managed_task", "complex_project", "program_scale"]
NodeType = Literal["project", "workstream", "epic", "module", "task", "run"]
NodeStatus = Literal["draft", "planned", "ready", "active", "blocked", "completed", "split", "superseded", "archived"]


EXECUTION_MODES: set[str] = {"simple_task", "managed_task", "complex_project", "program_scale"}


@dataclass
class TaskNode:
    node_id: str
    node_type: str
    title: str
    objective: str
    parent_id: str | None = None
    status: str = "planned"
    acceptance_criteria: list[str] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    priority: float = 0.5
    project_impact: float = 0.5
    implementation_confidence: float = 0.5
    verification_clarity: float = 0.5
    rework_risk: float = 0.2
    parallelizable: bool = False
    unlocks: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_record(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["record_type"] = "node"
        data["schema_version"] = 1
        return data


@dataclass
class TaskEdge:
    edge_id: str
    src: str
    dst: str
    relation: str
    strength: float = 1.0
    reason: str = ""
    created_at: str = ""

    def to_record(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["record_type"] = "edge"
        data["schema_version"] = 1
        return data


@dataclass
class QueueItem:
    queue_id: str
    task_id: str
    rank: int
    status: str
    why_now: str
    score: float
    score_breakdown: dict[str, float]
    required_context_refs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_record(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["schema_version"] = 1
        return data

