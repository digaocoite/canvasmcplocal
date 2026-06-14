from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import uuid
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse, RedirectResponse

from .claude_config import connect_to_claude, status as claude_status
from .converter import CoursePackConverter, bytes_human
from .runtime import app_root, data_root, is_frozen, output_root, upload_root, zip_root
from .reports import build_reports, save_reports
from .search import course_summary, load_conversion_events, load_course_map, load_skipped_assets, search_course

APP_ROOT = app_root()
WORKSPACE_ROOT = data_root()
UPLOAD_ROOT = upload_root()
OUTPUT_ROOT = output_root()
ZIP_ROOT = zip_root()

app = FastAPI(title="CoursePack Local", version="0.9.0")


@app.get("/api/health")
def api_health():
    return {"ok": True, "app": "CoursePack Local", "version": "0.9.0"}


def safe_name(name: str, fallback: str = "course-export") -> str:
    stem = Path(name or fallback).stem
    stem = re.sub(r"[^A-Za-z0-9_. -]+", "", stem).strip(" ._")
    stem = re.sub(r"\s+", "-", stem)
    return stem[:80] or fallback


def safe_output_dir(out_name: str) -> Path:
    candidate = (OUTPUT_ROOT / Path(out_name).name).resolve()
    try:
        candidate.relative_to(OUTPUT_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course path")
    if not candidate.exists() or not candidate.is_dir():
        raise HTTPException(status_code=404, detail="Course not found")
    return candidate


def safe_course_file(output_dir: Path, file_path: str) -> Path:
    target = (output_dir / file_path).resolve()
    try:
        target.relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return target


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; color: #1f2937; background: #f8fafc; }}
    body {{ margin: 0; }}
    header {{ background: #111827; color: white; padding: 22px 28px; }}
    nav {{ margin-top: 12px; }}
    nav a {{ color: #dbeafe; margin-right: 18px; text-decoration: none; font-weight: 700; }}
    main {{ max-width: 1100px; margin: 28px auto; background: white; padding: 28px; border-radius: 14px; box-shadow: 0 10px 30px rgba(15,23,42,.08); }}
    h1 {{ margin: 0 0 8px; font-size: 1.8rem; }}
    h2 {{ margin-top: 28px; }}
    p, li {{ line-height: 1.55; }}
    .muted {{ color: #64748b; }}
    .box {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; background: #f9fafb; margin: 14px 0; }}
    .warning {{ border-color: #facc15; background: #fefce8; }}
    .success {{ border-color: #86efac; background: #f0fdf4; }}
    .error {{ border-color: #fca5a5; background: #fef2f2; white-space: pre-wrap; }}
    label {{ display:block; font-weight: 650; margin: 16px 0 8px; }}
    input[type=file] {{ width: 100%; padding: 16px; border: 2px dashed #cbd5e1; border-radius: 12px; background: #f8fafc; }}
    input[type=number], input[type=text] {{ padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; }}
    input[type=text] {{ width: min(100%, 520px); }}
    button, .button {{ display:inline-block; border: 0; border-radius: 10px; background: #2563eb; color: white; padding: 11px 16px; font-weight: 700; text-decoration: none; cursor: pointer; margin: 6px 8px 6px 0; }}
    button:disabled {{ opacity: .65; cursor: not-allowed; }}
    .statusline {{ margin-top: 12px; font-weight: 700; }}
    .small {{ font-size: .92rem; }}
    .secondary {{ background: #374151; }}
    .ghost {{ background: #e5e7eb; color: #111827; }}
    .danger {{ background: #b91c1c; }}
    code {{ background: #f1f5f9; padding: 2px 5px; border-radius: 5px; }}
    pre {{ background: #0f172a; color: #e5e7eb; padding: 16px; border-radius: 12px; overflow: auto; white-space: pre-wrap; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
    .cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; background: white; }}
    .pill {{ display:inline-block; border-radius:999px; background:#e0f2fe; color:#075985; padding:4px 10px; font-size:.85rem; font-weight:700; }}
    .list-clean {{ padding-left: 20px; }}
    .snippet {{ background:#f8fafc; border-left:4px solid #93c5fd; padding:10px; margin:8px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>CoursePack Local</h1>
    <div class=\"muted\" style=\"color:#cbd5e1\">Convert Canvas course exports into clean Markdown on this computer.</div>
    <nav><a href=\"/\">Upload</a><a href=\"/courses\">Converted Courses</a><a href=\"/claude\">Claude Desktop</a></nav>
  </header>
  <main>{body}</main>
</body>
</html>"""
    )


def ensure_mcp_dependencies() -> dict[str, object]:
    """Install MCP dependency into the local .venv if it is missing.

    This keeps the normal web/converter startup light, then prepares Claude integration
    only when the user asks for it.
    """
    try:
        import mcp  # type: ignore  # noqa: F401
        return {"ok": True, "installed": False, "message": "MCP dependency already installed."}
    except Exception:
        pass

    if is_frozen():
        return {
            "ok": False,
            "installed": False,
            "message": "The packaged app is missing the MCP dependency. Rebuild the portable app after installing requirements-mcp.txt.",
        }

    req = APP_ROOT / "requirements-mcp.txt"
    if not req.exists():
        return {"ok": False, "installed": False, "message": "requirements-mcp.txt was not found."}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            text=True,
            capture_output=True,
            timeout=300,
        )
    except Exception as exc:
        return {"ok": False, "installed": False, "message": f"Could not install MCP dependency: {exc}"}
    if proc.returncode != 0:
        return {
            "ok": False,
            "installed": False,
            "message": "Could not install MCP dependency.",
            "detail": (proc.stdout + "\n" + proc.stderr)[-4000:],
        }
    return {"ok": True, "installed": True, "message": "MCP dependency installed."}


def html_table(data: dict[str, object]) -> str:
    rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in data.items())
    return f"<table>{rows}</table>"


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return page(
        "CoursePack Local",
        """
<section class="box">
  <h2 style="margin-top:0">Upload a Canvas course export</h2>
  <p>Choose a <code>.imscc</code> Canvas export or a renamed <code>.zip</code> copy. The file stays on this computer.</p>
  <form method="post" action="/convert" enctype="multipart/form-data">
    <label for="course_file">Course export file</label>
    <input id="course_file" name="course_file" type="file" accept=".imscc,.zip" required />

    <div class="grid">
      <div>
        <label for="max_convert_mb">Skip non-text files larger than</label>
        <input id="max_convert_mb" name="max_convert_mb" type="number" value="10" min="1" max="500" /> MB
      </div>
      <div>
        <label>Optional settings</label>
        <div><input id="convert_heavy_docs" name="convert_heavy_docs" type="checkbox" value="yes" />
        <label for="convert_heavy_docs" style="display:inline;font-weight:400">Try PDF/Word/PowerPoint/Excel conversion if MarkItDown is installed</label></div>
        <div><input id="copy_assets" name="copy_assets" type="checkbox" value="yes" />
        <label for="copy_assets" style="display:inline;font-weight:400">Copy skipped media/assets into output folder</label></div>
      </div>
    </div>

    <p class="muted">Images, audio, video, large files, and unsupported files are skipped by default and listed in the conversion report.</p>
    <button type="submit">Convert Course</button>
  </form>
</section>

<div class="cards">
  <div class="card"><h3>1. Convert</h3><p>Canvas export becomes a local Markdown coursepack.</p></div>
  <div class="card"><h3>2. Review</h3><p>View the course index, modules, converted files, skipped assets, and logs.</p></div>
  <div class="card"><h3>3. Search</h3><p>Search the converted course before adding AI or MCP workflows.</p></div>
  <div class="card"><h3>4. Connect Claude</h3><p>Register the read-only CoursePack MCP server with Claude Desktop.</p></div>
</div>
        """,
    )


@app.post("/convert")
async def convert_upload(
    course_file: UploadFile = File(...),
    max_convert_mb: int = Form(10),
    convert_heavy_docs: Optional[str] = Form(None),
    copy_assets: Optional[str] = Form(None),
):
    filename = course_file.filename or "course-export.imscc"
    ext = Path(filename).suffix.lower()
    if ext not in {".imscc", ".zip"}:
        raise HTTPException(status_code=400, detail="Please upload a Canvas .imscc file or a .zip copy of one.")

    job_id = uuid.uuid4().hex[:12]
    clean = safe_name(filename)
    upload_path = UPLOAD_ROOT / f"{job_id}-{clean}{ext}"
    output_dir = OUTPUT_ROOT / f"{job_id}-{clean}"

    try:
        with upload_path.open("wb") as f:
            while True:
                chunk = await course_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        converter = CoursePackConverter(
            upload_path,
            output_dir,
            max_convert_bytes=max(1, min(max_convert_mb, 500)) * 1024 * 1024,
            convert_heavy_docs=convert_heavy_docs == "yes",
            copy_assets=copy_assets == "yes",
        )
        converter.convert()
        try:
            save_reports(output_dir)
        except Exception:
            # Reports are helpful, but conversion should not fail if a report rule has a bug.
            pass

        zip_base = ZIP_ROOT / output_dir.name
        shutil.make_archive(str(zip_base), "zip", output_dir)
        return RedirectResponse(url=f"/course/{output_dir.name}", status_code=303)
    except Exception:
        details = traceback.format_exc()
        error_path = output_dir / "conversion_failed.txt"
        output_dir.mkdir(parents=True, exist_ok=True)
        error_path.write_text(details, encoding="utf-8")
        return page(
            "Conversion failed",
            f"""
<div class="box error">
<h2 style="margin-top:0">The course could not be opened as a valid export.</h2>
<p>The app did not continue because the whole package could not be read. Individual item-level failures are normally skipped, but this error happened before conversion could begin.</p>
<pre>{html.escape(details[-5000:])}</pre>
</div>
<p><a class="button ghost" href="/">Try another file</a></p>
            """,
        )


@app.get("/courses", response_class=HTMLResponse)
def courses_page() -> HTMLResponse:
    courses = []
    if OUTPUT_ROOT.exists():
        for folder in sorted([p for p in OUTPUT_ROOT.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True):
            if (folder / "course_index.md").exists():
                summary = course_summary(folder)
                modified = folder.stat().st_mtime
                courses.append((folder.name, summary, modified))
    if not courses:
        return page("Recent Courses", "<div class='box'><h2>No converted courses yet</h2><p>Upload a Canvas export to create your first CoursePack.</p><a class='button' href='/'>Upload course</a></div>")
    cards = []
    for name, summary, modified in courses:
        import datetime
        modified_text = datetime.datetime.fromtimestamp(modified).strftime("%Y-%m-%d %I:%M %p")
        kinds = summary.get("by_kind", {}) or {}
        kinds_text = ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())) or "No item summary"
        cards.append(f"""
<div class="card">
  <h3>{html.escape(name)}</h3>
  <p class="muted">Last updated: {html.escape(modified_text)}</p>
  <p><span class="pill">{summary.get('modules', 0)} modules</span> <span class="pill">{summary.get('converted_items', 0)} converted</span> <span class="pill">{summary.get('skipped_assets', 0)} skipped</span></p>
  <p class="small">{html.escape(kinds_text)}</p>
  <p>
    <a class="button" href="/course/{html.escape(name)}">Open dashboard</a>
    <a class="button secondary" href="/reports/{html.escape(name)}">Reports</a>
    <a class="button ghost" href="/download/{html.escape(name)}.zip">Download ZIP</a>
  </p>
  <form method="post" action="/course/{html.escape(name)}/delete" onsubmit="return confirm('Delete this converted course from CoursePack Local? This does not affect Canvas or the original export file.');">
    <button class="danger" type="submit">Delete local copy</button>
  </form>
</div>""")
    return page("Recent Courses", f"<h2>Recent converted courses</h2><p class='muted'>These courses are stored locally on this computer.</p><div class='cards'>{''.join(cards)}</div>")

@app.get("/course/{out_name}", response_class=HTMLResponse)
def course_page(out_name: str) -> HTMLResponse:
    output_dir = safe_output_dir(out_name)
    summary = course_summary(output_dir)
    cmap = load_course_map(output_dir)
    skipped = load_skipped_assets(output_dir)
    events = load_conversion_events(output_dir)
    items = cmap.get("converted_items", []) if isinstance(cmap, dict) else []
    modules = cmap.get("modules", []) if isinstance(cmap, dict) else []

    kinds = summary.get("by_kind", {}) or {}
    kind_rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{v}</td></tr>" for k, v in sorted(kinds.items())) or "<tr><td colspan='2'>No converted items found.</td></tr>"

    module_html = []
    for module in modules:
        lines = [f"<details class='box'><summary><strong>{html.escape(str(module.get('position') or ''))}. {html.escape(module.get('title','Untitled module'))}</strong></summary><ul class='list-clean'>"]
        for item in module.get("items", []):
            target = item.get("converted_output")
            label = item.get("content_type") or "item"
            if target:
                lines.append(f"<li><a href='/view/{html.escape(out_name)}/{html.escape(target)}'>{html.escape(item.get('title','Untitled'))}</a> <span class='muted'>({html.escape(label)})</span></li>")
            elif item.get("url"):
                lines.append(f"<li>{html.escape(item.get('title','Untitled'))} <span class='muted'>({html.escape(label)}, external link/tool)</span></li>")
            else:
                lines.append(f"<li>{html.escape(item.get('title','Untitled'))} <span class='muted'>({html.escape(label)}, {html.escape(item.get('status','not converted'))})</span></li>")
        lines.append("</ul></details>")
        module_html.append("".join(lines))

    all_items = "".join(
        f"<li><a href='/view/{html.escape(out_name)}/{html.escape(item.get('output_path',''))}'>{html.escape(item.get('title','Untitled'))}</a> <span class='muted'>— {html.escape(item.get('kind','item'))}</span></li>"
        for item in items
    ) or "<li>No converted items found.</li>"

    skipped_preview = "".join(
        f"<li><code>{html.escape(s.get('source_path',''))}</code> — {html.escape(s.get('reason',''))} — {bytes_human(int(s.get('size_bytes') or 0))}</li>"
        for s in skipped[:30]
    ) or "<li>No skipped assets.</li>"
    if len(skipped) > 30:
        skipped_preview += f"<li>...and {len(skipped) - 30} more. Open the conversion report for the full list.</li>"

    body = f"""
<div class="box success">
  <h2 style="margin-top:0">{html.escape(out_name)}</h2>
  {html_table({'Converted items': summary.get('converted_items'), 'Modules': summary.get('modules'), 'Skipped assets': summary.get('skipped_assets'), 'Warnings/errors': summary.get('events')})}
  <p>
    <a class="button" href="/download/{html.escape(out_name)}.zip">Download converted ZIP</a>
    <a class="button secondary" href="/reports/{html.escape(out_name)}">View built-in reports</a>
    <a class="button secondary" href="/view/{html.escape(out_name)}/course_index.md">View course index</a>
    <a class="button secondary" href="/view/{html.escape(out_name)}/conversion_report.md">View conversion report</a>
  </p>
</div>

<section class="box">
  <h2 style="margin-top:0">Search this course</h2>
  <form method="get" action="/search/{html.escape(out_name)}">
    <input type="text" name="q" placeholder="late work, AI policy, final project, attendance..." required />
    <button type="submit">Search</button>
  </form>
</section>

<div class="grid">
  <section class="box"><h2 style="margin-top:0">Converted by type</h2><table>{kind_rows}</table></section>
  <section class="box"><h2 style="margin-top:0">Built-in reports</h2><p>Check dates, links, policy mentions, workload, and skipped files without using AI.</p><a class="button secondary" href="/reports/{html.escape(out_name)}">Open reports</a></section>
  <section class="box"><h2 style="margin-top:0">Claude Desktop</h2><p>Use Claude Desktop to query this converted course through the read-only MCP server.</p><a class="button secondary" href="/claude">Connect Claude</a></section>
</div>

<h2>Modules</h2>
{''.join(module_html) or '<p>No module metadata found.</p>'}

<h2>All converted items</h2>
<ul class="list-clean">{all_items}</ul>

<h2>Skipped files preview</h2>
<ul class="list-clean">{skipped_preview}</ul>
    """
    return page("Course dashboard", body)


@app.get("/search/{out_name}", response_class=HTMLResponse)
def search_page(out_name: str, q: str = Query(..., min_length=1)) -> HTMLResponse:
    output_dir = safe_output_dir(out_name)
    hits = search_course(output_dir, q, max_results=50)
    rows = []
    for hit in hits:
        snippets = "".join(f"<div class='snippet'>{html.escape(s)}</div>" for s in hit.get("snippets", []))
        rows.append(f"""
<div class="box">
  <h3 style="margin-top:0"><a href="/view/{html.escape(out_name)}/{html.escape(hit['path'])}">{html.escape(hit['title'])}</a></h3>
  <p><span class="pill">{html.escape(hit['kind'])}</span> <span class="muted">{html.escape(hit['path'])} · score {hit['score']}</span></p>
  {snippets}
</div>""")
    body = f"""
<p><a class="button ghost" href="/course/{html.escape(out_name)}">Back to course</a></p>
<section class="box">
  <h2 style="margin-top:0">Search this course</h2>
  <form method="get" action="/search/{html.escape(out_name)}">
    <input type="text" name="q" value="{html.escape(q)}" required />
    <button type="submit">Search</button>
  </form>
</section>
<h2>{len(hits)} result(s) for “{html.escape(q)}”</h2>
{''.join(rows) or '<p>No matches found.</p>'}
    """
    return page("Search results", body)

@app.get("/reports/{out_name}", response_class=HTMLResponse)
def reports_page(out_name: str) -> HTMLResponse:
    output_dir = safe_output_dir(out_name)
    # Regenerate reports on demand so older converted courses also get v9 reports.
    try:
        md_path = save_reports(output_dir)
    except Exception:
        md_path = None
    data = build_reports(output_dir)

    dates = data.get("dates", [])
    links = data.get("links", [])
    policy = data.get("policy_mentions", {}) or {}
    workload = data.get("workload_by_module", [])
    skipped = data.get("skipped_summary", {}) or {}

    link_counts = {}
    for item in links:
        status = item.get("status", "unknown")
        link_counts[status] = link_counts.get(status, 0) + 1
    link_rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{v}</td></tr>" for k, v in sorted(link_counts.items())) or "<tr><td colspan='2'>No links found.</td></tr>"

    workload_rows = "".join(
        f"<tr><td>{html.escape(str(m.get('position')))}. {html.escape(str(m.get('title')))}</td><td>{m.get('converted_items')}</td><td>{m.get('words')}</td><td>{m.get('estimated_reading_minutes')}</td></tr>"
        for m in workload
    ) or "<tr><td colspan='4'>No module workload data found.</td></tr>"

    date_rows = "".join(
        f"<tr><td><code>{html.escape(str(d.get('match')))}</code></td><td>{html.escape(str(d.get('path')))}</td><td>{html.escape(str(d.get('context')))}</td></tr>"
        for d in dates[:60]
    ) or "<tr><td colspan='3'>No date-like text found.</td></tr>"

    missing_links = [l for l in links if l.get("status") in {"missing_local", "outside_coursepack"}]
    missing_link_rows = "".join(
        f"<tr><td>{html.escape(str(l.get('status')))}</td><td><code>{html.escape(str(l.get('target')))}</code></td><td>{html.escape(str(l.get('path')))}</td></tr>"
        for l in missing_links[:80]
    ) or "<tr><td colspan='3'>No missing local links found.</td></tr>"

    policy_sections = []
    for group, hits in policy.items():
        hit_items = "".join(
            f"<li><a href='/view/{html.escape(out_name)}/{html.escape(h.get('path',''))}'>{html.escape(h.get('title') or h.get('path',''))}</a> <span class='muted'>matched: {html.escape(str(h.get('matched_term','')))}</span><div class='snippet'>{html.escape((h.get('snippets') or [''])[0])}</div></li>"
            for h in hits[:8]
        ) or "<li>No matches found.</li>"
        policy_sections.append(f"<details class='box'><summary><strong>{html.escape(group)}</strong> — {len(hits)} file(s)</summary><ul class='list-clean'>{hit_items}</ul></details>")

    skipped_ext_rows = "".join(
        f"<tr><th>{html.escape(str(ext))}</th><td>{count}</td></tr>"
        for ext, count in sorted((skipped.get("by_extension") or {}).items())
    ) or "<tr><td colspan='2'>No skipped files.</td></tr>"

    report_file_button = ""
    if md_path and md_path.exists():
        report_file_button = f"<a class='button secondary' href='/view/{html.escape(out_name)}/reports/reports.md'>View report file</a>"

    body = f"""
<p><a class="button ghost" href="/course/{html.escape(out_name)}">Back to course dashboard</a> {report_file_button} <a class="button ghost" href="/raw/{html.escape(out_name)}/reports/reports.json">Open JSON</a></p>
<div class="box success">
  <h2 style="margin-top:0">Built-in reports for {html.escape(out_name)}</h2>
  <p>These reports are rule-based and run locally. They do not require Claude, ChatGPT, or an API key.</p>
  {html_table({'Date findings': len(dates), 'Links found': len(links), 'Missing local links': len(missing_links), 'Skipped files': skipped.get('total', 0), 'Workload modules': len(workload)})}
</div>

<div class="grid">
  <section class="box"><h2 style="margin-top:0">Link summary</h2><table>{link_rows}</table></section>
  <section class="box"><h2 style="margin-top:0">Skipped files by extension</h2><table>{skipped_ext_rows}</table><p class='muted'>Total skipped size: {bytes_human(int(skipped.get('total_size_bytes') or 0))}</p></section>
</div>

<h2>Workload by module</h2>
<div class="box"><table><tr><th>Module</th><th>Converted items</th><th>Words</th><th>Estimated reading minutes</th></tr>{workload_rows}</table></div>

<h2>Possible old/current dates</h2>
<div class="box"><p class="muted">This finds date-like text. Review manually; not every date is a problem.</p><table><tr><th>Date</th><th>File</th><th>Context</th></tr>{date_rows}</table></div>

<h2>Missing local links</h2>
<div class="box"><p class="muted">External web links are listed as not checked. Missing local links may indicate content that was skipped or a Canvas path that needs cleanup.</p><table><tr><th>Status</th><th>Target</th><th>File</th></tr>{missing_link_rows}</table></div>

<h2>Policy mentions</h2>
{''.join(policy_sections)}
    """
    return page("Built-in reports", body)


@app.post("/course/{out_name}/delete")
def delete_course(out_name: str):
    output_dir = safe_output_dir(out_name)
    zip_path = ZIP_ROOT / f"{output_dir.name}.zip"
    shutil.rmtree(output_dir, ignore_errors=True)
    if zip_path.exists():
        try:
            zip_path.unlink()
        except Exception:
            pass
    return RedirectResponse(url="/courses", status_code=303)


@app.get("/help", response_class=HTMLResponse)
def help_page() -> HTMLResponse:
    body = """
<div class="box">
  <h2 style="margin-top:0">How to use CoursePack Local again later</h2>
  <p>Open <strong>CoursePack Local</strong> from your Desktop shortcut or from the Windows Start Menu. The local page is usually:</p>
  <pre>http://127.0.0.1:3333</pre>
  <p>That address only works while the CoursePack app is running.</p>
</div>
<div class="box">
  <h2 style="margin-top:0">Recommended workflow</h2>
  <ol>
    <li>Export a course from Canvas as <code>.imscc</code>.</li>
    <li>Open CoursePack Local.</li>
    <li>Upload and convert the course export.</li>
    <li>Review the dashboard and built-in reports.</li>
    <li>Optionally connect Claude Desktop after conversion.</li>
  </ol>
</div>
<div class="box warning">
  <h2 style="margin-top:0">Privacy note</h2>
  <p>CoursePack stores converted courses locally on this computer. Built-in reports and search do not send content to an AI provider.</p>
</div>
    """
    return page("Help", body)


@app.get("/download/{zip_name}")
def download_zip(zip_name: str):
    path = ZIP_ROOT / Path(zip_name).name
    if not path.exists():
        # Backwards compatibility: maybe zip was not created or was deleted. Rebuild from output dir.
        out_name = Path(zip_name).stem
        output_dir = OUTPUT_ROOT / out_name
        if output_dir.exists():
            path = Path(shutil.make_archive(str(ZIP_ROOT / out_name), "zip", output_dir))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Download not found")
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.get("/view/{out_name}/{file_path:path}", response_class=HTMLResponse)
def view_file(out_name: str, file_path: str):
    output_dir = safe_output_dir(out_name)
    target = safe_course_file(output_dir, file_path)
    text = target.read_text(encoding="utf-8", errors="replace")
    body = f"""
<p><a class="button ghost" href="/course/{html.escape(out_name)}">Back to course</a> <a class="button secondary" href="/raw/{html.escape(out_name)}/{html.escape(file_path)}">Open raw text</a></p>
<div class="box">
  <h2 style="margin-top:0">{html.escape(file_path)}</h2>
  <pre>{html.escape(text[:300000])}</pre>
</div>
    """
    return page("View file", body)


@app.get("/raw/{out_name}/{file_path:path}")
def raw_file(out_name: str, file_path: str):
    output_dir = safe_output_dir(out_name)
    target = safe_course_file(output_dir, file_path)
    text = target.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(text)




def prepare_and_connect_claude() -> dict[str, object]:
    dep = ensure_mcp_dependencies()
    if not dep.get("ok"):
        return {
            "ok": False,
            "status": "dependency_error",
            "message": str(dep.get("message", "Could not prepare MCP dependency.")),
            "dependency": dep,
            "restart_required": False,
        }
    result = connect_to_claude(force=True)
    result["dependency"] = dep
    return result


@app.get("/api/claude/status")
def api_claude_status():
    return JSONResponse(claude_status())


@app.post("/api/claude/connect")
def api_claude_connect():
    return JSONResponse(prepare_and_connect_claude())


@app.get("/claude", response_class=HTMLResponse)
def claude_page() -> HTMLResponse:
    st = claude_status()
    status_class = "success" if st.get("ready_for_claude") else "warning"
    body = f"""
<section class="box {status_class}">
  <h2 style="margin-top:0">Claude Desktop connection</h2>
  <p>This adds a read-only <code>coursepack</code> MCP server entry to Claude Desktop's local config. It backs up the existing config before changing it.</p>
  {html_table(st)}
  <button id="connectClaudeBtn" type="button">Connect CoursePack to Claude Desktop</button>
  <a class="button ghost" href="/api/claude/status" target="_blank">Open raw status</a>
  <div id="claudeConnectStatus" class="box" style="display:none"></div>
  <p class="muted small">After connecting, fully quit and reopen Claude Desktop. Then ask Claude to use CoursePack to search or analyze your converted course.</p>
</section>
<section class="box warning">
  <h2 style="margin-top:0">What Claude can access</h2>
  <p>The MCP server is read-only. It exposes converted Markdown course files, course maps, conversion reports, skipped assets, and local search tools. It does not write back to Canvas.</p>
</section>
<script>
const btn = document.getElementById('connectClaudeBtn');
const statusBox = document.getElementById('claudeConnectStatus');
function showStatus(kind, title, message, details) {{
  statusBox.style.display = 'block';
  statusBox.className = 'box ' + kind;
  let html = `<h3 style="margin-top:0">${{title}}</h3><p>${{message}}</p>`;
  if (details) {{
    html += '<pre>' + details + '</pre>';
  }}
  statusBox.innerHTML = html;
}}
btn.addEventListener('click', async () => {{
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = 'Connecting...';
  showStatus('', 'Starting Claude connection...', 'CoursePack is checking dependencies and updating Claude Desktop configuration. Do not click again.', '');
  try {{
    const res = await fetch('/api/claude/connect', {{ method: 'POST' }});
    const data = await res.json();
    const details = JSON.stringify(data, null, 2);
    if (data.ok) {{
      const title = data.status === 'already_connected' ? 'Already connected' : 'Connected successfully';
      const next = data.next_step || 'Fully quit and reopen Claude Desktop.';
      showStatus('success', title, `${{data.message}}<br><br><strong>Next step:</strong> ${{next}}`, details);
      btn.textContent = 'Connected';
    }} else {{
      showStatus('error', 'Could not connect Claude Desktop', data.message || 'Unknown error.', details);
      btn.disabled = false;
      btn.textContent = oldText;
    }}
  }} catch (err) {{
    showStatus('error', 'Connection request failed', String(err), '');
    btn.disabled = false;
    btn.textContent = oldText;
  }}
}});
</script>
    """
    return page("Claude Desktop", body)


@app.post("/claude/connect", response_class=HTMLResponse)
def connect_claude_page() -> HTMLResponse:
    # Fallback for browsers with JavaScript disabled. The main Claude page uses
    # /api/claude/connect so users get immediate progress feedback.
    result = prepare_and_connect_claude()
    cls = "success" if result.get("ok") else "error"
    body = f"""
<div class="box {cls}">
  <h2 style="margin-top:0">{html.escape(str(result.get('status','status')))}</h2>
  <p>{html.escape(str(result.get('message','')))}</p>
  {html_table(result)}
</div>
<p><a class="button ghost" href="/claude">Back to Claude settings</a></p>
    """
    return page("Claude connection result", body)


def open_browser() -> None:
    webbrowser.open("http://127.0.0.1:3333")
