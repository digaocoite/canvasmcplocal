from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .search import iter_markdown_files, load_course_map, load_skipped_assets, read_text, search_course

POLICY_GROUPS: dict[str, list[str]] = {
    "AI / generative AI": ["ai", "artificial intelligence", "generative ai", "chatgpt", "claude", "gemini", "copilot"],
    "Late work / deadlines": ["late", "deadline", "due date", "extension", "makeup", "make-up", "missing work"],
    "Attendance / participation": ["attendance", "absent", "participation", "participate", "presence"],
    "Academic integrity": ["academic integrity", "plagiarism", "cheating", "honor code", "citation", "cite"],
    "Accessibility / accommodations": ["accessibility", "accommodation", "disability", "ada", "accessible", "caption", "alt text"],
    "Grading / rubrics": ["grade", "grading", "rubric", "points", "percent", "percentage", "assessment"],
}

DATE_PATTERNS = [
    # 01/31/2024, 1-31-24, etc.
    re.compile(r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:20\d{2}|\d{2})\b"),
    # January 31, 2024
    re.compile(r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+(?:20\d{2})\b", re.I),
    # Fall 2024, Spring 2025, Summer 2023, etc.
    re.compile(r"\b(?:Spring|Summer|Fall|Autumn|Winter)\s+(?:20\d{2})\b", re.I),
    # standalone years likely to matter in course pages
    re.compile(r"\b20(?:1\d|2[0-6])\b"),
]

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RAW_URL_PATTERN = re.compile(r"(?<!\()\bhttps?://[^\s)<>\]]+", re.I)


@dataclass
class DateFinding:
    path: str
    title: str
    match: str
    context: str


@dataclass
class LinkFinding:
    path: str
    label: str
    target: str
    status: str
    note: str


@dataclass
class WorkloadModule:
    position: int | str
    title: str
    converted_items: int
    words: int
    chars: int
    estimated_reading_minutes: int


def _title_from_text(path: Path, text: str) -> str:
    for line in text.splitlines()[:40]:
        if line.startswith("# "):
            return line[2:].strip()
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip().strip('"')
    return path.stem.replace("-", " ").title()


def _context(text: str, start: int, end: int, radius: int = 120) -> str:
    s = max(0, start - radius)
    e = min(len(text), end + radius)
    snippet = text[s:e].replace("\r", " ").replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if s > 0:
        snippet = "…" + snippet
    if e < len(text):
        snippet += "…"
    return snippet


def _word_count(text: str) -> int:
    # Ignore frontmatter-ish metadata and count normal tokens.
    return len(re.findall(r"\b[\w'-]{2,}\b", text))


def find_dates(course_dir: str | Path, *, max_items: int = 200) -> list[dict[str, Any]]:
    root = Path(course_dir)
    findings: list[DateFinding] = []
    for path in iter_markdown_files(root):
        try:
            text = read_text(path)
        except Exception:
            continue
        rel = path.relative_to(root).as_posix()
        title = _title_from_text(path, text)
        seen: set[tuple[str, int]] = set()
        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(text):
                key = (match.group(0), match.start())
                if key in seen:
                    continue
                seen.add(key)
                findings.append(DateFinding(rel, title, match.group(0), _context(text, match.start(), match.end())))
                if len(findings) >= max_items:
                    return [asdict(f) for f in findings]
    return [asdict(f) for f in findings]


def find_links(course_dir: str | Path, *, max_items: int = 300) -> list[dict[str, Any]]:
    root = Path(course_dir)
    findings: list[LinkFinding] = []
    for path in iter_markdown_files(root):
        try:
            text = read_text(path)
        except Exception:
            continue
        rel = path.relative_to(root).as_posix()
        seen_targets: set[str] = set()
        for label, target in LINK_PATTERN.findall(text):
            target = target.strip()
            if not target or target in seen_targets:
                continue
            seen_targets.add(target)
            status, note = _classify_link(root, path.parent, target)
            findings.append(LinkFinding(rel, label.strip()[:120] or target[:120], target, status, note))
            if len(findings) >= max_items:
                return [asdict(f) for f in findings]
        for m in RAW_URL_PATTERN.finditer(text):
            target = m.group(0).rstrip(".,;")
            if target in seen_targets:
                continue
            seen_targets.add(target)
            findings.append(LinkFinding(rel, target[:120], target, "external_not_checked", "External URL found. CoursePack does not verify internet links yet."))
            if len(findings) >= max_items:
                return [asdict(f) for f in findings]
    return [asdict(f) for f in findings]


def _classify_link(root: Path, base: Path, target: str) -> tuple[str, str]:
    lowered = target.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:")):
        return "external_not_checked", "External link found. CoursePack does not verify internet links yet."
    if lowered.startswith(("#", "javascript:")):
        return "internal_anchor_or_script", "Internal anchor/script-like link; not verified."
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean:
        return "internal_anchor", "Anchor-only link."
    candidate = (base / clean).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return "outside_coursepack", "Relative link points outside the converted course folder."
    if candidate.exists():
        return "ok", "Local converted link target exists."
    # Canvas exports often preserve paths to skipped web_resources. Try root-relative too.
    candidate2 = (root / clean).resolve()
    try:
        candidate2.relative_to(root.resolve())
        if candidate2.exists():
            return "ok", "Local converted link target exists."
    except ValueError:
        pass
    return "missing_local", "Local link target was not found in the converted CoursePack output."


def policy_mentions(course_dir: str | Path, *, per_group: int = 12) -> dict[str, list[dict[str, Any]]]:
    root = Path(course_dir)
    out: dict[str, list[dict[str, Any]]] = {}
    for group, terms in POLICY_GROUPS.items():
        query = " OR ".join(terms[:5])
        hits = []
        for term in terms:
            # Merge simple searches for each term; search_course requires all query terms otherwise via token count.
            for hit in search_course(root, term, max_results=per_group):
                if not any(h["path"] == hit["path"] for h in hits):
                    hit = dict(hit)
                    hit["matched_term"] = term
                    hits.append(hit)
                if len(hits) >= per_group:
                    break
            if len(hits) >= per_group:
                break
        out[group] = hits[:per_group]
    return out


def workload_by_module(course_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(course_dir)
    cmap = load_course_map(root)
    modules = cmap.get("modules", []) if isinstance(cmap, dict) else []
    results: list[WorkloadModule] = []
    for module in modules:
        words = 0
        chars = 0
        count = 0
        for item in module.get("items", []):
            target = item.get("converted_output")
            if not target:
                continue
            path = root / target
            if path.exists() and path.is_file():
                try:
                    text = read_text(path)
                except Exception:
                    continue
                count += 1
                words += _word_count(text)
                chars += len(text)
        mins = max(1, round(words / 200)) if words else 0
        results.append(WorkloadModule(module.get("position") or "", module.get("title") or "Untitled module", count, words, chars, mins))
    return [asdict(r) for r in results]


def skipped_summary(course_dir: str | Path) -> dict[str, Any]:
    skipped = load_skipped_assets(course_dir)
    by_reason: dict[str, int] = {}
    by_ext: dict[str, int] = {}
    total_size = 0
    for item in skipped:
        reason = str(item.get("reason") or "unknown")
        by_reason[reason] = by_reason.get(reason, 0) + 1
        path = str(item.get("source_path") or "")
        ext = Path(path).suffix.lower() or "(no extension)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        try:
            total_size += int(item.get("size_bytes") or 0)
        except Exception:
            pass
    return {"total": len(skipped), "total_size_bytes": total_size, "by_reason": by_reason, "by_extension": by_ext, "items": skipped}


def build_reports(course_dir: str | Path) -> dict[str, Any]:
    root = Path(course_dir)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "course_dir": str(root),
        "dates": find_dates(root),
        "links": find_links(root),
        "policy_mentions": policy_mentions(root),
        "workload_by_module": workload_by_module(root),
        "skipped_summary": skipped_summary(root),
    }


def save_reports(course_dir: str | Path) -> Path:
    root = Path(course_dir)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    data = build_reports(root)
    json_path = reports_dir / "reports.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = reports_dir / "reports.md"
    md_path.write_text(reports_to_markdown(data), encoding="utf-8")
    return md_path


def reports_to_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = ["# CoursePack Reports", "", f"Generated: {data.get('generated_at', '')}", ""]
    dates = data.get("dates", [])
    lines += ["## Date findings", "", f"Total findings: {len(dates)}", ""]
    for item in dates[:75]:
        lines.append(f"- `{item.get('match')}` in `{item.get('path')}` — {item.get('context')}")
    if len(dates) > 75:
        lines.append(f"- ...and {len(dates)-75} more date findings.")
    lines.append("")

    links = data.get("links", [])
    counts: dict[str, int] = {}
    for item in links:
        counts[item.get("status", "unknown")] = counts.get(item.get("status", "unknown"), 0) + 1
    lines += ["## Link findings", "", f"Total links found: {len(links)}", ""]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.append("")
    for item in links[:75]:
        lines.append(f"- `{item.get('status')}` — `{item.get('target')}` in `{item.get('path')}`")
    if len(links) > 75:
        lines.append(f"- ...and {len(links)-75} more links.")
    lines.append("")

    lines += ["## Policy mentions", ""]
    for group, hits in (data.get("policy_mentions") or {}).items():
        lines.append(f"### {group}")
        lines.append(f"Mentions found in {len(hits)} file(s).")
        for hit in hits[:10]:
            snippets = hit.get("snippets") or []
            snippet = snippets[0] if snippets else ""
            lines.append(f"- `{hit.get('path')}` — {snippet}")
        lines.append("")

    workload = data.get("workload_by_module", [])
    lines += ["## Workload by module", "", "| Module | Items | Words | Estimated reading minutes |", "|---|---:|---:|---:|"]
    for m in workload:
        lines.append(f"| {m.get('position')}. {m.get('title')} | {m.get('converted_items')} | {m.get('words')} | {m.get('estimated_reading_minutes')} |")
    lines.append("")

    skipped = data.get("skipped_summary") or {}
    lines += ["## Skipped files", "", f"Total skipped: {skipped.get('total', 0)}", "", "### By extension"]
    for ext, count in sorted((skipped.get("by_extension") or {}).items()):
        lines.append(f"- `{ext}`: {count}")
    lines.append("")
    return "\n".join(lines)
