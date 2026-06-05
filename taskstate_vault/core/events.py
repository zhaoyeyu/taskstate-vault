from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl
from taskstate_vault.core.timeutil import now_iso


def event_hash(event: dict[str, Any]) -> str:
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def append_event(path: Path, event_type: str, namespace: str, summary: str, **payload: Any) -> dict[str, Any]:
    event = {
        "schema_version": 1,
        "event_id": make_id("evt", event_type),
        "event_type": event_type,
        "namespace": namespace,
        "scope": payload.pop("scope", "project"),
        "actor": payload.pop("actor", "codex"),
        "time": now_iso(),
        "object_refs": payload.pop("object_refs", []),
        "input_refs": payload.pop("input_refs", []),
        "output_refs": payload.pop("output_refs", []),
        "summary": summary,
        "payload": payload,
    }
    event["event_hash"] = event_hash(event)
    append_jsonl(path, event)
    return event

