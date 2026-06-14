from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any

APP_NAME = "CoursePackLocal"


def is_frozen() -> bool:
    """True when running from a PyInstaller/packaged executable."""
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Folder where the app code/executable lives."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    """Writable folder for uploads, converted courses, zips, and local data.

    In source/development mode, keep data beside the project so it is easy to inspect.
    In packaged mode, store data in the user's profile so no admin rights are needed.
    """
    override = os.environ.get("COURSEPACK_DATA_DIR")
    if override:
        root = Path(override).expanduser()
    elif not is_frozen():
        root = app_root() / "workspaces"
    else:
        system = platform.system().lower()
        if system == "windows":
            base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
            root = base / APP_NAME
        elif system == "darwin":
            root = Path.home() / "Library" / "Application Support" / APP_NAME
        else:
            root = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_root() -> Path:
    p = data_root() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def output_root() -> Path:
    p = data_root() / "outputs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def zip_root() -> Path:
    p = data_root() / "zips"
    p.mkdir(parents=True, exist_ok=True)
    return p


def workspace_root() -> Path:
    # Claude/MCP should see the converted course outputs folder.
    return output_root()


def source_python_path() -> Path:
    root = app_root()
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def mcp_command_and_args() -> tuple[str, list[str], dict[str, Any]]:
    """Return the command/args Claude Desktop should use.

    Source/dev mode: .venv Python runs mcp_server.py.
    Packaged mode: the CoursePack executable starts itself in --mcp mode.
    """
    workspace = str(workspace_root())
    if is_frozen():
        return str(Path(sys.executable).resolve()), ["--mcp", "--workspace", workspace], {
            "mode": "packaged",
            "executable": str(Path(sys.executable).resolve()),
            "workspace": workspace,
        }

    py = source_python_path()
    server = app_root() / "mcp_server.py"
    return str(py), [str(server), "--workspace", workspace], {
        "mode": "source",
        "python_path": str(py),
        "mcp_server_path": str(server),
        "workspace": workspace,
    }
