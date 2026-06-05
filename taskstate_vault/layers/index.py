from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from taskstate_vault.core.db import (
    record_import_copy,
    search_layer_index,
    upsert_index_entry,
)
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import append_jsonl, read_jsonl
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.kernel.records import add_object
from taskstate_vault.layers.files import account_objects_path, domain_objects_path, ensure_account_layout, ensure_domain_layout


def make_pointer_uri(layer: str, object_id: str) -> str:
    return f"tsv://{layer}/{object_id}"


def add_account_object(
    paths: TaskStateVaultPaths,
    object_type: str,
    summary: str,
    content: str = "",
    tags: list[str] | None = None,
    ttl: str = "account",
) -> dict[str, Any]:
    ensure_account_layout(paths)
    created = now_iso()
    object_id = make_id("acct_obj", object_type)
    storage_path = account_objects_path(paths, object_type)
    record = {
        "schema_version": 1,
        "object_id": object_id,
        "entry_id": make_id("idx", object_id),
        "scope": "account/default",
        "layer": "account",
        "object_type": object_type,
        "status": "active",
        "arena": "account",
        "ttl": ttl,
        "summary": summary,
        "content": content or summary,
        "storage_path": str(storage_path.relative_to(paths.os_dir)),
        "pointer_uri": make_pointer_uri("account", object_id),
        "tags": tags or [],
        "source_refs": [],
        "created_at": created,
        "updated_at": created,
    }
    append_jsonl(storage_path, record)
    _upsert_entry(paths.account_index_db, record)
    return record


def add_domain_object(
    paths: TaskStateVaultPaths,
    domain_id: str,
    object_type: str,
    summary: str,
    content: str = "",
    tags: list[str] | None = None,
    ttl: str = "domain",
) -> dict[str, Any]:
    ensure_domain_layout(paths, domain_id)
    created = now_iso()
    object_id = make_id("dom_obj", object_type)
    storage_path = domain_objects_path(paths, domain_id, object_type)
    record = {
        "schema_version": 1,
        "object_id": object_id,
        "entry_id": make_id("idx", object_id),
        "scope": f"domain/{domain_id}",
        "layer": "domain",
        "domain_id": domain_id,
        "object_type": object_type,
        "status": "active",
        "arena": "domain",
        "ttl": ttl,
        "summary": summary,
        "content": content or summary,
        "storage_path": str(storage_path.relative_to(paths.os_dir)),
        "pointer_uri": make_pointer_uri(f"domain/{domain_id}", object_id),
        "tags": tags or [],
        "source_refs": [],
        "created_at": created,
        "updated_at": created,
    }
    append_jsonl(storage_path, record)
    _upsert_entry(paths.domain_index_db(domain_id), record)
    return record


def search_account(paths: TaskStateVaultPaths, query: str, limit: int = 10) -> list[dict[str, Any]]:
    ensure_account_layout(paths)
    return search_layer_index(paths.account_index_db, query, limit)


def search_domain(paths: TaskStateVaultPaths, domain_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    ensure_domain_layout(paths, domain_id)
    return search_layer_index(paths.domain_index_db(domain_id), query, limit)


def layered_search(paths: TaskStateVaultPaths, query: str, project_id: str | None = None, task_id: str | None = None, domain_id: str = "general", limit: int = 10) -> dict[str, Any]:
    results = {
        "query": query,
        "task": [],
        "project": [],
        "domain": search_domain(paths, domain_id, query, limit),
        "account": search_account(paths, query, limit),
    }
    if project_id:
        from taskstate_vault.governor.files import project_db

        results["project"] = search_layer_index(project_db(paths, project_id), query, limit)
    if project_id and task_id:
        results["task"] = search_layer_index(paths.task_dir(project_id, task_id) / "INDEX" / "task.sqlite", query, limit)
    return results


def import_index_entry_to_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, entry: dict[str, Any], reason: str = "") -> dict[str, Any]:
    object_type = entry.get("object_type", "resource")
    task_type = _task_object_type(object_type)
    copied = add_object(
        paths,
        project_id,
        task_id,
        task_type,
        entry.get("summary", ""),
        source_ref=entry.get("pointer_uri"),
    )
    copied.update(
        {
            "copied_from_entry_id": entry.get("entry_id"),
            "copied_from_layer": entry.get("layer"),
            "copied_from_pointer_uri": entry.get("pointer_uri"),
            "copy_reason": reason or "layered index import",
        }
    )
    task_root = paths.task_dir(project_id, task_id)
    append_jsonl(task_root / "OBJECTS" / "layer_imports.jsonl", copied)
    record_import_copy(
        _index_db_for_layer(paths, entry.get("layer", "account"), entry.get("scope", "")),
        {
            "copy_id": make_id("copy", task_id),
            "source_entry_id": entry.get("entry_id"),
            "source_pointer_uri": entry.get("pointer_uri"),
            "target_scope": f"project/{project_id}/task/{task_id}",
            "target_path": str((task_root / "OBJECTS" / "layer_imports.jsonl").relative_to(paths.os_dir)),
            "copied_at": now_iso(),
        },
    )
    return copied


def import_account_to_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, query: str, limit: int = 3, reason: str = "") -> dict[str, Any]:
    entries = search_account(paths, query, limit)
    copies = [import_index_entry_to_task(paths, project_id, task_id, entry, reason or f"account search: {query}") for entry in entries]
    return {"query": query, "imported": copies}


def import_domain_to_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, domain_id: str, query: str, limit: int = 3, reason: str = "") -> dict[str, Any]:
    entries = search_domain(paths, domain_id, query, limit)
    copies = [import_index_entry_to_task(paths, project_id, task_id, entry, reason or f"domain search: {query}") for entry in entries]
    return {"query": query, "domain_id": domain_id, "imported": copies}


def _upsert_entry(index_db: Path, record: dict[str, Any]) -> None:
    upsert_index_entry(
        index_db,
        {
            "entry_id": record["entry_id"],
            "object_id": record["object_id"],
            "scope": record["scope"],
            "layer": record["layer"],
            "object_type": record["object_type"],
            "status": record["status"],
            "arena": record["arena"],
            "ttl": record["ttl"],
            "summary": record["summary"],
            "content": record["content"],
            "storage_path": record["storage_path"],
            "pointer_uri": record["pointer_uri"],
            "tags_json": json.dumps(record.get("tags", []), ensure_ascii=False),
            "source_refs_json": json.dumps(record.get("source_refs", []), ensure_ascii=False),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        },
    )


def _task_object_type(object_type: str) -> str:
    if object_type in {"vps_config", "local_machine", "email_account", "service_account", "tool", "template"}:
        return "resource"
    if object_type in {"preference", "constraint"}:
        return "constraint"
    if object_type in {"known_error"}:
        return "error"
    return "fact"


def _index_db_for_layer(paths: TaskStateVaultPaths, layer: str, scope: str) -> Path:
    if layer == "account":
        return paths.account_index_db
    if layer == "domain":
        domain_id = scope.split("/", 1)[1] if "/" in scope else "general"
        return paths.domain_index_db(domain_id)
    raise ValueError(f"Unsupported import source layer: {layer}")
