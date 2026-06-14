from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "CoursePack Local"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    # Clean old build output so the resulting folder is predictable.
    for p in [DIST / APP_NAME, BUILD / APP_NAME]:
        if p.exists():
            shutil.rmtree(p)

    # PyInstaller does not cross-compile. Run this script on Windows to produce the Windows no-admin build.
    sep = ";" if os.name == "nt" else ":"
    add_data = [
        f"README.md{sep}.",
        f"requirements.txt{sep}.",
        f"requirements-mcp.txt{sep}.",
        f"requirements-docs.txt{sep}.",
        f"uninstall.ps1{sep}.",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        APP_NAME,
        "--hidden-import",
        "mcp_server",
        "--hidden-import",
        "coursepack.launcher",
        "--hidden-import",
        "coursepack.webapp",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--collect-all",
        "mcp",
    ]
    for entry in add_data:
        cmd.extend(["--add-data", entry])
    cmd.append("portable_launcher.py")
    run(cmd)

    app_dir = DIST / APP_NAME
    exe_name = f"{APP_NAME}.exe" if os.name == "nt" else APP_NAME

    if os.name == "nt":
        (app_dir / "Start CoursePack Local.bat").write_text(
            '@echo off\r\n'
            'cd /d "%~dp0"\r\n'
            'echo Starting CoursePack Local...\r\n'
            'echo Leave this window open while using CoursePack.\r\n'
            'echo.\r\n'
            f'"%~dp0{exe_name}"\r\n'
            'pause\r\n',
            encoding="utf-8",
        )
        (app_dir / "Connect CoursePack to Claude.bat").write_text(
            '@echo off\r\n'
            'cd /d "%~dp0"\r\n'
            'echo Connecting CoursePack to Claude Desktop...\r\n'
            'echo.\r\n'
            f'"%~dp0{exe_name}" --connect-claude\r\n'
            'pause\r\n',
            encoding="utf-8",
        )
        (app_dir / "Check Claude Connection.bat").write_text(
            '@echo off\r\n'
            'cd /d "%~dp0"\r\n'
            f'"%~dp0{exe_name}" --claude-status\r\n'
            'pause\r\n',
            encoding="utf-8",
        )
        (app_dir / "Uninstall CoursePack Local.bat").write_text(
            '@echo off\r\n'
            'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"\r\n'
            'pause\r\n',
            encoding="utf-8",
        )
    else:
        for name, args in {
            "start-coursepack.sh": "",
            "connect-claude.sh": "--connect-claude",
            "check-claude.sh": "--claude-status",
        }.items():
            path = app_dir / name
            path.write_text(f'#!/usr/bin/env bash\ncd "$(dirname "$0")"\n./"{exe_name}" {args}\n', encoding="utf-8")
            path.chmod(0o755)

    release_zip = ROOT / f"coursepack-local-portable-{sys.platform}.zip"
    if release_zip.exists():
        release_zip.unlink()
    shutil.make_archive(str(release_zip.with_suffix("")), "zip", app_dir)
    print("\nPortable build complete.")
    print(f"Folder: {app_dir}")
    print(f"ZIP:    {release_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
