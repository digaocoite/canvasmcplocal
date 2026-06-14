from __future__ import annotations

import argparse
import html
import json
import mimetypes
import re
import sys
import traceback
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET

try:
    from markdownify import markdownify as md
except Exception:  # pragma: no cover
    md = None

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

try:
    from markitdown import MarkItDown  # optional dependency for PDF/Office and other document files
except Exception:  # pragma: no cover
    MarkItDown = None

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff", ".heic",
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v",
}

TEXT_EXTENSIONS = {
    ".html", ".htm", ".txt", ".md", ".csv", ".json", ".xml", ".qti",
}

# Files instructors often upload into Canvas that are useful to convert into Markdown.
# XML is intentionally excluded from generic conversion because Canvas exports include a lot of
# internal XML metadata that is better handled by the structured Canvas parsers.
GENERIC_TEXT_FILE_EXTENSIONS = {
    ".html", ".htm", ".txt", ".md", ".csv", ".json",
}

OPTIONAL_HEAVY_DOC_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
}

GENERIC_FILE_ROOTS = (
    "web_resources/",
    "files/",
    "resources/",
)

XML_COURSE_SETTINGS = {
    "course_settings/module_meta.xml",
    "course_settings/course_settings.xml",
    "course_settings/context.xml",
    "course_settings/assignment_groups.xml",
    "course_settings/files_meta.xml",
    "course_settings/media_tracks.xml",
}


def slugify(value: str, fallback: str = "item") -> str:
    value = html.unescape(value or "").strip().lower()
    value = re.sub(r"[^\w\s.-]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s/\\]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value[:90] or fallback


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def find_child_text(elem: ET.Element, name: str, default: str = "") -> str:
    for child in list(elem):
        if local_name(child.tag) == name:
            return (child.text or default).strip()
    return default


def iter_children(elem: ET.Element, name: str) -> Iterable[ET.Element]:
    for child in list(elem):
        if local_name(child.tag) == name:
            yield child


def safe_read_text(zf: zipfile.ZipFile, name: str, errors: str = "replace") -> str:
    return zf.read(name).decode("utf-8", errors=errors)


def bytes_human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@dataclass
class ConversionEvent:
    level: str
    path: str
    message: str
    detail: Optional[str] = None


@dataclass
class ConvertedItem:
    kind: str
    title: str
    source_path: str
    output_path: str
    identifier: Optional[str] = None
    module: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkippedAsset:
    source_path: str
    size_bytes: int
    reason: str
    extension: str
    referenced_by: Optional[str] = None


@dataclass
class CoursePackResult:
    source_file: str
    generated_at: str
    output_dir: str
    converted_items: List[ConvertedItem] = field(default_factory=list)
    skipped_assets: List[SkippedAsset] = field(default_factory=list)
    events: List[ConversionEvent] = field(default_factory=list)
    modules: List[Dict[str, Any]] = field(default_factory=list)
    resource_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def warn(self, path: str, message: str, detail: Optional[str] = None) -> None:
        self.events.append(ConversionEvent("warning", path, message, detail))

    def error(self, path: str, message: str, detail: Optional[str] = None) -> None:
        self.events.append(ConversionEvent("error", path, message, detail))

    def info(self, path: str, message: str, detail: Optional[str] = None) -> None:
        self.events.append(ConversionEvent("info", path, message, detail))


class CoursePackConverter:
    def __init__(
        self,
        source_file: str | Path,
        output_dir: str | Path,
        *,
        max_convert_bytes: int = 10 * 1024 * 1024,
        convert_heavy_docs: bool = False,
        copy_assets: bool = False,
    ) -> None:
        self.source_file = Path(source_file)
        self.output_dir = Path(output_dir)
        self.max_convert_bytes = max_convert_bytes
        self.convert_heavy_docs = convert_heavy_docs
        self.copy_assets = copy_assets
        self.result = CoursePackResult(
            source_file=str(self.source_file),
            generated_at=datetime.now(timezone.utc).isoformat(),
            output_dir=str(self.output_dir),
        )
        self.resource_map: Dict[str, Dict[str, Any]] = {}
        self.used_output_names: Dict[str, int] = {}

    def convert(self) -> CoursePackResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "pages").mkdir(exist_ok=True)
        (self.output_dir / "assignments").mkdir(exist_ok=True)
        (self.output_dir / "discussions").mkdir(exist_ok=True)
        (self.output_dir / "quizzes").mkdir(exist_ok=True)
        (self.output_dir / "files").mkdir(exist_ok=True)
        (self.output_dir / "modules").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "assets").mkdir(exist_ok=True)

        if not self.source_file.exists():
            raise FileNotFoundError(self.source_file)

        with zipfile.ZipFile(self.source_file) as zf:
            self._build_resource_map(zf)
            self._scan_skipped_assets(zf)
            self._convert_wiki_pages(zf)
            self._convert_assignments(zf)
            self._convert_discussions_and_announcements(zf)
            self._convert_quizzes(zf)
            self._convert_generic_files(zf)
            self._build_modules(zf)

        self._write_indexes()
        return self.result

    def _build_resource_map(self, zf: zipfile.ZipFile) -> None:
        try:
            root = ET.fromstring(zf.read("imsmanifest.xml"))
        except Exception:
            self.result.error("imsmanifest.xml", "Could not parse manifest", traceback.format_exc())
            return

        for elem in root.iter():
            if local_name(elem.tag) != "resource":
                continue
            identifier = elem.attrib.get("identifier")
            if not identifier:
                continue
            files = []
            for f in elem.iter():
                if local_name(f.tag) == "file" and f.attrib.get("href"):
                    files.append(f.attrib["href"])
            self.resource_map[identifier] = {
                "identifier": identifier,
                "type": elem.attrib.get("type"),
                "href": elem.attrib.get("href"),
                "files": files,
            }
        self.result.resource_map = self.resource_map

    def _scan_skipped_assets(self, zf: zipfile.ZipFile) -> None:
        for info in zf.infolist():
            if info.is_dir():
                continue
            ext = Path(info.filename).suffix.lower()
            reason = None
            if ext in MEDIA_EXTENSIONS:
                reason = "media skipped by default"
            elif ext in OPTIONAL_HEAVY_DOC_EXTENSIONS and not self.convert_heavy_docs:
                reason = "document/media-like file skipped by default"
            elif info.file_size > self.max_convert_bytes and ext not in {".html", ".htm", ".xml", ".txt", ".qti"}:
                reason = f"file larger than conversion limit ({bytes_human(self.max_convert_bytes)})"
            if reason:
                self.result.skipped_assets.append(SkippedAsset(info.filename, info.file_size, reason, ext))
                if self.copy_assets:
                    self._copy_asset(zf, info.filename)

    def _copy_asset(self, zf: zipfile.ZipFile, source_path: str) -> None:
        try:
            out = self.output_dir / "assets" / Path(source_path).name
            out.write_bytes(zf.read(source_path))
        except Exception:
            self.result.warn(source_path, "Could not copy skipped asset", traceback.format_exc())

    def _convert_wiki_pages(self, zf: zipfile.ZipFile) -> None:
        for name in zf.namelist():
            if not name.startswith("wiki_content/") or not name.lower().endswith((".html", ".htm")):
                continue
            try:
                raw = safe_read_text(zf, name)
                title = self._html_title(raw) or Path(name).stem.replace("-", " ").title()
                markdown = self._html_to_markdown(raw, source_path=name)
                out_name = self._unique_name("pages", slugify(title), ".md")
                out_path = self.output_dir / out_name
                out_path.write_text(self._frontmatter("page", title, name) + markdown, encoding="utf-8")
                identifier = self._identifier_for_href(name)
                self.result.converted_items.append(ConvertedItem("page", title, name, out_name, identifier=identifier))
            except Exception:
                self.result.error(name, "Could not convert wiki page; skipped", traceback.format_exc())

    def _convert_assignments(self, zf: zipfile.ZipFile) -> None:
        assignment_dirs = set()
        for name in zf.namelist():
            if name.endswith("/assignment_settings.xml"):
                assignment_dirs.add(str(Path(name).parent))

        for folder in sorted(assignment_dirs):
            settings_path = f"{folder}/assignment_settings.xml"
            try:
                title, metadata = self._parse_assignment_settings(zf, settings_path)
            except Exception:
                title, metadata = Path(folder).name, {}
                self.result.warn(settings_path, "Could not parse assignment settings; using folder name", traceback.format_exc())
            html_files = [n for n in zf.namelist() if n.startswith(folder + "/") and n.lower().endswith((".html", ".htm"))]
            if not html_files:
                self.result.warn(folder, "Assignment has settings but no HTML body; skipped")
                continue
            for html_path in html_files:
                try:
                    raw = safe_read_text(zf, html_path)
                    html_title = self._html_title(raw)
                    final_title = title or html_title or Path(html_path).stem.replace("-", " ").title()
                    body = self._html_to_markdown(raw, source_path=html_path)
                    out_name = self._unique_name("assignments", slugify(final_title), ".md")
                    out_path = self.output_dir / out_name
                    out_path.write_text(self._frontmatter("assignment", final_title, html_path, metadata) + body, encoding="utf-8")
                    identifier = Path(folder).name
                    self.result.converted_items.append(ConvertedItem("assignment", final_title, html_path, out_name, identifier=identifier, metadata=metadata))
                except Exception:
                    self.result.error(html_path, "Could not convert assignment body; skipped", traceback.format_exc())

    def _convert_discussions_and_announcements(self, zf: zipfile.ZipFile) -> None:
        # topic files use <topic>; topicMeta files are metadata only and should not produce duplicate content.
        for name in zf.namelist():
            if "/" in name or not name.lower().endswith(".xml"):
                continue
            try:
                root = ET.fromstring(zf.read(name))
                if local_name(root.tag) != "topic":
                    continue
                title = find_child_text(root, "title", Path(name).stem)
                text_html = ""
                for child in iter_children(root, "text"):
                    text_html = child.text or ""
                    break
                content = self._html_to_markdown(html.unescape(text_html), source_path=name) if text_html else ""
                out_name = self._unique_name("discussions", slugify(title), ".md")
                out_path = self.output_dir / out_name
                out_path.write_text(self._frontmatter("discussion_or_announcement", title, name) + content, encoding="utf-8")
                self.result.converted_items.append(ConvertedItem("discussion_or_announcement", title, name, out_name, identifier=Path(name).stem))
            except Exception:
                self.result.error(name, "Could not convert discussion/announcement; skipped", traceback.format_exc())

    def _convert_quizzes(self, zf: zipfile.ZipFile) -> None:
        quiz_dirs = set()
        for name in zf.namelist():
            if name.endswith("/assessment_meta.xml") or name.endswith("/assessment_qti.xml"):
                quiz_dirs.add(str(Path(name).parent))
        for folder in sorted(quiz_dirs):
            title = Path(folder).name
            metadata: Dict[str, Any] = {}
            meta_path = f"{folder}/assessment_meta.xml"
            qti_path = f"{folder}/assessment_qti.xml"
            try:
                if meta_path in zf.namelist():
                    root = ET.fromstring(zf.read(meta_path))
                    title = find_child_text(root, "title", title)
                    for key in ["description", "due_at", "lock_at", "unlock_at", "shuffle_questions", "scoring_policy", "points_possible"]:
                        val = find_child_text(root, key, "")
                        if val:
                            metadata[key] = val
            except Exception:
                self.result.warn(meta_path, "Could not parse quiz metadata", traceback.format_exc())
            try:
                content = f"# {title}\n\n"
                if metadata:
                    content += "## Metadata\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in metadata.items()) + "\n\n"
                if qti_path in zf.namelist():
                    content += self._extract_qti_text(zf, qti_path)
                out_name = self._unique_name("quizzes", slugify(title), ".md")
                out_path = self.output_dir / out_name
                out_path.write_text(self._frontmatter("quiz", title, qti_path, metadata) + content, encoding="utf-8")
                self.result.converted_items.append(ConvertedItem("quiz", title, qti_path, out_name, identifier=Path(folder).name, metadata=metadata))
            except Exception:
                self.result.error(folder, "Could not convert quiz; skipped", traceback.format_exc())

    def _convert_generic_files(self, zf: zipfile.ZipFile) -> None:
        """Convert loose instructor-uploaded files that are not Canvas-native pages.

        Canvas exports usually place uploaded files in web_resources/. This pass is deliberately
        conservative: it converts small text-like files by default and only attempts PDF/Office
        files when convert_heavy_docs=True. Images, audio, and video remain skipped assets.
        """
        converted_sources = {item.source_path for item in self.result.converted_items}
        all_names = set(zf.namelist())

        for info in zf.infolist():
            name = info.filename
            if info.is_dir() or name in converted_sources:
                continue
            if self._is_canvas_internal_file(name):
                continue
            if not self._is_probable_uploaded_or_loose_file(name):
                continue

            ext = Path(name).suffix.lower()
            if ext in MEDIA_EXTENSIONS:
                # Already recorded in skipped_assets during _scan_skipped_assets.
                continue
            if info.file_size > self.max_convert_bytes and ext not in GENERIC_TEXT_FILE_EXTENSIONS:
                self._record_skip_once(name, info.file_size, f"file larger than conversion limit ({bytes_human(self.max_convert_bytes)})", ext)
                continue

            if ext in GENERIC_TEXT_FILE_EXTENSIONS:
                self._convert_small_text_file(zf, name, ext)
                continue

            if ext in OPTIONAL_HEAVY_DOC_EXTENSIONS:
                if not self.convert_heavy_docs:
                    # Already recorded in skipped_assets during _scan_skipped_assets.
                    continue
                self._convert_document_file(zf, name, ext)
                continue

            # Unknown files are not fatal. Record them so the instructor knows they were ignored.
            self._record_skip_once(name, info.file_size, "unsupported file type skipped", ext or "")

    def _is_canvas_internal_file(self, name: str) -> bool:
        if name == "imsmanifest.xml":
            return True
        if name.startswith("course_settings/"):
            return True
        if name.startswith("lti_resource_links/"):
            return True
        if name.startswith("non_cc_assessments/"):
            return True
        if name.startswith("wiki_content/"):
            return True
        if name.endswith("/assignment_settings.xml") or name.endswith("/assessment_meta.xml") or name.endswith("/assessment_qti.xml"):
            return True
        if "/" not in name and name.lower().endswith(".xml"):
            # Root-level topic XML is handled by _convert_discussions_and_announcements.
            return True
        return False

    def _is_probable_uploaded_or_loose_file(self, name: str) -> bool:
        if name.startswith(GENERIC_FILE_ROOTS):
            return True
        # Some Canvas exports put assignment/file resources in generated folders. If it is not
        # known Canvas metadata and it has a regular document/text extension, consider it.
        ext = Path(name).suffix.lower()
        return ext in GENERIC_TEXT_FILE_EXTENSIONS or ext in OPTIONAL_HEAVY_DOC_EXTENSIONS or ext in MEDIA_EXTENSIONS

    def _convert_small_text_file(self, zf: zipfile.ZipFile, name: str, ext: str) -> None:
        try:
            raw = safe_read_text(zf, name)
            title = Path(name).stem.replace("-", " ").replace("_", " ").title()
            if ext in {".html", ".htm"}:
                title = self._html_title(raw) or title
                body = self._html_to_markdown(raw, source_path=name)
            elif ext == ".md":
                body = raw.strip() + "\n"
            elif ext in {".csv", ".json"}:
                body = f"```{ext.lstrip('.')}\n{raw.strip()}\n```\n"
            else:
                body = raw.strip() + "\n"
            out_name = self._unique_name("files", slugify(title), ".md")
            out_path = self.output_dir / out_name
            out_path.write_text(self._frontmatter("file", title, name, {"conversion_method": "text_or_html"}) + body, encoding="utf-8")
            self.result.converted_items.append(ConvertedItem("file", title, name, out_name, metadata={"extension": ext, "conversion_method": "text_or_html"}))
        except Exception:
            self.result.error(name, "Could not convert text-like file; skipped", traceback.format_exc())

    def _convert_document_file(self, zf: zipfile.ZipFile, name: str, ext: str) -> None:
        if MarkItDown is None:
            self._record_skip_once(
                name,
                zf.getinfo(name).file_size,
                "document conversion requested, but MarkItDown is not installed",
                ext,
            )
            self.result.warn(name, "Install optional dependency `markitdown` to convert PDF/Office files")
            return

        temp_dir = self.output_dir / "metadata" / "_tmp_conversion"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / Path(name).name
        try:
            temp_path.write_bytes(zf.read(name))
            converter = MarkItDown()
            converted = converter.convert(str(temp_path))
            text = getattr(converted, "text_content", None) or str(converted)
            if not text or not text.strip():
                self._record_skip_once(name, zf.getinfo(name).file_size, "document converted to empty text; skipped", ext)
                return
            title = Path(name).stem.replace("-", " ").replace("_", " ").title()
            out_name = self._unique_name("files", slugify(title), ".md")
            out_path = self.output_dir / out_name
            out_path.write_text(
                self._frontmatter("file", title, name, {"conversion_method": "markitdown", "extension": ext}) + text.strip() + "\n",
                encoding="utf-8",
            )
            self.result.converted_items.append(ConvertedItem("file", title, name, out_name, metadata={"extension": ext, "conversion_method": "markitdown"}))
        except Exception:
            self.result.error(name, "Could not convert document file with MarkItDown; skipped", traceback.format_exc())
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _record_skip_once(self, source_path: str, size_bytes: int, reason: str, extension: str) -> None:
        if any(s.source_path == source_path for s in self.result.skipped_assets):
            return
        self.result.skipped_assets.append(SkippedAsset(source_path, size_bytes, reason, extension))

    def _build_modules(self, zf: zipfile.ZipFile) -> None:
        path = "course_settings/module_meta.xml"
        if path not in zf.namelist():
            self.result.warn(path, "No Canvas module metadata found")
            return
        try:
            root = ET.fromstring(zf.read(path))
        except Exception:
            self.result.error(path, "Could not parse module metadata", traceback.format_exc())
            return

        modules = []
        for module in iter_children(root, "module"):
            module_title = find_child_text(module, "title", "Untitled module")
            module_position = find_child_text(module, "position", "")
            module_entry: Dict[str, Any] = {
                "title": module_title,
                "position": int(module_position) if module_position.isdigit() else None,
                "identifier": module.attrib.get("identifier"),
                "items": [],
            }
            items_container = next(iter_children(module, "items"), None)
            if items_container is not None:
                for item in iter_children(items_container, "item"):
                    identifierref = find_child_text(item, "identifierref", "")
                    content_type = find_child_text(item, "content_type", "")
                    item_title = find_child_text(item, "title", "Untitled item")
                    item_position = find_child_text(item, "position", "")
                    url = find_child_text(item, "url", "")
                    resolved = self.resource_map.get(identifierref, {})
                    output_item = self._find_converted_by_identifier_or_source(identifierref, resolved)
                    module_entry["items"].append({
                        "title": item_title,
                        "content_type": content_type,
                        "position": int(item_position) if item_position.isdigit() else None,
                        "identifierref": identifierref,
                        "url": url,
                        "source_href": resolved.get("href"),
                        "converted_output": output_item.output_path if output_item else None,
                        "status": "converted" if output_item else "not_converted_or_external",
                    })
            modules.append(module_entry)

        modules.sort(key=lambda m: (m.get("position") is None, m.get("position") or 9999, m.get("title") or ""))
        self.result.modules = modules
        self._write_module_markdown(modules)

    def _write_module_markdown(self, modules: List[Dict[str, Any]]) -> None:
        for idx, module in enumerate(modules, start=1):
            title = module["title"]
            lines = [f"# Module {idx}: {title}", ""]
            for item in sorted(module.get("items", []), key=lambda i: (i.get("position") is None, i.get("position") or 9999)):
                status = item.get("status")
                out = item.get("converted_output")
                label = item.get("content_type") or "Item"
                if out:
                    lines.append(f"- **{item['title']}** ({label}) → `{out}`")
                elif item.get("url"):
                    lines.append(f"- **{item['title']}** ({label}) → external URL: {item['url']}")
                else:
                    lines.append(f"- **{item['title']}** ({label}) → {status}")
            lines.append("")
            out_name = self._unique_name("modules", f"{idx:02d}-{slugify(title)}", ".md")
            (self.output_dir / out_name).write_text("\n".join(lines), encoding="utf-8")

    def _find_converted_by_identifier_or_source(self, identifier: str, resource: Dict[str, Any]) -> Optional[ConvertedItem]:
        for item in self.result.converted_items:
            if item.identifier == identifier:
                return item
        href = resource.get("href")
        files = set(resource.get("files") or [])
        for item in self.result.converted_items:
            if href and item.source_path == href:
                return item
            if item.source_path in files:
                return item
        return None

    def _parse_assignment_settings(self, zf: zipfile.ZipFile, path: str) -> Tuple[str, Dict[str, Any]]:
        root = ET.fromstring(zf.read(path))
        title = find_child_text(root, "title", Path(path).parent.name)
        metadata: Dict[str, Any] = {}
        for key in ["due_at", "lock_at", "unlock_at", "points_possible", "grading_type", "submission_types", "workflow_state"]:
            val = find_child_text(root, key, "")
            if val:
                metadata[key] = val
        return title, metadata

    def _extract_qti_text(self, zf: zipfile.ZipFile, path: str) -> str:
        root = ET.fromstring(zf.read(path))
        lines = ["## Questions / QTI extracted text", ""]
        question_num = 1
        for item in root.iter():
            if local_name(item.tag) != "item":
                continue
            title = item.attrib.get("title") or f"Question {question_num}"
            lines.append(f"### {question_num}. {title}")
            for mattext in item.iter():
                if local_name(mattext.tag) == "mattext" and mattext.text:
                    text = self._html_to_markdown(html.unescape(mattext.text), source_path=path).strip()
                    if text:
                        lines.append(text)
                        lines.append("")
            question_num += 1
        return "\n".join(lines) + "\n"

    def _identifier_for_href(self, href: str) -> Optional[str]:
        for identifier, res in self.resource_map.items():
            if res.get("href") == href or href in (res.get("files") or []):
                return identifier
        return None

    def _html_title(self, raw: str) -> str:
        if BeautifulSoup:
            soup = BeautifulSoup(raw, "html.parser")
            if soup.title and soup.title.get_text(strip=True):
                return soup.title.get_text(strip=True)
            h1 = soup.find(["h1", "h2"])
            if h1 and h1.get_text(strip=True):
                return h1.get_text(" ", strip=True)
        m = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
        if m:
            return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        m = re.search(r"<h[12][^>]*>(.*?)</h[12]>", raw, flags=re.I | re.S)
        if m:
            return re.sub(r"<[^>]+>", "", html.unescape(m.group(1))).strip()
        return ""

    def _html_to_markdown(self, raw: str, *, source_path: str) -> str:
        if not raw.strip():
            return ""
        cleaned = raw
        if BeautifulSoup:
            soup = BeautifulSoup(raw, "html.parser")
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            for img in soup.find_all("img"):
                alt = img.get("alt") or ""
                src = img.get("src") or img.get("data-src") or ""
                placeholder = soup.new_string(f"\n\n[Image skipped: {alt or Path(src).name or 'embedded image'} | source: {src}]\n\n")
                img.replace_with(placeholder)
            for audio in soup.find_all(["audio", "video", "source"]):
                src = audio.get("src") or ""
                placeholder = soup.new_string(f"\n\n[Media skipped: {Path(src).name or 'embedded media'} | source: {src}]\n\n")
                audio.replace_with(placeholder)
            cleaned = str(soup)
        if md:
            text = md(cleaned, heading_style="ATX", bullets="-")
        else:
            text = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.I)
            text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = html.unescape(text)
        text = html.unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip() + "\n"

    def _frontmatter(self, kind: str, title: str, source_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        data = {
            "type": kind,
            "title": title,
            "source_path": source_path,
        }
        if metadata:
            data.update(metadata)
        lines = ["---"]
        for key, value in data.items():
            value_s = str(value).replace("\n", " ").replace('"', "'")
            lines.append(f'{key}: "{value_s}"')
        lines.append("---")
        lines.append("")
        if not re.match(r"^#\s", title.strip()):
            lines.append(f"# {title}")
            lines.append("")
        return "\n".join(lines)

    def _unique_name(self, folder: str, stem: str, suffix: str) -> str:
        base = f"{folder}/{stem}{suffix}"
        count = self.used_output_names.get(base, 0)
        if count == 0:
            self.used_output_names[base] = 1
            return base
        self.used_output_names[base] += 1
        return f"{folder}/{stem}-{count+1}{suffix}"

    def _write_indexes(self) -> None:
        # JSON metadata
        items = [asdict(i) for i in self.result.converted_items]
        skipped = [asdict(s) for s in self.result.skipped_assets]
        events = [asdict(e) for e in self.result.events]
        (self.output_dir / "metadata" / "course_map.json").write_text(json.dumps({
            "source_file": self.result.source_file,
            "generated_at": self.result.generated_at,
            "modules": self.result.modules,
            "converted_items": items,
            "skipped_assets_count": len(skipped),
            "events_count": len(events),
        }, indent=2), encoding="utf-8")
        (self.output_dir / "metadata" / "skipped_assets.json").write_text(json.dumps(skipped, indent=2), encoding="utf-8")
        (self.output_dir / "metadata" / "conversion_events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
        (self.output_dir / "metadata" / "resource_map.json").write_text(json.dumps(self.resource_map, indent=2), encoding="utf-8")

        # Markdown report
        lines = [
            "# CoursePack Conversion Report",
            "",
            f"- Source file: `{self.source_file.name}`",
            f"- Generated: {self.result.generated_at}",
            f"- Converted items: {len(self.result.converted_items)}",
            f"- Skipped assets: {len(self.result.skipped_assets)}",
            f"- Warnings/errors: {len(self.result.events)}",
            "",
            "## Converted content",
            "",
        ]
        by_kind: Dict[str, int] = {}
        for item in self.result.converted_items:
            by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        for kind, count in sorted(by_kind.items()):
            lines.append(f"- {kind}: {count}")
        lines.extend(["", "## Modules", ""])
        for module in self.result.modules:
            lines.append(f"### {module.get('position') or ''}. {module['title']}")
            for item in module.get("items", []):
                target = item.get("converted_output") or item.get("url") or item.get("status")
                lines.append(f"- {item['title']} ({item.get('content_type')}) → {target}")
            lines.append("")
        lines.extend(["", "## Skipped assets", ""])
        for s in self.result.skipped_assets[:200]:
            lines.append(f"- `{s.source_path}` — {s.reason} — {bytes_human(s.size_bytes)}")
        if len(self.result.skipped_assets) > 200:
            lines.append(f"- ...and {len(self.result.skipped_assets) - 200} more. See `metadata/skipped_assets.json`.")
        lines.extend(["", "## Warnings and errors", ""])
        if not self.result.events:
            lines.append("No conversion warnings or errors.")
        for e in self.result.events:
            lines.append(f"- **{e.level.upper()}** `{e.path}` — {e.message}")
        (self.output_dir / "conversion_report.md").write_text("\n".join(lines), encoding="utf-8")

        # Course index
        index = ["# Converted Course Index", "", "## Modules", ""]
        for module in self.result.modules:
            index.append(f"### {module.get('position') or ''}. {module['title']}")
            for item in module.get("items", []):
                out = item.get("converted_output")
                if out:
                    index.append(f"- [{item['title']}]({out})")
                elif item.get("url"):
                    index.append(f"- {item['title']} — external tool/link: {item['url']}")
                else:
                    index.append(f"- {item['title']} — {item.get('status')}")
            index.append("")
        index.extend(["", "## All converted items", ""])
        for item in self.result.converted_items:
            index.append(f"- [{item.title}]({item.output_path}) — {item.kind}")
        (self.output_dir / "course_index.md").write_text("\n".join(index), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a Canvas .imscc course export into a Markdown CoursePack.")
    parser.add_argument("source", help="Path to Canvas .imscc export")
    parser.add_argument("output", help="Output directory for converted CoursePack")
    parser.add_argument("--max-convert-mb", type=int, default=10, help="Skip non-text files larger than this size. Default: 10 MB")
    parser.add_argument("--convert-heavy-docs", "--convert-docs", action="store_true", help="Attempt to convert PDF/Office files with MarkItDown if installed. Default: skip")
    parser.add_argument("--copy-assets", action="store_true", help="Copy skipped assets into output/assets. Default: only log them")
    args = parser.parse_args(argv)

    converter = CoursePackConverter(
        args.source,
        args.output,
        max_convert_bytes=args.max_convert_mb * 1024 * 1024,
        convert_heavy_docs=args.convert_heavy_docs,
        copy_assets=args.copy_assets,
    )
    result = converter.convert()
    print(f"Converted items: {len(result.converted_items)}")
    print(f"Skipped assets: {len(result.skipped_assets)}")
    print(f"Warnings/errors: {len(result.events)}")
    print(f"Output: {converter.output_dir}")
    print(f"Report: {converter.output_dir / 'conversion_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
