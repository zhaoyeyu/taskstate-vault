from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from taskstate_vault.core.db import upsert_index_entry
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import project_db


SKIP_DIRS = {".taskstate-vault", ".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", ".mypy_cache"}
TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def index_project_files(paths: TaskStateVaultPaths, project_id: str, scan_path: str | Path) -> dict[str, Any]:
    root = Path(scan_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Project file scan path does not exist: {root}")
    files = [root] if root.is_file() else _iter_files(root)
    indexed = 0
    skipped = 0
    for file_path in files:
        if not file_path.is_file():
            continue
        if _is_skipped(file_path, root):
            skipped += 1
            continue
        record = _file_record(paths, project_id, root, file_path)
        upsert_index_entry(project_db(paths, project_id), record)
        indexed += 1
    return {
        "project_id": project_id,
        "scan_path": str(root),
        "indexed_files": indexed,
        "skipped_files": skipped,
        "index_db": str(project_db(paths, project_id)),
    }


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir() and path.name in SKIP_DIRS:
            continue
        if path.is_file():
            files.append(path)
    return files


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        rel_parts = path.parts
    return any(part in SKIP_DIRS for part in rel_parts)


def _file_record(paths: TaskStateVaultPaths, project_id: str, root: Path, file_path: Path) -> dict[str, Any]:
    stat = file_path.stat()
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        rel = file_path.name
    digest = hashlib.sha1(str(file_path).encode("utf-8")).hexdigest()
    timestamp = now_iso()
    content_preview = _content_preview(file_path)
    summary = f"Project file {rel}"
    metadata = {
        "relative_path": str(rel),
        "absolute_path": str(file_path),
        "scan_root": str(root),
        "size_bytes": stat.st_size,
        "modified_time": stat.st_mtime,
    }
    return {
        "entry_id": f"idx_project_file_{digest}",
        "object_id": f"project_file_{digest}",
        "scope": f"project/{project_id}",
        "layer": "project",
        "object_type": "project_file",
        "status": "active",
        "arena": "project",
        "ttl": "project",
        "summary": summary,
        "content": f"{summary}\n{json.dumps(metadata, ensure_ascii=False, sort_keys=True)}\n{content_preview}",
        "storage_path": str(file_path),
        "pointer_uri": f"tsv://project/{project_id}/file/{digest}",
        "tags_json": json.dumps(["project_file", file_path.suffix.lower().lstrip(".")], ensure_ascii=False),
        "source_refs_json": json.dumps([str(file_path)], ensure_ascii=False),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _content_preview(file_path: Path, limit: int = 4000) -> str:
    if file_path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    if file_path.stat().st_size > 1_000_000:
        return ""
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore").lstrip("\ufeff")[:limit]
    except OSError:
        return ""
