from __future__ import annotations

import re
import uuid


def slugify(value: str, fallback: str = "item") -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or fallback


def make_id(prefix: str, hint: str | None = None) -> str:
    if hint:
        slug = slugify(hint, fallback=prefix)
        return f"{prefix}_{slug[:48]}_{uuid.uuid4().hex[:8]}"
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

