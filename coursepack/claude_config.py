from __future__ import annotations

import json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import is_frozen, mcp_command_and_args


def claude_config_path() -> Path:
    system = platform.system().lower()
    if system == "windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def likely_claude_installed() -> bool:
    system = platform.system().lower()
    candidates: list[Path] = [claude_config_path().parent]
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
        candidates.extend([Path.home() / ".local" / "share" / "applications" / "claude.desktop"])
    return any(p.exists() for p in candidates)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.read_text(encoding="utf-8", errors="replace").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def desired_coursepack_config() -> tuple[dict[str, Any], dict[str, Any]]:
    command, args, meta = mcp_command_and_args()
    return {"command": command, "args": args}, meta


def connect_to_claude(*, force: bool = False) -> dict[str, Any]:
    """Register CoursePack as a local Claude Desktop MCP server.

    Idempotent: repeated clicks should not create unnecessary backup chains or duplicate entries.
    """
    config_path = claude_config_path()
    detected = likely_claude_installed()
    if not detected and not force:
        return {
            "ok": False,
            "status": "not_detected",
            "message": "Claude Desktop was not detected. CoursePack Local still works in the browser. Install Claude Desktop and run this again.",
            "config_path": str(config_path),
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

    # In source mode, also make sure mcp_server.py exists. In packaged mode, the exe starts --mcp itself.
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

    config_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    data: dict[str, Any] = {}

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
                "message": "Claude Desktop's config file exists but is not valid JSON. CoursePack made a backup and did not overwrite it automatically.",
                "config_path": str(config_path),
                "backup_path": str(backup_path),
                "error": str(exc),
                "restart_required": False,
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
            "message": "CoursePack is already configured in Claude Desktop. Fully quit and reopen Claude Desktop if the tools are not visible yet.",
            "config_path": str(config_path),
            "backup_path": None,
            "detected_claude": detected,
            "restart_required": True,
            "next_step": "Fully quit and reopen Claude Desktop.",
            "mode": meta.get("mode"),
            "workspace": meta.get("workspace"),
        }

    if config_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = config_path.with_name(config_path.name + f".backup-{stamp}")
        shutil.copy2(config_path, backup_path)

    servers["coursepack"] = desired
    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    action = "updated" if previous else "connected"
    detection_note = "" if detected else " Claude Desktop was not detected, but the config was prepared for when it is installed."
    return {
        "ok": True,
        "status": action,
        "message": f"CoursePack was {action} in Claude Desktop's MCP config.{detection_note} Fully quit and reopen Claude Desktop to see the CoursePack tools.",
        "config_path": str(config_path),
        "backup_path": str(backup_path) if backup_path else None,
        "detected_claude": detected,
        "restart_required": True,
        "next_step": "Fully quit and reopen Claude Desktop.",
        "mode": meta.get("mode"),
        "workspace": meta.get("workspace"),
    }


def status() -> dict[str, Any]:
    config_path = claude_config_path()
    configured = False
    error = None
    coursepack_entry = None
    if config_path.exists():
        try:
            data = read_json(config_path)
            servers = data.get("mcpServers") if isinstance(data, dict) else None
            if isinstance(servers, dict):
                coursepack_entry = servers.get("coursepack")
                configured = "coursepack" in servers
        except Exception as exc:
            error = str(exc)

    desired, meta = desired_coursepack_config()
    command_found = Path(desired["command"]).exists()
    return {
        "detected_claude": likely_claude_installed(),
        "configured": configured,
        "ready_for_claude": bool(configured and command_found and not error),
        "config_path": str(config_path),
        "mode": meta.get("mode"),
        "packaged_app": is_frozen(),
        "command_found": command_found,
        "desired_command": desired["command"],
        "desired_args": " ".join(desired.get("args", [])),
        "workspace": str(meta.get("workspace")),
        "configured_command": coursepack_entry.get("command") if isinstance(coursepack_entry, dict) else None,
        "error": error,
    }
