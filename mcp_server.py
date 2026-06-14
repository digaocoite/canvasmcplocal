from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from coursepack.search import course_summary, load_conversion_events, load_course_map, load_skipped_assets, read_text, search_course

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "The Python package 'mcp' is required for Claude Desktop integration. "
        "Install it with: pip install mcp\n\n" + str(exc)
    )


def latest_course_dir(workspace: Path) -> Path | None:
    if not workspace.exists():
        return None
    dirs = [p for p in workspace.iterdir() if p.is_dir() and (p / "course_index.md").exists()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def resolve_course(workspace: Path, course_name: str | None = None) -> Path:
    workspace = workspace.resolve()
    if course_name:
        candidate = (workspace / Path(course_name).name).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError:
            raise ValueError("Invalid course name")
        if not candidate.exists():
            raise FileNotFoundError(f"Course not found: {course_name}")
        return candidate
    latest = latest_course_dir(workspace)
    if latest is None:
        raise FileNotFoundError("No converted CoursePack courses were found yet. Convert a Canvas export in CoursePack Local first.")
    return latest


def safe_course_file(course_dir: Path, file_path: str) -> Path:
    target = (course_dir / file_path).resolve()
    try:
        target.relative_to(course_dir.resolve())
    except ValueError:
        raise ValueError("Invalid file path")
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    return target


def build_server(workspace: Path) -> FastMCP:
    mcp = FastMCP("CoursePack Local")

    @mcp.tool()
    def list_courses() -> list[dict[str, Any]]:
        """List converted CoursePack courses available on this computer."""
        if not workspace.exists():
            return []
        courses = []
        for p in sorted([d for d in workspace.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime, reverse=True):
            if not (p / "course_index.md").exists():
                continue
            s = course_summary(p)
            courses.append({"name": p.name, "path": str(p), **s})
        return courses

    @mcp.tool()
    def get_course_summary(course_name: str | None = None) -> dict[str, Any]:
        """Get a summary of a converted course. Defaults to the most recently converted course."""
        course = resolve_course(workspace, course_name)
        return course_summary(course)

    @mcp.tool()
    def get_course_index(course_name: str | None = None) -> str:
        """Read the Markdown course index. Defaults to the most recently converted course."""
        course = resolve_course(workspace, course_name)
        return read_text(course / "course_index.md", limit_chars=120000)

    @mcp.tool()
    def search_course_tool(query: str, course_name: str | None = None, max_results: int = 10) -> list[dict[str, Any]]:
        """Search converted course Markdown files for a phrase or keyword."""
        course = resolve_course(workspace, course_name)
        return search_course(course, query, max_results=max(1, min(max_results, 50)))

    @mcp.tool()
    def read_course_file(file_path: str, course_name: str | None = None, max_chars: int = 60000) -> str:
        """Read one converted Markdown/text file from a course by relative path, such as pages/welcome.md."""
        course = resolve_course(workspace, course_name)
        target = safe_course_file(course, file_path)
        return read_text(target, limit_chars=max(1000, min(max_chars, 200000)))

    @mcp.tool()
    def get_conversion_report(course_name: str | None = None) -> str:
        """Read the conversion report for a course."""
        course = resolve_course(workspace, course_name)
        return read_text(course / "conversion_report.md", limit_chars=120000)

    @mcp.tool()
    def get_skipped_assets(course_name: str | None = None) -> list[dict[str, Any]]:
        """List files skipped during conversion, including images, audio, video, large files, and unsupported files."""
        course = resolve_course(workspace, course_name)
        return load_skipped_assets(course)

    @mcp.tool()
    def get_conversion_events(course_name: str | None = None) -> list[dict[str, Any]]:
        """List conversion warnings and errors. Item-level failures are logged here instead of stopping the whole conversion."""
        course = resolve_course(workspace, course_name)
        return load_conversion_events(course)

    @mcp.tool()
    def get_course_map(course_name: str | None = None) -> dict[str, Any]:
        """Return structured course metadata including modules, converted items, and output paths."""
        course = resolve_course(workspace, course_name)
        return load_course_map(course)

    return mcp


def main() -> int:
    parser = argparse.ArgumentParser(description="CoursePack Local MCP server for Claude Desktop.")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parent / "workspaces" / "outputs"), help="Folder containing converted CoursePack outputs")
    args = parser.parse_args()
    workspace = Path(args.workspace)
    server = build_server(workspace)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
