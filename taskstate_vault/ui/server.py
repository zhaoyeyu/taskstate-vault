from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from taskstate_vault.core import yamlish
from taskstate_vault.core.io import read_jsonl, read_text
from taskstate_vault.core.paths import TaskStateVaultPaths


MAX_FILE_PREVIEW_BYTES = 256_000


def serve_ui(paths: TaskStateVaultPaths, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = _handler_factory(paths)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"TaskState Vault UI: http://{host}:{port}")
    server.serve_forever()


def _handler_factory(paths: TaskStateVaultPaths) -> type[BaseHTTPRequestHandler]:
    class TaskStateVaultUIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/":
                self._send_html(render_dashboard(paths))
                return
            if parsed.path == "/project":
                self._send_html(render_project(paths, _first(query, "id")))
                return
            if parsed.path == "/file":
                self._send_html(render_file(paths, _first(query, "path")))
                return
            if parsed.path == "/api/summary":
                self._send_json(build_summary(paths))
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_html(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, data: Any) -> None:
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return TaskStateVaultUIHandler


def build_summary(paths: TaskStateVaultPaths) -> dict[str, Any]:
    projects = []
    for project_path in sorted(paths.projects_dir.glob("*")) if paths.projects_dir.exists() else []:
        if not project_path.is_dir():
            continue
        project_id = project_path.name
        graph = read_jsonl(project_path / "GOVERNOR" / "TASK_GRAPH.jsonl")
        queue = read_jsonl(project_path / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
        tasks = [p for p in (project_path / "TASKS").glob("*") if p.is_dir()] if (project_path / "TASKS").exists() else []
        projects.append(
            {
                "project_id": project_id,
                "manifest": yamlish.read(project_path / "PROJECT_MANIFEST.yaml", default={}),
                "progress": yamlish.read(project_path / "PROJECT_PROGRESS.yaml", default={}),
                "graph_nodes": len([item for item in graph if item.get("record_type", "node") == "node"]),
                "queue_items": len(queue),
                "tasks": len(tasks),
                "path": _rel(paths, project_path),
            }
        )
    account_objects = _count_jsonl_files(paths.account_dir / "GLOBAL_OBJECTS")
    domains = [p.name for p in sorted(paths.domains_dir.glob("*")) if p.is_dir()] if paths.domains_dir.exists() else []
    return {
        "root": str(paths.workspace),
        "taskfs": str(paths.os_dir),
        "projects": projects,
        "project_registry": read_jsonl(paths.os_dir / "project_registry.jsonl"),
        "workspaces": read_jsonl(paths.account_dir / "GLOBAL_OBJECTS" / "workspace_refs.jsonl"),
        "account_objects": account_objects,
        "domains": domains,
    }


def render_dashboard(paths: TaskStateVaultPaths) -> str:
    summary = build_summary(paths)
    project_rows = []
    for project in summary["projects"]:
        manifest = project.get("manifest", {})
        progress = project.get("progress", {})
        project_rows.append(
            "<tr>"
            f"<td><a href='/project?id={quote(project['project_id'])}'>{esc(project['project_id'])}</a></td>"
            f"<td>{esc(manifest.get('title', ''))}</td>"
            f"<td>{esc(manifest.get('execution_mode', ''))}</td>"
            f"<td>{esc(progress.get('status', ''))}</td>"
            f"<td>{project['graph_nodes']}</td>"
            f"<td>{project['queue_items']}</td>"
            f"<td>{project['tasks']}</td>"
            "</tr>"
        )
    account_cards = "".join(
        f"<div class='metric'><span>{esc(name)}</span><strong>{count}</strong></div>"
        for name, count in summary["account_objects"].items()
    )
    workspace_rows = "".join(
        "<tr>"
        f"<td>{esc(item.get('workspace', ''))}</td>"
        f"<td>{esc(item.get('project_id', ''))}</td>"
        f"<td>{esc(item.get('task_id', ''))}</td>"
        f"<td>{esc(item.get('summary', ''))}</td>"
        "</tr>"
        for item in summary["workspaces"]
    )
    return page(
        "TaskState Vault",
        f"""
        <section class="band">
          <h1>TaskState Vault</h1>
          <p class="muted">Root: {esc(summary["root"])}</p>
          <p class="muted">TaskFS: {esc(summary["taskfs"])}</p>
        </section>
        <section>
          <h2>Projects</h2>
          <table>
            <thead><tr><th>Project</th><th>Title</th><th>Mode</th><th>Status</th><th>Graph</th><th>Queue</th><th>Tasks</th></tr></thead>
            <tbody>{''.join(project_rows) or empty_row(7)}</tbody>
          </table>
        </section>
        <section>
          <h2>Account Objects</h2>
          <div class="metrics">{account_cards or '<p class="muted">No account objects found.</p>'}</div>
        </section>
        <section>
          <h2>Workspaces</h2>
          <table>
            <thead><tr><th>Workspace</th><th>Project</th><th>Task</th><th>Summary</th></tr></thead>
            <tbody>{workspace_rows or empty_row(4)}</tbody>
          </table>
        </section>
        <section>
          <h2>Files</h2>
          <p><a href="/file?path={quote('.taskstate-vault/project_registry.jsonl')}">Project registry</a></p>
        </section>
        """,
    )


def render_project(paths: TaskStateVaultPaths, project_id: str) -> str:
    if not project_id:
        return page("Project", "<p>Missing project id.</p>")
    root = paths.project_dir(project_id)
    manifest = yamlish.read(root / "PROJECT_MANIFEST.yaml", default={})
    progress = yamlish.read(root / "PROJECT_PROGRESS.yaml", default={})
    graph = read_jsonl(root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    queue = read_jsonl(root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
    blockers = read_jsonl(root / "GOVERNOR" / "BLOCKERS.jsonl")
    changes = read_jsonl(root / "GOVERNOR" / "OBJECTIVE_CHANGE_LOG.jsonl")
    task_rows = []
    tasks_dir = root / "TASKS"
    for task_dir in sorted(tasks_dir.glob("*")) if tasks_dir.exists() else []:
        state = yamlish.read(task_dir / "TASK_STATE.yaml", default={})
        runs = [p for p in (task_dir / "RUNS").glob("*") if p.is_dir()] if (task_dir / "RUNS").exists() else []
        task_rows.append(
            "<tr>"
            f"<td>{esc(task_dir.name)}</td>"
            f"<td>{esc(state.get('status', ''))}</td>"
            f"<td>{esc(state.get('objective', ''))}</td>"
            f"<td>{len(runs)}</td>"
            f"<td><a href='/file?path={quote(_rel(paths, task_dir / 'TASK_STATE.yaml'))}'>state</a></td>"
            "</tr>"
        )
    file_links = "".join(
        f"<li><a href='/file?path={quote(_rel(paths, root / rel))}'>{esc(rel)}</a></li>"
        for rel in [
            "PROJECT_INTENT.yaml",
            "PROJECT_MODEL.yaml",
            "PROJECT_PROGRESS.yaml",
            "GOVERNOR/TASK_GRAPH.jsonl",
            "GOVERNOR/EXECUTION_QUEUE.jsonl",
            "GOVERNOR/BLOCKERS.jsonl",
            "GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl",
            "PROJECT_LOGS/event_log.jsonl",
        ]
    )
    return page(
        esc(project_id),
        f"""
        <p><a href="/">Back to dashboard</a></p>
        <section class="band">
          <h1>{esc(manifest.get('title', project_id))}</h1>
          <p class="muted">Project: {esc(project_id)} | Mode: {esc(manifest.get('execution_mode', ''))}</p>
        </section>
        <section class="metrics">
          <div class="metric"><span>Graph records</span><strong>{len(graph)}</strong></div>
          <div class="metric"><span>Queue items</span><strong>{len(queue)}</strong></div>
          <div class="metric"><span>Blockers</span><strong>{len(blockers)}</strong></div>
          <div class="metric"><span>Objective changes</span><strong>{len(changes)}</strong></div>
        </section>
        <section>
          <h2>Progress</h2>
          <pre>{esc(json.dumps(progress, ensure_ascii=False, indent=2))}</pre>
        </section>
        <section>
          <h2>Tasks</h2>
          <table>
            <thead><tr><th>Task</th><th>Status</th><th>Objective</th><th>Runs</th><th>File</th></tr></thead>
            <tbody>{''.join(task_rows) or empty_row(5)}</tbody>
          </table>
        </section>
        <section>
          <h2>Project Files</h2>
          <ul>{file_links}</ul>
        </section>
        """,
    )


def render_file(paths: TaskStateVaultPaths, rel_path: str) -> str:
    rel_path = unquote(rel_path or "")
    base = paths.os_dir.resolve()
    target = (paths.workspace / rel_path).resolve()
    if not str(target).startswith(str(base)):
        return page("File", "<p>File preview is limited to TaskFS files.</p>")
    if not target.exists() or not target.is_file():
        return page("File", f"<p>File not found: {esc(rel_path)}</p>")
    raw = target.read_bytes()[:MAX_FILE_PREVIEW_BYTES]
    text = raw.decode("utf-8", errors="replace")
    suffix = "" if target.stat().st_size <= MAX_FILE_PREVIEW_BYTES else "\n\n[Preview truncated]"
    return page(esc(rel_path), f"<p><a href='/'>Dashboard</a></p><h1>{esc(rel_path)}</h1><pre>{esc(text + suffix)}</pre>")


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{ color-scheme: light; --line:#d7dde5; --text:#17202a; --muted:#657080; --bg:#f7f9fb; --panel:#ffffff; --accent:#176b87; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--text); background: var(--bg); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    section {{ margin: 0 0 22px; }}
    .band {{ border-bottom: 1px solid var(--line); padding-bottom: 18px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin: 0 0 10px; font-size: 18px; }}
    p {{ line-height: 1.45; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); margin: 4px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #eef3f7; font-weight: 600; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); padding: 12px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
    .metric strong {{ font-size: 22px; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #101820; color: #f2f6fa; padding: 14px; border-radius: 6px; }}
  </style>
</head>
<body><main>{body}</main></body>
</html>"""


def _count_jsonl_files(directory: Path) -> dict[str, int]:
    if not directory.exists():
        return {}
    return {path.name: len(read_jsonl(path)) for path in sorted(directory.glob("*.jsonl"))}


def _rel(paths: TaskStateVaultPaths, path: Path) -> str:
    return path.resolve().relative_to(paths.workspace.resolve()).as_posix()


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key, [])
    return values[0] if values else ""


def empty_row(columns: int) -> str:
    return f"<tr><td colspan='{columns}' class='muted'>No records found.</td></tr>"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)
