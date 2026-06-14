from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from coursepack.claude_config import status as claude_status

checks = []
root = Path(__file__).resolve().parent

def add(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": ok, "detail": detail})

add("Python version 3.10+", sys.version_info >= (3, 10), sys.version.split()[0])
for module in ["fastapi", "uvicorn", "bs4", "markdownify", "multipart"]:
    add(f"Python package: {module}", importlib.util.find_spec(module) is not None)
add("Converter file", (root / "coursepack" / "converter.py").exists(), str(root / "coursepack" / "converter.py"))
add("Web app file", (root / "coursepack" / "webapp.py").exists(), str(root / "coursepack" / "webapp.py"))
add("MCP server file", (root / "mcp_server.py").exists(), str(root / "mcp_server.py"))
add("Claude status readable", True, json.dumps(claude_status(), indent=2))

print("CoursePack Local install check")
print("==============================")
for c in checks:
    mark = "OK" if c["ok"] else "NEEDS ATTENTION"
    print(f"[{mark}] {c['name']}")
    if c["detail"]:
        print(f"  {c['detail']}")

failed = [c for c in checks if not c["ok"]]
if failed:
    print("\nSome checks need attention. Run Start CoursePack Local.bat first, then run this check again.")
    raise SystemExit(1)
print("\nAll required checks passed.")
