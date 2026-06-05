from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps(data: Any) -> str:
    """Return JSON-compatible YAML.

    JSON is valid YAML 1.2 and keeps this project dependency-free while still
    producing deterministic, human-readable state files.
    """
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def loads(text: str) -> Any:
    if not text.strip():
        return {}
    return json.loads(text)


def write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(data), encoding="utf-8")


def read(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return loads(path.read_text(encoding="utf-8"))

