"""Reject internal task residue from public-facing repository documents."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = sorted(
    {
        ROOT / "README.md",
        ROOT / "pyproject.toml",
        ROOT / "CONTRIBUTING.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "frontend" / "src").glob("*.*")),
        *sorted((ROOT / "taskstate_vault" / "ui").glob("*.py")),
    }
)
FORBIDDEN = {
    "local Windows project path": re.compile(r"[A-Za-z]:[\\/](?:myproject|Users)[\\/]"),
    "local Unix home path": re.compile(r"/home/[A-Za-z0-9._-]+/"),
    "internal release decisions": re.compile(r"Repository And Release Decisions", re.I),
    "provider budget instructions": re.compile(r"(remaining provider budget|budget guidance)", re.I),
    "known weak UI password": re.compile(r"\b12345678\b"),
    "OpenAI-style secret": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main() -> None:
    findings: list[str] = []
    for path in PUBLIC_FILES:
        text = path.read_text(encoding="utf-8-sig")
        if path.name == "README.md" and text.count("\n") < 20:
            findings.append(f"{path.relative_to(ROOT)}: README appears collapsed")
        for label, pattern in FORBIDDEN.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    if findings:
        raise SystemExit("Public-boundary check failed:\n" + "\n".join(findings))


if __name__ == "__main__":
    main()
