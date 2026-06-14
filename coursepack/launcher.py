from __future__ import annotations

import argparse
import sys
import threading
import urllib.request
import webbrowser

import uvicorn

from .runtime import data_root, is_frozen, output_root, upload_root, zip_root


def open_browser(port: int = 3333) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}")


def server_is_running(port: int = 3333) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def start_web(*, no_browser: bool = False, port: int = 3333) -> int:
    # Create writable folders early, especially in packaged/no-admin mode.
    data_root(); upload_root(); output_root(); zip_root()

    # If the app is already running, do not crash with a port-in-use error.
    # Just open the browser and exit cleanly. This makes repeated desktop-shortcut clicks safe.
    if server_is_running(port):
        print("CoursePack Local is already running.")
        print(f"Opening http://127.0.0.1:{port}")
        if not no_browser:
            open_browser(port)
        return 0

    if not no_browser:
        threading.Timer(1.0, lambda: open_browser(port)).start()
    print("CoursePack Local is starting...")
    print("Open this address if the browser does not open automatically:")
    print(f"http://127.0.0.1:{port}")
    print(f"Data folder: {data_root()}")
    uvicorn.run("coursepack.webapp:app", host="127.0.0.1", port=port, reload=False)
    return 0


def start_mcp(argv: list[str]) -> int:
    # Import only when needed so normal web startup stays light.
    import mcp_server
    sys.argv = ["mcp_server.py", *argv]
    return int(mcp_server.main())


def print_jsonish(label: str, data: dict) -> None:
    import json
    print(label)
    print("=" * len(label))
    print(json.dumps(data, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="CoursePack Local")
    parser.add_argument("--mcp", action="store_true", help="Start the CoursePack read-only MCP server for Claude Desktop")
    parser.add_argument("--workspace", help="Converted CoursePack output folder for MCP mode")
    parser.add_argument("--connect-claude", action="store_true", help="Update Claude Desktop config to use CoursePack MCP")
    parser.add_argument("--claude-status", action="store_true", help="Print Claude Desktop CoursePack connection status")
    parser.add_argument("--no-browser", action="store_true", help="Start the local web server without opening the browser")
    parser.add_argument("--port", type=int, default=3333, help="Local web server port")
    args, unknown = parser.parse_known_args()

    if args.mcp:
        mcp_args: list[str] = []
        if args.workspace:
            mcp_args.extend(["--workspace", args.workspace])
        mcp_args.extend(unknown)
        return start_mcp(mcp_args)

    if args.connect_claude:
        from .claude_config import connect_to_claude
        result = connect_to_claude(force=True)
        print_jsonish("CoursePack Claude Desktop connection", result)
        if result.get("ok"):
            print("\nDone. Fully quit and reopen Claude Desktop before checking for CoursePack tools.")
            return 0
        print("\nCoursePack could not connect to Claude Desktop. Read the message above.")
        return 1

    if args.claude_status:
        from .claude_config import status
        print_jsonish("CoursePack Claude Desktop status", status())
        return 0

    return start_web(no_browser=args.no_browser, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
