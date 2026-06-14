from __future__ import annotations

import json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import is_frozen, mcp_command_and_args


def _standalone_config_path() -> Path:
    system = platform.system().lower()
    if system == "windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _windows_store_config_paths() -> list[Path]:
    """Microsoft Store Claude uses a separate config under Packages/Claude_*/LocalCache/Roaming/Claude/."""
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    packages = local / "Packages"
    if not packages.exists():
        return []

    paths: list[Path] = []
    for pkg_dir in sorted(packages.glob("Claude_*")):
        if not pkg_dir.is_dir():
            continue
        paths.append(pkg_dir / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json")
    return paths


def claude_config_paths() -> list[Path]:
    """All known Claude Desktop config file locations for this OS/user."""
    system = platform.system().lower()
    if system == "windows":
        candidates = [_standalone_config_path(), *_windows_store_config_paths()]
    else:
        candidates = [_standalone_config_path()]

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def claude_config_path() -> Path:
    """Primary/legacy config path (standalone install)."""
    return _standalone_config_path()


def _store_package_root(config_path: Path) -> Path | None:
    for parent in config_path.parents:
        if parent.parent.name == "Packages" and parent.name.startswith("Claude_"):
            return parent
    return None


def _config_path_is_relevant(config_path: Path) -> bool:
    if config_path.exists():
        return True
    if config_path.parent.exists():
        return True
    pkg_root = _store_package_root(config_path)
    return bool(pkg_root and pkg_root.exists())


def relevant_claude_config_paths(*, force: bool = False) -> list[Path]:
    """Config files CoursePack should update for this machine."""
    paths = [p for p in claude_config_paths() if _config_path_is_relevant(p)]
    if paths:
        return paths
    if force:
        return claude_config_paths()[:1]
    return []


def likely_claude_installed() -> bool:
    system = platform.system().lower()
    candidates: list[Path] = []

    for config_path in claude_config_paths():
        candidates.append(config_path)
        candidates.append(config_path.parent)
        pkg_root = _store_package_root(config_path)
        if pkg_root:
            candidates.append(pkg_root)

    if system == "windows":
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        program_files = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
        ]
        candidates.extend([
            local / "Programs" / "Claude" / "Claude.exe",
            local / "AnthropicClaude" / "Claude.exe",
            *(p / "Claude" / "Claude.exe" for p in program_files),
        ])
    elif system == "darwin":
        candidates.extend([Path("/Applications/Claude.app"), Path.home() / "Applications" / "Claude.app"])
    else:
        candidates.append(Path.home() / ".local" / "share" / "applications" / "claude.desktop")

    return any(p.exists() for p in candidates)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.read_text(encoding="utf-8", errors="replace").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def desired_coursepack_config() -> tuple[dict[str, Any], dict[str, Any]]:
    command, args, meta = mcp_command_and_args()
    return {"command": command, "args": args}, meta


def _config_kind(config_path: Path) -> str:
    if _store_package_root(config_path):
        return "microsoft_store"
    return "standalone"


def _update_single_config(config_path: Path, desired: dict[str, Any]) -> dict[str, Any]:
    backup_path = None
    data: dict[str, Any] = {}

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "ok": False,
            "status": "mkdir_failed",
            "config_path": str(config_path),
            "config_kind": _config_kind(config_path),
            "message": f"Could not create config folder: {exc}",
        }

    if config_path.exists():
        try:
            data = read_json(config_path)
        except Exception as exc:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = config_path.with_name(config_path.name + f".invalid-backup-{stamp}")
            shutil.copy2(config_path, backup_path)
            return {
                "ok": False,
                "status": "invalid_claude_config",
                "message": "Claude config exists but is not valid JSON. A backup was created and this file was not overwritten.",
                "config_path": str(config_path),
                "config_kind": _config_kind(config_path),
                "backup_path": str(backup_path),
                "error": str(exc),
            }

    if not isinstance(data, dict):
        data = {}

    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers

    previous = servers.get("coursepack")
    if previous == desired:
        return {
            "ok": True,
            "status": "already_connected",
            "config_path": str(config_path),
            "config_kind": _config_kind(config_path),
            "backup_path": None,
            "changed": False,
        }

    if config_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = config_path.with_name(config_path.name + f".backup-{stamp}")
        shutil.copy2(config_path, backup_path)

    servers["coursepack"] = desired
    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    action = "updated" if previous else "connected"
    return {
        "ok": True,
        "status": action,
        "config_path": str(config_path),
        "config_kind": _config_kind(config_path),
        "backup_path": str(backup_path) if backup_path else None,
        "changed": True,
    }


def connect_to_claude(*, force: bool = False) -> dict[str, Any]:
    """Register CoursePack in every relevant Claude Desktop config file.

    On Windows, standalone and Microsoft Store Claude use different config paths.
    CoursePack writes to all relevant locations so the active Claude install can see MCP tools.
    """
    detected = likely_claude_installed()
    target_paths = relevant_claude_config_paths(force=force)
    primary_path = claude_config_path()

    if not target_paths and not detected and not force:
        return {
            "ok": False,
            "status": "not_detected",
            "message": "Claude Desktop was not detected. CoursePack Local still works in the browser. Install Claude Desktop and run this again.",
            "config_path": str(primary_path),
            "config_paths": [str(p) for p in claude_config_paths()],
            "restart_required": False,
        }

    desired, meta = desired_coursepack_config()
    command_path = Path(desired["command"])
    if not command_path.exists():
        return {
            "ok": False,
            "status": "missing_command",
            "message": "CoursePack could not find the command Claude needs to start the MCP server.",
            "command": str(command_path),
            "mode": meta.get("mode"),
            "restart_required": False,
        }

    if meta.get("mode") == "source":
        server = Path(str(meta.get("mcp_server_path", "")))
        if not server.exists():
            return {
                "ok": False,
                "status": "missing_mcp_server",
                "message": "CoursePack MCP server file was not found.",
                "mcp_server_path": str(server),
                "restart_required": False,
            }

    if not target_paths:
        target_paths = [primary_path]

    per_path: list[dict[str, Any]] = []
    for config_path in target_paths:
        per_path.append(_update_single_config(config_path, desired))

    successes = [r for r in per_path if r.get("ok")]
    failures = [r for r in per_path if not r.get("ok")]
    changed = [r for r in successes if r.get("changed")]
    already = [r for r in successes if r.get("status") == "already_connected"]

    if failures and not successes:
        first = failures[0]
        return {
            "ok": False,
            "status": first.get("status", "connect_failed"),
            "message": first.get("message", "Could not update Claude Desktop config."),
            "config_path": first.get("config_path", str(primary_path)),
            "config_paths": [str(p) for p in target_paths],
            "per_path": per_path,
            "restart_required": False,
        }

    store_updated = any(r.get("config_kind") == "microsoft_store" and r.get("ok") for r in per_path)
    standalone_updated = any(r.get("config_kind") == "standalone" and r.get("ok") for r in per_path)

    if changed:
        action = "connected"
        if len(changed) > 1:
            msg = (
                f"CoursePack was added to {len(changed)} Claude Desktop config file(s). "
                "Windows may have separate configs for standalone vs Microsoft Store Claude — both were updated when found."
            )
        else:
            kind = changed[0].get("config_kind", "standalone")
            msg = f"CoursePack was connected in the {kind.replace('_', ' ')} Claude Desktop config."
    elif already and len(already) == len(successes):
        action = "already_connected"
        msg = (
            "CoursePack is already configured in all relevant Claude Desktop config files. "
            "If tools are still missing, fully quit Claude from the system tray and reopen it."
        )
    else:
        action = "updated"
        msg = "CoursePack Claude configuration is in place."

    if store_updated and not standalone_updated:
        msg += " Microsoft Store Claude config was updated — that is usually the active one on Windows."
    elif standalone_updated and store_updated:
        msg += " Both standalone and Microsoft Store Claude configs were updated."

    msg += " Fully quit Claude Desktop from the system tray (Quit, not just close the window), then reopen Claude."

    return {
        "ok": True,
        "status": action,
        "message": msg,
        "config_path": str(primary_path),
        "config_paths": [r.get("config_path") for r in per_path if r.get("config_path")],
        "updated_paths": [r.get("config_path") for r in changed],
        "per_path": per_path,
        "backup_paths": [r.get("backup_path") for r in per_path if r.get("backup_path")],
        "detected_claude": detected,
        "restart_required": True,
        "next_step": "Right-click the Claude icon in the system tray and choose Quit, then reopen Claude from the Start Menu.",
        "mode": meta.get("mode"),
        "workspace": meta.get("workspace"),
        "mcp_log_hint_windows_store": _windows_store_mcp_log_hint(),
    }


def _windows_store_mcp_log_hint() -> str | None:
    for config_path in _windows_store_config_paths():
        pkg_root = _store_package_root(config_path)
        if not pkg_root:
            continue
        log_path = pkg_root / "LocalCache" / "Roaming" / "Claude" / "logs" / "mcp.log"
        if log_path.parent.exists():
            return str(log_path)
    return None


def status() -> dict[str, Any]:
    desired, meta = desired_coursepack_config()
    command_found = Path(desired["command"]).exists()

    per_path: list[dict[str, Any]] = []
    any_configured = False
    all_relevant_configured = True

    for config_path in claude_config_paths():
        relevant = _config_path_is_relevant(config_path)
        entry = {
            "config_path": str(config_path),
            "config_kind": _config_kind(config_path),
            "exists": config_path.exists(),
            "relevant": relevant,
            "configured": False,
            "matches_desired": False,
            "error": None,
        }
        if config_path.exists():
            try:
                data = read_json(config_path)
                servers = data.get("mcpServers") if isinstance(data, dict) else None
                if isinstance(servers, dict) and "coursepack" in servers:
                    entry["configured"] = True
                    entry["matches_desired"] = servers.get("coursepack") == desired
                    any_configured = True
            except Exception as exc:
                entry["error"] = str(exc)
        if relevant and not entry["configured"]:
            all_relevant_configured = False
        per_path.append(entry)

    relevant_paths = [p for p in per_path if p.get("relevant")]
    ready = bool(
        command_found
        and relevant_paths
        and all(p.get("configured") and p.get("matches_desired") for p in relevant_paths)
    )

    return {
        "detected_claude": likely_claude_installed(),
        "configured": any_configured,
        "ready_for_claude": ready,
        "config_path": str(claude_config_path()),
        "config_paths": [p["config_path"] for p in per_path],
        "per_path": per_path,
        "mode": meta.get("mode"),
        "packaged_app": is_frozen(),
        "command_found": command_found,
        "desired_command": desired["command"],
        "desired_args": " ".join(desired.get("args", [])),
        "workspace": str(meta.get("workspace")),
        "mcp_log_hint_windows_store": _windows_store_mcp_log_hint(),
        "next_step": "Fully quit Claude from the system tray, then reopen Claude. On Windows, Microsoft Store Claude uses a different config file than a standalone install.",
    }
