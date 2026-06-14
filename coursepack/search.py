from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, List

TEXT_FILE_EXTENSIONS = {".md", ".txt", ".json", ".csv"}


@dataclass
class SearchHit:
    path: str
    title: str
    kind: str
    score: int
    snippets: list[str]


def load_course_map(course_dir: str | Path) -> dict[str, Any]:
    course_dir = Path(course_dir)
    path = course_dir / "metadata" / "course_map.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def load_skipped_assets(course_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(course_dir) / "metadata" / "skipped_assets.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def load_conversion_events(course_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(course_dir) / "metadata" / "conversion_events.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def iter_markdown_files(course_dir: str | Path) -> Iterable[Path]:
    root = Path(course_dir)
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in TEXT_FILE_EXTENSIONS and "metadata" not in p.relative_to(root).parts:
            yield p


def read_text(path: Path, limit_chars: int | None = None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit_chars] if limit_chars else text


def extract_title_and_kind(text: str, fallback: str) -> tuple[str, str]:
    title = fallback
    kind = "file"
    in_frontmatter = False
    for i, line in enumerate(text.splitlines()[:60]):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            in_frontmatter = False
            continue
        if in_frontmatter:
            m = re.match(r"(title|type):\s*[\"']?(.*?)[\"']?\s*$", line)
            if m:
                key, value = m.group(1), m.group(2).strip()
                if key == "title" and value:
                    title = value
                elif key == "type" and value:
                    kind = value
        elif line.startswith("# ") and title == fallback:
            title = line[2:].strip()
    return title, kind


def search_course(course_dir: str | Path, query: str, *, max_results: int = 20) -> list[dict[str, Any]]:
    root = Path(course_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    terms = [t.lower() for t in re.findall(r"[\w'-]+", query or "") if len(t) >= 2]
    if not terms:
        return []
    hits: list[SearchHit] = []
    for path in iter_markdown_files(root):
        try:
            text = read_text(path)
        except Exception:
            continue
        lower = text.lower()
        score = sum(lower.count(term) for term in terms)
        if score <= 0:
            continue
        title, kind = extract_title_and_kind(text, path.stem.replace("-", " ").title())
        snippets = make_snippets(text, terms)
        rel = path.relative_to(root).as_posix()
        hits.append(SearchHit(rel, title, kind, score, snippets))
    hits.sort(key=lambda h: (-h.score, h.path))
    return [asdict(h) for h in hits[:max_results]]


def make_snippets(text: str, terms: list[str], *, radius: int = 120, max_snippets: int = 3) -> list[str]:
    lower = text.lower()
    snippets: list[str] = []
    seen_spans: list[tuple[int, int]] = []
    for term in terms:
        for match in re.finditer(re.escape(term), lower):
            start = max(0, match.start() - radius)
            end = min(len(text), match.end() + radius)
            if any(abs(start - s) < 60 for s, _ in seen_spans):
                continue
            seen_spans.append((start, end))
            snippet = text[start:end].replace("\r", " ").replace("\n", " ")
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if start > 0:
                snippet = "…" + snippet
            if end < len(text):
                snippet += "…"
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def course_summary(course_dir: str | Path) -> dict[str, Any]:
    root = Path(course_dir)
    cmap = load_course_map(root)
    skipped = load_skipped_assets(root)
    events = load_conversion_events(root)
    items = cmap.get("converted_items", []) if isinstance(cmap, dict) else []
    modules = cmap.get("modules", []) if isinstance(cmap, dict) else []
    by_kind: dict[str, int] = {}
    for item in items:
        kind = item.get("kind") or item.get("type") or "unknown"
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "course_dir": str(root),
        "converted_items": len(items),
        "skipped_assets": len(skipped),
        "events": len(events),
        "modules": len(modules),
        "by_kind": by_kind,
    }
