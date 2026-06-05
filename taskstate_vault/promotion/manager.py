from __future__ import annotations

from typing import Any

from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_dir


def propose_promotion(paths, project_id: str, kind: str, summary: str, scope: str = "project") -> dict[str, Any]:
    candidate = {
        "schema_version": 1,
        "promotion_id": make_id("promotion", kind),
        "project_id": project_id,
        "kind": kind,
        "summary": summary,
        "target_scope": scope,
        "status": "candidate",
        "evidence_refs": [],
        "applicability": "Reusable when a future task has similar project-governor or memory-kernel needs.",
        "created_at": now_iso(),
    }
    append_jsonl(project_dir(paths, project_id) / "PROJECT_OBJECTS" / "promotion_candidates.jsonl", candidate)
    return candidate

