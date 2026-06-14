from __future__ import annotations

import json

from .claude_config import connect_to_claude, status


def main() -> int:
    print("CoursePack is starting the Claude Desktop connection process...")
    print()
    print("Current Claude/CoursePack status:")
    print(json.dumps(status(), indent=2))
    print()
    print("Updating Claude Desktop MCP configuration...")
    result = connect_to_claude(force=True)
    print(json.dumps(result, indent=2))
    print()
    if result.get("ok"):
        print("Done. Fully quit and reopen Claude Desktop to see CoursePack tools.")
        return 0
    print(result.get("message", "CoursePack could not be connected to Claude Desktop."))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
