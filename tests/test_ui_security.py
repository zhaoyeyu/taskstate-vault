from __future__ import annotations

import http.client
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from taskstate_vault.core.io import read_json, write_json, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.kernel.init import init_workspace
from taskstate_vault.ui.app_server import ApiError, _handler_factory, build_bootstrap, safe_file_path, serve_ui
from taskstate_vault.ui.server import (
    PASSWORD_ITERATIONS,
    PASSWORD_SCHEME,
    _accounts_path,
    _ensure_ui_state,
    _legacy_hash_password,
    _verify_account,
    initialize_admin_account,
    reset_admin_password,
)


class UiSecurityTests(unittest.TestCase):
    def test_admin_password_is_generated_hashed_and_resettable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_workspace(root)
            paths = TaskStateVaultPaths(root)

            password = initialize_admin_account(paths)

            self.assertIsNotNone(password)
            self.assertGreaterEqual(len(str(password)), 12)
            self.assertTrue(_verify_account(paths, "admin", str(password)))
            self.assertFalse(_verify_account(paths, "admin", "incorrect-password"))
            self.assertIsNone(initialize_admin_account(paths))

            account = read_json(_accounts_path(paths))["users"]["admin"]
            self.assertEqual(account["password_scheme"], PASSWORD_SCHEME)
            self.assertEqual(account["password_iterations"], PASSWORD_ITERATIONS)
            self.assertNotIn(str(password), json.dumps(account))

            replacement = reset_admin_password(paths)
            self.assertNotEqual(password, replacement)
            self.assertFalse(_verify_account(paths, "admin", str(password)))
            self.assertTrue(_verify_account(paths, "admin", replacement))

    def test_legacy_password_hash_is_upgraded_after_successful_login(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_workspace(root)
            paths = TaskStateVaultPaths(root)
            _ensure_ui_state(paths)
            password = "legacy-password-for-migration"
            salt = "legacy-salt"
            write_json(
                _accounts_path(paths),
                {
                    "schema_version": 1,
                    "users": {
                        "admin": {
                            "username": "admin",
                            "role": "administrator",
                            "password_salt": salt,
                            "password_hash": _legacy_hash_password(password, salt),
                        }
                    },
                },
            )

            self.assertTrue(_verify_account(paths, "admin", password))

            migrated = read_json(_accounts_path(paths))["users"]["admin"]
            self.assertEqual(migrated["password_scheme"], PASSWORD_SCHEME)
            self.assertEqual(migrated["password_iterations"], PASSWORD_ITERATIONS)

    def test_file_editor_is_confined_to_taskstate_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_workspace(root)
            paths = TaskStateVaultPaths(root)
            allowed = paths.os_dir / "safe.md"
            outside = root / "workspace-secret.txt"
            write_text(allowed, "safe")
            write_text(outside, "outside")

            self.assertEqual(safe_file_path(paths, str(allowed)), allowed.resolve())
            with self.assertRaises(ApiError):
                safe_file_path(paths, str(outside))

    def test_logged_out_bootstrap_does_not_disclose_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_workspace(root)
            paths = TaskStateVaultPaths(root)

            payload = build_bootstrap(
                paths,
                {"loggedIn": False, "username": None, "advanced": False, "lang": "en"},
            )

            self.assertEqual(payload["overview"]["root"], "")
            self.assertEqual(payload["overview"]["projectCount"], 0)
            self.assertEqual(payload["projects"]["projects"], [])

    def test_http_api_requires_login_and_sets_hardened_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init_workspace(root)
            paths = TaskStateVaultPaths(root)
            password = initialize_admin_account(paths)
            server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_factory(paths))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = int(server.server_address[1])
                status, _, body = _request(port, "GET", "/api/projects")
                self.assertEqual(status, 401)
                self.assertEqual(body["error"]["code"], "login_required")

                status, _, body = _request(port, "GET", "/api/bootstrap")
                self.assertEqual(status, 200)
                self.assertEqual(body["data"]["overview"]["root"], "")

                status, _, body = _request(
                    port,
                    "POST",
                    "/api/session/login",
                    {"username": "admin", "password": password},
                    origin="https://untrusted.example",
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "invalid_origin")

                status, headers, body = _request(
                    port,
                    "POST",
                    "/api/session/login",
                    {"username": "admin", "password": password},
                )
                self.assertEqual(status, 200)
                self.assertTrue(body["data"]["loggedIn"])
                set_cookie = headers["set-cookie"]
                self.assertIn("HttpOnly", set_cookie)
                self.assertIn("SameSite=Strict", set_cookie)

                cookie = set_cookie.split(";", 1)[0]
                status, _, body = _request(port, "GET", "/api/projects", cookie=cookie)
                self.assertEqual(status, 200)
                self.assertIn("projects", body["data"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_network_bind_requires_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = TaskStateVaultPaths(Path(temp))
            with self.assertRaises(ValueError):
                serve_ui(paths, "0.0.0.0", 8765)


def _request(
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    *,
    cookie: str | None = None,
    origin: str | None = None,
) -> tuple[int, dict[str, str], dict[str, object]]:
    raw = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if raw is not None:
        headers["Content-Length"] = str(len(raw))
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, body=raw, headers=headers)
        response = connection.getresponse()
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        body = json.loads(response.read().decode("utf-8"))
        return response.status, response_headers, body
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
