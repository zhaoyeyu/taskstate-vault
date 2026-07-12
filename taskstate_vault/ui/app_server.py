from __future__ import annotations

import difflib
import json
import logging
import mimetypes
import secrets
import shutil
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from taskstate_vault.core import yamlish
from taskstate_vault.core.ids import make_id
from taskstate_vault.core.io import read_jsonl, read_text, rewrite_jsonl, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.files import queue_path
from taskstate_vault.governor.graph import read_graph, update_node, write_graph
from taskstate_vault.governor.manager import create_project
from taskstate_vault.governor.queue import reschedule_queue
from taskstate_vault.kernel.task import create_task_from_queue
from taskstate_vault.ui import server as legacy
from taskstate_vault.ui.security import is_loopback_host


STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_LANG = "zh"
SUPPORTED_LANGS = {"zh", "en"}
MAX_JSON_BODY_BYTES = 1_000_000
SESSION_TTL_SECONDS = 12 * 60 * 60
LOGIN_WINDOW_SECONDS = 60
MAX_LOGIN_ATTEMPTS = 8
LOGGER = logging.getLogger(__name__)
SENSITIVE_KEYWORDS = {
    "private",
    "personal",
    "sensitive",
    "confidential",
    "restricted",
}


TRANSLATIONS = {
    "zh": {
        "login_failed": "登录失败。",
        "login_required": "需要登录。",
        "advanced_required": "需要开启高级权限。",
        "not_found": "找不到请求的资源。",
        "invalid_json": "请求 JSON 无效。",
        "cycle": "不能创建环形依赖。",
        "unsafe_path": "文件路径不在允许范围内。",
        "archive_first": "永久删除前必须先归档。",
        "invalid_origin": "请求来源不受信任。",
        "rate_limited": "登录尝试过多，请稍后重试。",
        "request_too_large": "请求内容过大。",
        "server_error": "服务器无法完成请求。",
        "ok": "已保存。",
    },
    "en": {
        "login_failed": "Login failed.",
        "login_required": "Login is required.",
        "advanced_required": "Advanced permission is required.",
        "not_found": "Resource not found.",
        "invalid_json": "Invalid JSON request.",
        "cycle": "Dependency would create a cycle.",
        "unsafe_path": "File path is outside allowed roots.",
        "archive_first": "Archive before permanent delete.",
        "invalid_origin": "The request origin is not trusted.",
        "rate_limited": "Too many login attempts. Try again shortly.",
        "request_too_large": "The request body is too large.",
        "server_error": "The server could not complete the request.",
        "ok": "Saved.",
    },
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code


def serve_ui(
    paths: TaskStateVaultPaths,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    allow_network: bool = False,
) -> None:
    if not is_loopback_host(host) and not allow_network:
        raise ValueError("Refusing a non-loopback UI bind without --allow-network.")
    if not is_loopback_host(host):
        print("WARNING: network mode uses plain HTTP; place the console behind a trusted TLS proxy.")
    initial_password = legacy.initialize_admin_account(paths)
    if initial_password:
        print(f"Initial admin password: {initial_password}")
        print("Change it from Settings after the first login.")
    handler = _handler_factory(paths)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"TaskState Vault Console: http://{host}:{port}")
    server.serve_forever()


def _handler_factory(paths: TaskStateVaultPaths) -> type[BaseHTTPRequestHandler]:
    sessions: dict[str, dict[str, Any]] = {}
    login_attempts: dict[str, list[float]] = {}

    class TaskStateVaultAppHandler(BaseHTTPRequestHandler):
        server_version = "TaskStateVaultConsole/0.1"

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PATCH(self) -> None:
            self._dispatch("PATCH")

        def do_DELETE(self) -> None:
            self._dispatch("DELETE")

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _dispatch(self, method: str) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path.startswith("/api/"):
                    if method in {"POST", "PATCH", "DELETE"}:
                        self._validate_request_origin()
                    payload = self._route_api(method, parsed.path, parse_qs(parsed.query))
                    self._send_json(payload)
                    return
                self._serve_static(parsed.path)
            except ApiError as exc:
                self._send_json({"ok": False, "error": {"code": exc.code, "message": _msg(self._ctx(), exc.code, exc.message)}}, exc.status)
            except Exception:  # pragma: no cover - defensive local UI boundary
                LOGGER.exception("TaskState Vault UI request failed")
                self._send_json(
                    {"ok": False, "error": {"code": "server_error", "message": _msg(self._ctx(), "server_error")}},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def _route_api(self, method: str, path: str, query: dict[str, list[str]]) -> dict[str, Any]:
            ctx = self._ctx()
            body = self._json_body() if method in {"POST", "PATCH", "DELETE"} else {}
            parts = [unquote(part) for part in path.strip("/").split("/")]

            if method == "GET" and path == "/api/bootstrap":
                return {"ok": True, "data": build_bootstrap(paths, ctx)}
            if method == "GET" and path == "/api/session":
                return {"ok": True, "data": ctx}
            if method == "POST" and path == "/api/session/login":
                client = str(self.client_address[0])
                now = time.monotonic()
                attempts = [stamp for stamp in login_attempts.get(client, []) if now - stamp < LOGIN_WINDOW_SECONDS]
                if len(attempts) >= MAX_LOGIN_ATTEMPTS:
                    raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited")
                username = str(body.get("username", ""))
                password = str(body.get("password", ""))
                if not legacy._verify_account(paths, username, password):
                    attempts.append(now)
                    login_attempts[client] = attempts
                    raise ApiError(HTTPStatus.UNAUTHORIZED, "login_failed")
                login_attempts.pop(client, None)
                token = secrets.token_urlsafe(32)
                sessions[token] = {
                    "username": username,
                    "advanced": False,
                    "lang": ctx["lang"],
                    "expires_at": time.monotonic() + SESSION_TTL_SECONDS,
                }
                self._set_cookie("tsv_session", token, max_age=SESSION_TTL_SECONDS)
                return {"ok": True, "data": self._ctx(token)}
            if method == "POST" and path == "/api/session/logout":
                token = self._cookies().get("tsv_session", "")
                sessions.pop(token, None)
                self._set_cookie("tsv_session", "", max_age=0)
                return {"ok": True, "data": self._ctx("")}
            if method == "POST" and path == "/api/session/language":
                lang = str(body.get("lang", DEFAULT_LANG))
                if lang not in SUPPORTED_LANGS:
                    lang = DEFAULT_LANG
                token = self._cookies().get("tsv_session", "")
                if token in sessions:
                    sessions[token]["lang"] = lang
                self._set_cookie("tsv_lang", lang)
                return {"ok": True, "data": self._ctx(token)}
            if method == "POST" and path == "/api/session/advanced":
                _require_login(ctx)
                enabled = bool(body.get("enabled"))
                token = self._cookies().get("tsv_session", "")
                sessions[token]["advanced"] = enabled
                return {"ok": True, "data": self._ctx(token)}
            if method == "POST" and path == "/api/session/password":
                _require_login(ctx)
                try:
                    legacy._change_password(paths, str(ctx["username"]), str(body.get("oldPassword", "")), str(body.get("newPassword", "")), str(body.get("repeatPassword", "")))
                except ValueError as exc:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_password", str(exc)) from exc
                return {"ok": True, "data": {"message": _msg(ctx, "ok")}}

            if method == "GET" and path == "/api/projects":
                _require_login(ctx)
                return {"ok": True, "data": list_projects(paths, ctx, query)}
            if method == "POST" and path == "/api/projects":
                _require_login(ctx)
                project = create_project(paths, str(body.get("title", "")), execution_mode=str(body.get("executionMode") or "complex_project"), project_id=str(body.get("projectId") or "") or None, workspace_path=body.get("workspace") or None)
                return {"ok": True, "data": project}
            if len(parts) == 3 and parts[:2] == ["api", "projects"] and method == "GET":
                _require_login(ctx)
                return {"ok": True, "data": project_detail(paths, parts[2], ctx)}
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "visibility" and method == "POST":
                _require_advanced(ctx)
                return {"ok": True, "data": set_project_visibility(paths, parts[2], bool(body.get("hidden")), str(ctx.get("username") or ""))}
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "archive" and method == "POST":
                _require_advanced(ctx)
                legacy.archive_project(paths, parts[2], str(body.get("reason", "")), str(ctx.get("username") or ""))
                return {"ok": True, "data": project_detail(paths, parts[2], ctx)}
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "restore" and method == "POST":
                _require_advanced(ctx)
                legacy.restore_project(paths, parts[2], str(body.get("status") or "active"), str(ctx.get("username") or ""))
                return {"ok": True, "data": project_detail(paths, parts[2], ctx)}
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "permanent" and method == "DELETE":
                _require_advanced(ctx)
                legacy.permanent_delete_project(paths, parts[2], str(body.get("confirm", "")), str(body.get("repairConfirm", "")), str(ctx.get("username") or ""))
                return {"ok": True, "data": {"deleted": True, "projectId": parts[2]}}

            if len(parts) == 4 and parts[:2] == ["api", "graph"] and parts[3] == "layout" and method == "POST":
                _require_login(ctx)
                save_graph_layout(paths, parts[2], body)
                return {"ok": True, "data": graph_payload(paths, parts[2], ctx)}
            if len(parts) == 4 and parts[:2] == ["api", "graph"] and parts[3] == "edge" and method == "POST":
                _require_login(ctx)
                add_graph_edge(paths, parts[2], str(body.get("src", "")), str(body.get("dst", "")), str(body.get("relation") or "depends_on"))
                return {"ok": True, "data": graph_payload(paths, parts[2], ctx)}
            if len(parts) == 4 and parts[:2] == ["api", "graph"] and parts[3] == "edge" and method == "DELETE":
                _require_login(ctx)
                remove_graph_edge(paths, parts[2], str(body.get("edgeId", "")), str(body.get("src", "")), str(body.get("dst", "")))
                return {"ok": True, "data": graph_payload(paths, parts[2], ctx)}

            if len(parts) == 4 and parts[:2] == ["api", "tasks"] and method == "GET":
                _require_login(ctx)
                return {"ok": True, "data": task_detail(paths, parts[2], parts[3], ctx)}
            if len(parts) == 4 and parts[:2] == ["api", "tasks"] and method == "PATCH":
                _require_login(ctx)
                return {"ok": True, "data": update_task(paths, parts[2], parts[3], body, ctx)}
            if len(parts) == 5 and parts[:2] == ["api", "tasks"] and parts[4] == "visibility" and method == "POST":
                _require_advanced(ctx)
                legacy.set_task_hidden(paths, parts[2], parts[3], bool(body.get("hidden")), str(ctx.get("username") or ""))
                return {"ok": True, "data": task_detail(paths, parts[2], parts[3], ctx)}
            if len(parts) == 5 and parts[:2] == ["api", "tasks"] and parts[4] == "archive" and method == "POST":
                _require_advanced(ctx)
                legacy.archive_task(paths, parts[2], parts[3], str(body.get("reason", "")), str(ctx.get("username") or ""))
                return {"ok": True, "data": task_detail(paths, parts[2], parts[3], ctx)}
            if len(parts) == 5 and parts[:2] == ["api", "tasks"] and parts[4] == "restore" and method == "POST":
                _require_advanced(ctx)
                legacy.restore_task(paths, parts[2], parts[3], str(body.get("status") or "active"), str(ctx.get("username") or ""))
                return {"ok": True, "data": task_detail(paths, parts[2], parts[3], ctx)}
            if len(parts) == 5 and parts[:2] == ["api", "tasks"] and parts[4] == "permanent" and method == "DELETE":
                _require_advanced(ctx)
                legacy.permanent_delete_task(paths, parts[2], parts[3], str(body.get("confirm", "")), str(body.get("repairConfirm", "")), str(ctx.get("username") or ""))
                return {"ok": True, "data": {"deleted": True, "projectId": parts[2], "taskId": parts[3]}}

            if len(parts) == 3 and parts[:2] == ["api", "queue"] and method == "POST":
                _require_login(ctx)
                update_queue(paths, parts[2], body)
                return {"ok": True, "data": queue_payload(paths, parts[2])}
            if len(parts) == 4 and parts[:2] == ["api", "queue"] and parts[3] == "open" and method == "POST":
                _require_login(ctx)
                return {"ok": True, "data": create_task_from_queue(paths, parts[2], int(body.get("rank") or 1))}

            if method == "GET" and path == "/api/records":
                _require_login(ctx)
                return {"ok": True, "data": records_payload(paths, ctx, query)}
            if method == "GET" and path == "/api/hidden":
                _require_advanced(ctx)
                return {"ok": True, "data": hidden_payload(paths, ctx)}
            if method == "GET" and path == "/api/archive":
                _require_advanced(ctx)
                return {"ok": True, "data": archive_payload(paths, ctx)}
            if method == "GET" and path == "/api/files":
                _require_advanced(ctx)
                return {"ok": True, "data": list_state_files(paths, ctx, query)}
            if method == "POST" and path == "/api/files/read":
                _require_advanced(ctx)
                target = safe_file_path(paths, str(body.get("path", "")))
                return {"ok": True, "data": {"path": str(target), "content": read_text(target, "")}}
            if method == "POST" and path == "/api/files/diff":
                _require_advanced(ctx)
                target = safe_file_path(paths, str(body.get("path", "")))
                old = read_text(target, "")
                new = str(body.get("content", ""))
                return {"ok": True, "data": {"path": str(target), "diff": unified_diff(old, new, str(target))}}
            if method == "POST" and path == "/api/files/save":
                _require_advanced(ctx)
                target = safe_file_path(paths, str(body.get("path", "")))
                content = str(body.get("content", ""))
                backup = backup_file(target)
                write_text(target, content)
                return {"ok": True, "data": {"path": str(target), "backup": str(backup), "message": _msg(ctx, "ok")}}
            if method == "GET" and path == "/api/settings":
                _require_login(ctx)
                return {"ok": True, "data": {"preferences": legacy._load_preferences(paths), "session": ctx}}
            if method == "POST" and path == "/api/settings":
                _require_login(ctx)
                prefs = legacy._load_preferences(paths)
                prefs.update({key: body[key] for key in body.keys() if key in {"show_internal_ids", "show_raw_paths", "show_archived", "advanced_editor_enabled", "backup_retention", "hidden_keywords", "deletion_confirmation_strength"}})
                legacy._save_preferences(paths, prefs)
                return {"ok": True, "data": prefs}

            raise ApiError(HTTPStatus.NOT_FOUND, "not_found")

        def _json_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError as exc:
                raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_json") from exc
            if length <= 0:
                return {}
            if length > MAX_JSON_BODY_BYTES:
                raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request_too_large")
            raw = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_json") from exc
            return data if isinstance(data, dict) else {}

        def _ctx(self, token: str | None = None) -> dict[str, Any]:
            cookies = self._cookies()
            lang = cookies.get("tsv_lang", DEFAULT_LANG)
            if lang not in SUPPORTED_LANGS:
                lang = DEFAULT_LANG
            session_token = token if token is not None else cookies.get("tsv_session", "")
            session = sessions.get(session_token or "", {})
            if session and float(session.get("expires_at") or 0) <= time.monotonic():
                sessions.pop(session_token or "", None)
                session = {}
            return {
                "loggedIn": bool(session.get("username")),
                "username": session.get("username"),
                "advanced": bool(session.get("advanced")),
                "lang": str(session.get("lang") or lang),
                "permission": "advanced" if session.get("advanced") else "normal",
            }

        def _cookies(self) -> dict[str, str]:
            cookies: dict[str, str] = {}
            for part in (self.headers.get("Cookie") or "").split(";"):
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                cookies[key.strip()] = unquote(value.strip())
            return cookies

        def _set_cookie(self, key: str, value: str, max_age: int | None = None) -> None:
            cookie = f"{key}={value}; Path=/; SameSite=Strict; HttpOnly"
            if max_age is not None:
                cookie += f"; Max-Age={max_age}"
            self._pending_cookie = cookie

        def _validate_request_origin(self) -> None:
            origin = (self.headers.get("Origin") or "").rstrip("/")
            if not origin:
                return
            host = self.headers.get("Host") or ""
            if origin not in {f"http://{host}", f"https://{host}"}:
                raise ApiError(HTTPStatus.FORBIDDEN, "invalid_origin")

        def _send_json(self, data: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            cookie = getattr(self, "_pending_cookie", None)
            if cookie:
                self.send_header("Set-Cookie", cookie)
                self._pending_cookie = None
            self.end_headers()
            self.wfile.write(raw)

        def _serve_static(self, path: str) -> None:
            if path in {"", "/"}:
                rel = "index.html"
            else:
                rel = path.lstrip("/")
            target = (STATIC_DIR / rel).resolve()
            static_root = STATIC_DIR.resolve()
            if not target.is_relative_to(static_root) or not target.exists() or target.is_dir():
                target = static_root / "index.html"
            if not target.exists():
                body = _missing_build_html().encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
                return
            content = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(content)

    return TaskStateVaultAppHandler


def _msg(ctx: dict[str, Any], key: str, fallback: str | None = None) -> str:
    return TRANSLATIONS.get(str(ctx.get("lang") or DEFAULT_LANG), TRANSLATIONS["zh"]).get(key, fallback or key)


def _require_login(ctx: dict[str, Any]) -> None:
    if not ctx.get("loggedIn"):
        raise ApiError(HTTPStatus.UNAUTHORIZED, "login_required")


def _require_advanced(ctx: dict[str, Any]) -> None:
    _require_login(ctx)
    if not ctx.get("advanced"):
        raise ApiError(HTTPStatus.FORBIDDEN, "advanced_required")


def _missing_build_html() -> str:
    return """<!doctype html><meta charset="utf-8"><title>TaskState Vault</title>
<style>body{font-family:Inter,Segoe UI,sans-serif;margin:48px;color:#172033;background:#f6f8fb}code{background:#e9eef5;padding:2px 6px;border-radius:5px}</style>
<h1>TaskState Vault Console</h1><p>Frontend build is missing. Run <code>cd frontend && npm install && npm run build</code>, then restart <code>taskstate-vault ui serve</code>.</p>"""


def build_bootstrap(paths: TaskStateVaultPaths, ctx: dict[str, Any]) -> dict[str, Any]:
    if not ctx.get("loggedIn"):
        return {
            "session": ctx,
            "settings": {},
            "overview": {
                "root": "",
                "projectCount": 0,
                "activeTasks": 0,
                "blockedTasks": 0,
                "queueItems": 0,
                "hiddenCount": 0,
                "archivedCount": 0,
            },
            "projects": {"projects": [], "groups": [], "hiddenProjects": [], "archivedProjects": []},
        }
    projects = list_projects(paths, ctx, {})
    visible = projects["projects"]
    active_tasks = sum(project.get("activeTasks", 0) for project in visible)
    blocked_tasks = sum(project.get("blockedTasks", 0) for project in visible)
    queue_items = sum(project.get("queueItems", 0) for project in visible)
    return {
        "session": ctx,
        "settings": legacy._load_preferences(paths),
        "overview": {
            "root": str(paths.workspace),
            "projectCount": len(visible),
            "activeTasks": active_tasks,
            "blockedTasks": blocked_tasks,
            "queueItems": queue_items,
            "hiddenCount": len(projects.get("hiddenProjects", [])),
            "archivedCount": len(projects.get("archivedProjects", [])),
        },
        "projects": projects,
    }


def list_projects(paths: TaskStateVaultPaths, ctx: dict[str, Any], query: dict[str, list[str]]) -> dict[str, Any]:
    visibility = legacy._load_visibility(paths)
    projects: list[dict[str, Any]] = []
    for project_root in sorted(paths.projects_dir.glob("*")) if paths.projects_dir.exists() else []:
        if not project_root.is_dir():
            continue
        project_id = project_root.name
        manifest = yamlish.read(project_root / "PROJECT_MANIFEST.yaml", default={})
        graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
        queue = read_jsonl(project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
        nodes = [item for item in graph if item.get("record_type") == "node"]
        hidden = is_project_hidden(paths, project_id, manifest, visibility)
        archived = project_id in visibility.get("archived_projects", {}) or manifest.get("status") == "archived"
        category = project_category(project_id, manifest)
        item = {
            "id": project_id,
            "title": manifest.get("title") or project_id,
            "status": manifest.get("status") or "active",
            "executionMode": manifest.get("execution_mode") or "",
            "category": category,
            "workspace": manifest.get("paths", {}).get("external_workspace", ""),
            "hidden": hidden,
            "archived": archived,
            "nodeCount": len(nodes),
            "taskCount": len([node for node in nodes if node.get("node_type") == "task"]),
            "activeTasks": len([node for node in nodes if node.get("status") == "active"]),
            "blockedTasks": len([node for node in nodes if node.get("status") == "blocked"]),
            "queueItems": len(queue),
            "updatedAt": manifest.get("updated_at", ""),
        }
        projects.append(item)
    q = str(_first(query, "q") or "").lower()
    status = str(_first(query, "status") or "")
    if q:
        projects = [item for item in projects if q in f"{item['id']} {item['title']} {item['category']['path']}".lower()]
    if status:
        projects = [item for item in projects if item.get("status") == status]
    hidden_projects = [item for item in projects if item["hidden"]]
    archived_projects = [item for item in projects if item["archived"]]
    if not ctx.get("advanced"):
        projects = [item for item in projects if not item["hidden"] and not item["archived"]]
    groups: dict[str, dict[str, Any]] = {}
    for item in projects:
        group_key = item["category"]["path"]
        group = groups.setdefault(group_key, {"path": group_key, "section": item["category"]["section"], "name": item["category"]["name"], "projects": []})
        group["projects"].append(item)
    return {"projects": projects, "groups": list(groups.values()), "hiddenProjects": hidden_projects, "archivedProjects": archived_projects}


def project_detail(paths: TaskStateVaultPaths, project_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    manifest_path = paths.project_dir(project_id) / "PROJECT_MANIFEST.yaml"
    if not manifest_path.exists():
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found")
    manifest = yamlish.read(manifest_path, default={})
    visibility = legacy._load_visibility(paths)
    if is_project_hidden(paths, project_id, manifest, visibility) and not ctx.get("advanced"):
        raise ApiError(HTTPStatus.FORBIDDEN, "advanced_required")
    graph = graph_payload(paths, project_id, ctx)
    return {
        "project": next((p for p in list_projects(paths, {**ctx, "advanced": True}, {})["projects"] if p["id"] == project_id), {"id": project_id, "title": project_id}),
        "manifest": manifest,
        "graph": graph,
        "queue": queue_payload(paths, project_id),
        "records": records_payload(paths, ctx, {"project": [project_id], "limit": ["80"]}),
        "files": list_state_files(paths, ctx, {"project": [project_id]}),
    }


def graph_payload(paths: TaskStateVaultPaths, project_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    records = read_graph(paths, project_id)
    visibility = legacy._load_visibility(paths)
    layout = legacy._load_graph_layout(paths).get("projects", {}).get(project_id, {})
    nodes = []
    for index, node in enumerate([item for item in records if item.get("record_type") == "node"]):
        hidden = node.get("node_id") in visibility.get("hidden_tasks", {}).get(project_id, [])
        if hidden and not ctx.get("advanced"):
            continue
        node_id = str(node.get("node_id"))
        pos = layout.get(node_id, {})
        nodes.append({
            **node,
            "id": node_id,
            "hidden": hidden,
            "position": {"x": float(pos.get("x", (index % 4) * 260)), "y": float(pos.get("y", (index // 4) * 150))},
        })
    visible_ids = {node["id"] for node in nodes}
    edges = []
    for edge in [item for item in records if item.get("record_type") == "edge"]:
        if edge.get("src") in visible_ids and edge.get("dst") in visible_ids:
            edges.append({**edge, "id": edge.get("edge_id") or make_id("edge", f"{edge.get('src')}_{edge.get('dst')}")})
    return {"nodes": nodes, "edges": edges}


def queue_payload(paths: TaskStateVaultPaths, project_id: str) -> dict[str, Any]:
    queue = read_jsonl(queue_path(paths, project_id))
    return {"items": sorted(queue, key=lambda item: int(item.get("rank", 9999)))}


def task_detail(paths: TaskStateVaultPaths, project_id: str, task_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    visibility = legacy._load_visibility(paths)
    if task_id in visibility.get("hidden_tasks", {}).get(project_id, []) and not ctx.get("advanced"):
        raise ApiError(HTTPStatus.FORBIDDEN, "advanced_required")
    graph = read_graph(paths, project_id)
    node = next((item for item in graph if item.get("record_type") == "node" and item.get("node_id") == task_id), {})
    task_root = paths.task_dir(project_id, task_id)
    state = yamlish.read(task_root / "CURRENT" / "TASK_STATE.yaml", default={})
    next_action = read_text(task_root / "CURRENT" / "NEXT_ACTION.md", "")
    return {
        "projectId": project_id,
        "taskId": task_id,
        "node": node,
        "state": state,
        "nextAction": next_action,
        "records": records_payload(paths, ctx, {"project": [project_id], "task": [task_id], "limit": ["120"]}),
        "files": list_state_files(paths, ctx, {"project": [project_id], "task": [task_id]}),
        "hidden": task_id in visibility.get("hidden_tasks", {}).get(project_id, []),
        "archived": task_id in visibility.get("archived_tasks", {}).get(project_id, {}),
    }


def update_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, data: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    allowed = {key: data[key] for key in ["title", "status", "priority", "parent_id", "objective"] if key in data}
    if allowed:
        update_node(paths, project_id, task_id, **allowed)
    task_root = paths.task_dir(project_id, task_id)
    state_path = task_root / "CURRENT" / "TASK_STATE.yaml"
    state = yamlish.read(state_path, default={})
    for key in ["title", "status", "priority", "objective", "acceptance_criteria"]:
        if key in data:
            state[key] = data[key]
    state["updated_at"] = now_iso()
    yamlish.write(state_path, state)
    if "nextAction" in data:
        write_text(task_root / "CURRENT" / "NEXT_ACTION.md", str(data.get("nextAction") or ""))
    return task_detail(paths, project_id, task_id, ctx)


def records_payload(paths: TaskStateVaultPaths, ctx: dict[str, Any], query: dict[str, list[str]]) -> dict[str, Any]:
    filters = {key: _first(query, key) for key in ["project", "task", "type", "status", "q"] if _first(query, key)}
    try:
        records = legacy.collect_log_records(paths, {"advanced": bool(ctx.get("advanced")), "lang": ctx.get("lang", DEFAULT_LANG)}, filters, limit=int(_first(query, "limit") or 200), scope="all" if ctx.get("advanced") else "visible")
    except Exception:
        records = []
    return {"records": records}


def hidden_payload(paths: TaskStateVaultPaths, ctx: dict[str, Any]) -> dict[str, Any]:
    projects = list_projects(paths, {**ctx, "advanced": True}, {})
    return {
        "projects": projects["hiddenProjects"],
        "records": records_payload(paths, ctx, {"status": ["hidden"], "limit": ["200"]})["records"],
        "visibility": legacy._load_visibility(paths),
    }


def archive_payload(paths: TaskStateVaultPaths, ctx: dict[str, Any]) -> dict[str, Any]:
    projects = list_projects(paths, {**ctx, "advanced": True}, {})
    return {
        "projects": projects["archivedProjects"],
        "records": records_payload(paths, ctx, {"status": ["archived"], "limit": ["200"]})["records"],
        "visibility": legacy._load_visibility(paths),
    }


def set_project_visibility(paths: TaskStateVaultPaths, project_id: str, hidden: bool, actor: str) -> dict[str, Any]:
    legacy.set_project_hidden(paths, project_id, hidden, actor)
    return {"projectId": project_id, "hidden": hidden}


def save_graph_layout(paths: TaskStateVaultPaths, project_id: str, data: dict[str, Any]) -> None:
    layout = legacy._load_graph_layout(paths)
    project_layout = layout.setdefault("projects", {}).setdefault(project_id, {})
    for item in data.get("nodes", []):
        node_id = str(item.get("id") or item.get("node_id") or "")
        if not node_id:
            continue
        position = item.get("position") or {}
        project_layout[node_id] = {"x": float(position.get("x", 0)), "y": float(position.get("y", 0)), "updated_at": now_iso()}
    legacy._save_graph_layout(paths, layout)


def add_graph_edge(paths: TaskStateVaultPaths, project_id: str, src: str, dst: str, relation: str = "depends_on") -> None:
    if not src or not dst or src == dst:
        raise ApiError(HTTPStatus.BAD_REQUEST, "cycle")
    records = read_graph(paths, project_id)
    if creates_cycle(records, src, dst):
        raise ApiError(HTTPStatus.BAD_REQUEST, "cycle")
    if any(item.get("record_type") == "edge" and item.get("src") == src and item.get("dst") == dst for item in records):
        return
    records.append({"schema_version": 1, "record_type": "edge", "edge_id": make_id("edge", f"{src}_{dst}_{relation}"), "src": src, "dst": dst, "relation": relation, "reason": "Created in TaskState Vault Console", "created_at": now_iso()})
    write_graph(paths, project_id, records)


def remove_graph_edge(paths: TaskStateVaultPaths, project_id: str, edge_id: str = "", src: str = "", dst: str = "") -> None:
    records = read_graph(paths, project_id)
    remaining = []
    for item in records:
        if item.get("record_type") != "edge":
            remaining.append(item)
            continue
        match = bool(edge_id and item.get("edge_id") == edge_id) or bool(src and dst and item.get("src") == src and item.get("dst") == dst)
        if not match:
            remaining.append(item)
    write_graph(paths, project_id, remaining)


def creates_cycle(records: list[dict[str, Any]], src: str, dst: str) -> bool:
    adjacency: dict[str, list[str]] = {}
    for edge in [item for item in records if item.get("record_type") == "edge"]:
        adjacency.setdefault(str(edge.get("src")), []).append(str(edge.get("dst")))
    adjacency.setdefault(src, []).append(dst)
    seen: set[str] = set()

    def visit(node: str) -> bool:
        if node == src:
            return True
        if node in seen:
            return False
        seen.add(node)
        return any(visit(child) for child in adjacency.get(node, []))

    return visit(dst)


def update_queue(paths: TaskStateVaultPaths, project_id: str, data: dict[str, Any]) -> None:
    op = str(data.get("op") or "")
    if op == "reschedule":
        reschedule_queue(paths, project_id)
        return
    queue = read_jsonl(queue_path(paths, project_id))
    queue_id = str(data.get("queueId") or "")
    for item in queue:
        if item.get("queue_id") == queue_id:
            if op in {"pause", "resume", "remove"}:
                item["status"] = "paused" if op == "pause" else "ready"
            if op == "move":
                item["rank"] = int(data.get("rank") or item.get("rank") or 1)
            item["updated_at"] = now_iso()
    if op == "remove":
        queue = [item for item in queue if item.get("queue_id") != queue_id]
    queue.sort(key=lambda item: int(item.get("rank", 9999)))
    for rank, item in enumerate(queue, start=1):
        item["rank"] = rank
    rewrite_jsonl(queue_path(paths, project_id), queue)


def list_state_files(paths: TaskStateVaultPaths, ctx: dict[str, Any], query: dict[str, list[str]]) -> dict[str, Any]:
    project_id = _first(query, "project")
    task_id = _first(query, "task")
    roots: list[Path] = []
    if project_id and task_id:
        roots.append(paths.task_dir(project_id, task_id))
    elif project_id:
        roots.append(paths.project_dir(project_id))
    else:
        roots.append(paths.os_dir)
    files = []
    for root in roots:
        if not root.exists():
            continue
        for candidate in root.rglob("*"):
            if candidate.is_file() and candidate.suffix.lower() in {".yaml", ".json", ".jsonl", ".md", ".txt"}:
                files.append({"path": str(candidate), "name": candidate.name, "relativePath": str(candidate.relative_to(root)), "size": candidate.stat().st_size, "advancedOnly": True})
                if len(files) >= 200:
                    break
    return {"files": files, "advancedRequired": True}


def safe_file_path(paths: TaskStateVaultPaths, raw_path: str) -> Path:
    target = Path(raw_path).resolve()
    allowed_roots = [paths.os_dir.resolve()]
    if not any(target.is_relative_to(root) for root in allowed_roots):
        raise ApiError(HTTPStatus.FORBIDDEN, "unsafe_path")
    if not target.exists() or not target.is_file():
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found")
    if target.suffix.lower() not in {".yaml", ".json", ".jsonl", ".md", ".txt"}:
        raise ApiError(HTTPStatus.FORBIDDEN, "unsafe_path")
    return target


def backup_file(target: Path) -> Path:
    backup_dir = target.parent / ".tsv_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{target.name}.{now_iso().replace(':', '-').replace('+', '_')}.bak"
    shutil.copy2(target, backup)
    return backup


def unified_diff(old: str, new: str, name: str) -> str:
    return "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=f"{name}.before", tofile=f"{name}.after", lineterm=""))


def project_category(project_id: str, manifest: dict[str, Any]) -> dict[str, str]:
    title = str(manifest.get("title") or project_id)
    haystack = f"{project_id} {title}".lower()
    if "taskstate" in haystack:
        return {"section": "TaskState Vault", "name": "Core Product", "path": "TaskState Vault / Core Product"}
    if any(keyword in haystack for keyword in SENSITIVE_KEYWORDS):
        return {"section": "Sensitive Materials", "name": "Restricted", "path": "Sensitive Materials / Restricted"}
    if "alpha" in haystack or "ops" in haystack:
        return {"section": "Product Labs", "name": "Operations Tools", "path": "Product Labs / Operations Tools"}
    if "research" in haystack:
        return {"section": "Research", "name": "Product Discovery", "path": "Research / Product Discovery"}
    return {"section": "Workspace", "name": "General", "path": "Workspace / General"}


def is_project_hidden(paths: TaskStateVaultPaths, project_id: str, manifest: dict[str, Any], visibility: dict[str, Any]) -> bool:
    if project_id in set(visibility.get("hidden_projects", [])):
        return True
    category = project_category(project_id, manifest)
    if category["name"] in set(visibility.get("hidden_project_groups", [])):
        return True
    haystack = f"{project_id} {manifest.get('title', '')}".lower()
    hidden_keywords = legacy._load_preferences(paths).get("hidden_keywords", [])
    keywords = {str(item).lower() for item in hidden_keywords} | {item.lower() for item in SENSITIVE_KEYWORDS}
    return any(keyword and keyword in haystack for keyword in keywords)


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or []
    return values[0] if values else ""
