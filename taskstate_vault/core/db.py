from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def managed_connection(path: Path):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_kernel_db(path: Path) -> None:
    with managed_connection(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
              project_id TEXT PRIMARY KEY,
              portfolio_id TEXT,
              program_id TEXT,
              domain_id TEXT,
              status TEXT NOT NULL,
              title TEXT NOT NULL,
              path TEXT NOT NULL,
              execution_mode TEXT,
              current_task_id TEXT,
              created_at TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              parent_node_id TEXT,
              status TEXT NOT NULL,
              title TEXT NOT NULL,
              path TEXT NOT NULL,
              queue_rank INTEGER,
              created_at TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              project_id TEXT,
              task_id TEXT,
              status TEXT,
              started_at TEXT,
              ended_at TEXT,
              path TEXT
            );

            CREATE TABLE IF NOT EXISTS scopes (
              scope_id TEXT PRIMARY KEY,
              scope_type TEXT NOT NULL,
              parent_scope_id TEXT,
              path TEXT,
              status TEXT
            );
            """
        )


def init_project_db(path: Path) -> None:
    with managed_connection(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS task_nodes (
              node_id TEXT PRIMARY KEY,
              node_type TEXT NOT NULL,
              parent_id TEXT,
              title TEXT NOT NULL,
              objective TEXT,
              status TEXT NOT NULL,
              priority REAL DEFAULT 0,
              project_impact REAL DEFAULT 0,
              implementation_confidence REAL DEFAULT 0,
              verification_clarity REAL DEFAULT 0,
              rework_risk REAL DEFAULT 0,
              parallelizable INTEGER DEFAULT 0,
              created_at TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS task_edges (
              edge_id TEXT PRIMARY KEY,
              src TEXT NOT NULL,
              dst TEXT NOT NULL,
              relation TEXT NOT NULL,
              strength REAL DEFAULT 1,
              reason TEXT
            );

            CREATE TABLE IF NOT EXISTS execution_queue (
              queue_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              rank INTEGER NOT NULL,
              status TEXT NOT NULL,
              score REAL DEFAULT 0,
              why_now TEXT,
              score_breakdown_json TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS blockers (
              blocker_id TEXT PRIMARY KEY,
              scope TEXT,
              description TEXT,
              status TEXT,
              recommended_action TEXT,
              created_at TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS objective_changes (
              change_id TEXT PRIMARY KEY,
              task_id TEXT,
              change_type TEXT,
              old_objective TEXT,
              new_objective TEXT,
              reason TEXT,
              parent_project_objective TEXT,
              created_at TEXT
            );
            """
        )


def init_task_db(path: Path) -> None:
    with managed_connection(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS objects (
              object_id TEXT PRIMARY KEY,
              namespace TEXT NOT NULL,
              type TEXT NOT NULL,
              arena TEXT NOT NULL,
              status TEXT NOT NULL,
              confidence REAL DEFAULT 0.5,
              salience REAL DEFAULT 0.0,
              ttl TEXT DEFAULT 'task',
              content_hash TEXT,
              path TEXT,
              summary TEXT,
              source_refs_json TEXT,
              derived_from_json TEXT,
              supersedes_json TEXT,
              invalidated_by_json TEXT,
              access_policy TEXT,
              import_policy TEXT,
              created_at TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS edges (
              src_id TEXT NOT NULL,
              relation TEXT NOT NULL,
              dst_id TEXT NOT NULL,
              confidence REAL DEFAULT 1.0,
              PRIMARY KEY (src_id, relation, dst_id)
            );

            CREATE TABLE IF NOT EXISTS events (
              event_id TEXT PRIMARY KEY,
              namespace TEXT NOT NULL,
              type TEXT NOT NULL,
              time TEXT NOT NULL,
              object_refs_json TEXT,
              summary TEXT,
              payload_path TEXT,
              event_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              status TEXT,
              started_at TEXT,
              ended_at TEXT,
              manifest_path TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS fts_objects USING fts5(object_id, type, summary, content);
            """
        )


def init_layer_index_db(path: Path) -> None:
    with managed_connection(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS index_entries (
              entry_id TEXT PRIMARY KEY,
              object_id TEXT NOT NULL,
              scope TEXT NOT NULL,
              layer TEXT NOT NULL,
              object_type TEXT NOT NULL,
              status TEXT NOT NULL,
              arena TEXT,
              ttl TEXT,
              summary TEXT,
              content TEXT,
              storage_path TEXT,
              pointer_uri TEXT,
              tags_json TEXT,
              source_refs_json TEXT,
              created_at TEXT,
              updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS pointer_edges (
              edge_id TEXT PRIMARY KEY,
              src_entry_id TEXT NOT NULL,
              relation TEXT NOT NULL,
              dst_uri TEXT NOT NULL,
              reason TEXT,
              created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS import_copies (
              copy_id TEXT PRIMARY KEY,
              source_entry_id TEXT NOT NULL,
              source_pointer_uri TEXT NOT NULL,
              target_scope TEXT NOT NULL,
              target_path TEXT NOT NULL,
              copied_at TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS fts_index_entries USING fts5(entry_id, layer, object_type, summary, content, tags);
            """
        )


def upsert_index_entry(index_db: Path, record: dict[str, Any]) -> None:
    init_layer_index_db(index_db)
    with managed_connection(index_db) as conn:
        conn.execute(
            """
            INSERT INTO index_entries(entry_id, object_id, scope, layer, object_type, status, arena, ttl, summary, content,
              storage_path, pointer_uri, tags_json, source_refs_json, created_at, updated_at)
            VALUES(:entry_id, :object_id, :scope, :layer, :object_type, :status, :arena, :ttl, :summary, :content,
              :storage_path, :pointer_uri, :tags_json, :source_refs_json, :created_at, :updated_at)
            ON CONFLICT(entry_id) DO UPDATE SET
              status=excluded.status,
              summary=excluded.summary,
              content=excluded.content,
              storage_path=excluded.storage_path,
              pointer_uri=excluded.pointer_uri,
              tags_json=excluded.tags_json,
              source_refs_json=excluded.source_refs_json,
              updated_at=excluded.updated_at
            """,
            record,
        )
        conn.execute("DELETE FROM fts_index_entries WHERE entry_id = ?", (record["entry_id"],))
        conn.execute(
            "INSERT INTO fts_index_entries(entry_id, layer, object_type, summary, content, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (
                record["entry_id"],
                record["layer"],
                record["object_type"],
                record["summary"],
                record.get("content", ""),
                record.get("tags_json", "[]"),
            ),
        )


def search_layer_index(index_db: Path, query: str, limit: int = 10) -> list[dict[str, Any]]:
    init_layer_index_db(index_db)
    if not query.strip():
        sql = "SELECT * FROM index_entries ORDER BY updated_at DESC LIMIT ?"
        params: tuple[Any, ...] = (limit,)
    else:
        sql = """
        SELECT e.*
        FROM fts_index_entries f
        JOIN index_entries e ON e.entry_id = f.entry_id
        WHERE fts_index_entries MATCH ?
        LIMIT ?
        """
        params = (query, limit)
    with managed_connection(index_db) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def record_import_copy(index_db: Path, record: dict[str, Any]) -> None:
    init_layer_index_db(index_db)
    with managed_connection(index_db) as conn:
        conn.execute(
            """
            INSERT INTO import_copies(copy_id, source_entry_id, source_pointer_uri, target_scope, target_path, copied_at)
            VALUES(:copy_id, :source_entry_id, :source_pointer_uri, :target_scope, :target_path, :copied_at)
            """,
            record,
        )


def upsert_project(kernel_db: Path, record: dict[str, Any]) -> None:
    with managed_connection(kernel_db) as conn:
        conn.execute(
            """
            INSERT INTO projects(project_id, portfolio_id, program_id, domain_id, status, title, path, execution_mode, current_task_id, created_at, updated_at)
            VALUES(:project_id, :portfolio_id, :program_id, :domain_id, :status, :title, :path, :execution_mode, :current_task_id, :created_at, :updated_at)
            ON CONFLICT(project_id) DO UPDATE SET
              status=excluded.status,
              title=excluded.title,
              path=excluded.path,
              execution_mode=excluded.execution_mode,
              current_task_id=excluded.current_task_id,
              updated_at=excluded.updated_at
            """,
            record,
        )


def upsert_task(kernel_db: Path, record: dict[str, Any]) -> None:
    with managed_connection(kernel_db) as conn:
        conn.execute(
            """
            INSERT INTO tasks(task_id, project_id, parent_node_id, status, title, path, queue_rank, created_at, updated_at)
            VALUES(:task_id, :project_id, :parent_node_id, :status, :title, :path, :queue_rank, :created_at, :updated_at)
            ON CONFLICT(task_id) DO UPDATE SET
              status=excluded.status,
              title=excluded.title,
              path=excluded.path,
              queue_rank=excluded.queue_rank,
              updated_at=excluded.updated_at
            """,
            record,
        )


def sync_project_graph(project_db: Path, records: list[dict[str, Any]]) -> None:
    init_project_db(project_db)
    with managed_connection(project_db) as conn:
        for record in records:
            if record.get("record_type") == "node":
                conn.execute(
                    """
                    INSERT INTO task_nodes(node_id, node_type, parent_id, title, objective, status, priority, project_impact,
                      implementation_confidence, verification_clarity, rework_risk, parallelizable, created_at, updated_at)
                    VALUES(:node_id, :node_type, :parent_id, :title, :objective, :status, :priority, :project_impact,
                      :implementation_confidence, :verification_clarity, :rework_risk, :parallelizable, :created_at, :updated_at)
                    ON CONFLICT(node_id) DO UPDATE SET
                      parent_id=excluded.parent_id,
                      title=excluded.title,
                      objective=excluded.objective,
                      status=excluded.status,
                      priority=excluded.priority,
                      project_impact=excluded.project_impact,
                      implementation_confidence=excluded.implementation_confidence,
                      verification_clarity=excluded.verification_clarity,
                      rework_risk=excluded.rework_risk,
                      parallelizable=excluded.parallelizable,
                      updated_at=excluded.updated_at
                    """,
                    {**record, "parallelizable": 1 if record.get("parallelizable") else 0},
                )
            elif record.get("record_type") == "edge":
                conn.execute(
                    """
                    INSERT INTO task_edges(edge_id, src, dst, relation, strength, reason)
                    VALUES(:edge_id, :src, :dst, :relation, :strength, :reason)
                    ON CONFLICT(edge_id) DO UPDATE SET
                      src=excluded.src,
                      dst=excluded.dst,
                      relation=excluded.relation,
                      strength=excluded.strength,
                      reason=excluded.reason
                    """,
                    record,
                )


def sync_execution_queue(project_db: Path, records: list[dict[str, Any]]) -> None:
    init_project_db(project_db)
    with managed_connection(project_db) as conn:
        conn.execute("DELETE FROM execution_queue")
        for record in records:
            conn.execute(
                """
                INSERT INTO execution_queue(queue_id, task_id, rank, status, score, why_now, score_breakdown_json, updated_at)
                VALUES(:queue_id, :task_id, :rank, :status, :score, :why_now, :score_breakdown_json, :updated_at)
                """,
                {**record, "score_breakdown_json": json.dumps(record.get("score_breakdown", {}), ensure_ascii=False)},
            )
