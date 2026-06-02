"""``reachy-mini-mcp doctor`` — diagnose the install and runtime environment.

Read-only health check: Python version, package + bundled tools, the optional
``[server]``/``[tts]`` stacks, daemon reachability, and which clients already have
the server registered. Exits non-zero only on **hard** failures (a broken
install); a stopped daemon or a missing optional extra is a warning.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from reachy_mini_mcp import __version__
from reachy_mini_mcp.cli import _clients, _mcp
from reachy_mini_mcp.cli._errors import EXIT_ENV_ERROR
from reachy_mini_mcp.cli._meta import count_tools, daemon_status, tools_dir
from reachy_mini_mcp.cli._output import emit_result

_OK, _WARN, _FAIL = "ok", "warn", "fail"
_MARK = {_OK: "✓", _WARN: "•", _FAIL: "✗"}


@dataclass
class Check:
    name: str
    status: str
    detail: str
    hard: bool = False  # a failing hard check sets a non-zero exit code


def _python_check() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 10)
    return Check(
        "python",
        _OK if ok else _FAIL,
        f"{v.major}.{v.minor}.{v.micro}" + ("" if ok else " (need >= 3.10)"),
        hard=True,
    )


def _tools_check() -> Check:
    td = tools_dir()
    if not (td / "tools_index.json").exists():
        return Check("tools", _FAIL, f"tools_index.json missing under {td}", hard=True)
    enabled, total = count_tools()
    return Check("tools", _OK, f"{enabled} enabled / {total} total in {td}")


def _import_check(label: str, modules: List[str], extra: str) -> Check:
    missing = []
    for mod in modules:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if not missing:
        return Check(label, _OK, "installed")
    return Check(
        label,
        _WARN,
        f"missing {', '.join(missing)} — install with: pip install \"reachy-mini-mcp[{extra}]\"",
    )


def _binaries_check() -> Check:
    found = {b: shutil.which(b) for b in ("piper", "aplay")}
    have = [b for b, p in found.items() if p]
    if len(have) == 2:
        return Check("tts-binaries", _OK, "piper and aplay on PATH")
    missing = [b for b, p in found.items() if not p]
    return Check("tts-binaries", _WARN, f"not found: {', '.join(missing)} (speech disabled)")


def _daemon_check(base_url: str) -> Check:
    reachable, detail = daemon_status(base_url)
    return Check(
        "daemon",
        _OK if reachable else _WARN,
        f"{base_url} — {'reachable' if reachable else 'unreachable'} ({detail})",
    )


def _env_check() -> Check:
    found = [k for k in ("REACHY_BASE_URL", "PIPER_MODEL", "AUDIO_DEVICE") if os.environ.get(k)]
    dotenv = Path.cwd() / ".env"
    parts = []
    if found:
        parts.append("set: " + ", ".join(found))
    if dotenv.exists():
        parts.append(f".env present ({dotenv})")
    return Check("env", _OK, "; ".join(parts) if parts else "no robot env vars set (using defaults)")


def _install_check() -> Check:
    name = _mcp.DEFAULT_NAME
    targets = [
        _clients.resolve_target(client="claude-code", scope="project"),
        _clients.resolve_target(client="claude-code", scope="user"),
        _clients.resolve_target(client="claude-desktop"),
        _clients.resolve_target(client="cursor", scope="project"),
        _clients.resolve_target(client="cursor", scope="user"),
    ]
    installed = [t.label for t in targets if _clients.is_installed(t.path, name=name)]
    if installed:
        return Check("installed-in", _OK, "; ".join(installed))
    return Check(
        "installed-in",
        _WARN,
        "not registered in any known client — run `reachy-mini-mcp install`",
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "doctor",
        help="Diagnose the install, dependencies, daemon, and client registration.",
        description="Read-only health check; non-zero exit only on a broken install.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Daemon URL to probe "
        f"(default: $REACHY_BASE_URL or {_mcp.DEFAULT_BASE_URL}).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.set_defaults(func=_handle)


def run_checks(base_url: Optional[str] = None) -> List[Check]:
    url = base_url or os.environ.get("REACHY_BASE_URL", _mcp.DEFAULT_BASE_URL)
    return [
        Check("package", _OK, f"reachy-mini-mcp {__version__}"),
        _python_check(),
        _tools_check(),
        _import_check("server-extra", ["fastmcp", "httpx", "mcp"], "server"),
        _import_check("tts-extra", ["piper", "pyaudio"], "tts"),
        _binaries_check(),
        _daemon_check(url),
        _env_check(),
        _install_check(),
    ]


def _handle(args: argparse.Namespace) -> int:
    checks = run_checks(args.base_url)
    failed = any(c.status == _FAIL and c.hard for c in checks)

    if args.json:
        emit_result(json.dumps({"ok": not failed, "checks": [asdict(c) for c in checks]}, indent=2))
    else:
        lines = ["reachy-mini-mcp doctor", ""]
        for c in checks:
            lines.append(f"  {_MARK[c.status]} {c.name}: {c.detail}")
        lines.append("")
        lines.append("OK" if not failed else "FAILED — fix the ✗ checks above")
        emit_result("\n".join(lines))

    return EXIT_ENV_ERROR if failed else 0
