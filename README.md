# CoursePack Local MVP v5

CoursePack Local converts Canvas `.imscc` course exports into a clean, local Markdown coursepack. It now includes a local web interface, course viewer, search, safe skip logging, and a read-only MCP server connection for Claude Desktop.

The project is still an MVP, but v5 is closer to a deployable instructor workflow:

1. Double-click `Start CoursePack Local.bat`.
2. Browser opens at `http://127.0.0.1:3333`.
3. Upload a Canvas `.imscc` export.
4. Review the converted course, skipped files, and report.
5. Search the converted course.
6. Connect the local read-only MCP server to Claude Desktop.

## What changed in v5

- Added immediate browser feedback when clicking **Connect CoursePack to Claude Desktop**.
- The button now disables while connecting so users do not click it multiple times.
- The page shows **Starting**, **Connected**, **Already connected**, or **Error** messages.
- Added JSON status endpoint: `/api/claude/status`.
- Added JSON connect endpoint: `/api/claude/connect`.
- Claude config updates are now idempotent: repeated clicks do not create unnecessary backups if the config is already correct.
- Claude config is backed up before it is changed.
- Added `Check CoursePack Install.bat` for a basic readiness check.
- Improved `Connect CoursePack to Claude.bat` with visible progress messages.

## What it does now

- Reads a Canvas `.imscc` file as a ZIP archive.
- Parses `imsmanifest.xml` and `course_settings/module_meta.xml` when present.
- Converts Canvas wiki HTML pages to Markdown.
- Converts assignment HTML pages and assignment metadata.
- Converts discussion/announcement XML topic bodies.
- Extracts basic quiz/QTI text.
- Builds module index files.
- Converts loose instructor-uploaded text-like files, such as `.html`, `.txt`, `.md`, `.csv`, and `.json`.
- Skips images, audio, video, PowerPoint, Office files, PDFs, unknown files, and very large files by default.
- Can optionally attempt PDF/Office conversion with Microsoft MarkItDown if the optional dependency is installed.
- Writes a human-readable `conversion_report.md`.
- Writes structured metadata in `metadata/course_map.json`, `metadata/skipped_assets.json`, `metadata/conversion_events.json`, and `metadata/resource_map.json`.
- Runs a local web app for upload, review, search, and download.
- Provides a read-only MCP server for Claude Desktop.

## Windows quick start

1. Unzip the CoursePack folder.
2. Double-click:

```text
Start CoursePack Local.bat
```

The first run creates a local `.venv` and installs required packages.

3. Open or wait for the browser page:

```text
http://127.0.0.1:3333
```

4. Upload a Canvas `.imscc` export and click **Convert Course**.

## Check the install

After running CoursePack once, double-click:

```text
Check CoursePack Install.bat
```

This checks Python, required packages, local app files, and Claude configuration readability.

## Connect to Claude Desktop

The easiest method is from the browser UI:

1. Open CoursePack Local.
2. Go to **Claude Desktop** in the top navigation.
3. Click **Connect CoursePack to Claude Desktop**.
4. The page immediately shows that the process started.
5. When it finishes, fully quit and reopen Claude Desktop.

You can also run:

```text
Connect CoursePack to Claude.bat
```

Claude Desktop reads local MCP servers from its local config file. CoursePack adds a `coursepack` MCP server entry pointing to this project's local Python environment and `mcp_server.py`.

## What Claude can access

The MCP server is read-only. It exposes:

- converted Markdown course files
- course map metadata
- conversion report
- skipped assets log
- conversion events log
- local search tools

It does **not** write back to Canvas.

## Failure behavior

A single bad file should never stop the full course conversion.

The converter records:

- converted files in `metadata/course_map.json`
- skipped files in `metadata/skipped_assets.json`
- warnings/errors in `metadata/conversion_events.json`
- a readable summary in `conversion_report.md`

If a document cannot be converted, CoursePack skips it, logs it, and keeps converting the rest of the course.

## Optional document conversion

By default, PDFs and Office files are skipped because they can be large, slow, or messy.

To attempt conversion of PDF/Office files, install the optional converter dependency:

```bash
pip install -r requirements-docs.txt
```

Then enable the optional document conversion checkbox in the upload page.

If MarkItDown is not installed, the converter will skip those files, record the reason, and continue.

## Media files skipped by default

Skipped by default:

- images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`, `.bmp`, `.tif`, `.tiff`, `.heic`
- audio: `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac`
- video: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.wmv`, `.m4v`
- PDF/Office files unless optional conversion is enabled
- unknown file types
- large files above the conversion size limit

## Current deployment limitations

This is closer to deployment, but not fully packaged for nontechnical instructors yet.

Current v5 still requires:

- Python installed on the computer
- first-run package installation into `.venv`
- Windows batch files for startup

The next deployment milestone is a portable build that bundles Python so instructors do not need to install Python or use a terminal.

## Recommended next steps

1. Test v5 on Windows with Claude Desktop installed.
2. Test with several Canvas exports from different course types.
3. Package Python into the app so it can run without a system Python install.
4. Add a signed Windows installer or portable `.exe`.
5. Add optional AI chat inside the local browser UI.
6. Add a Claude Desktop `.mcpb` extension package later for the cleanest Claude install experience.

## One-line Windows installer

v7 adds `install.ps1`, which allows this style of installation after the project is on GitHub and a portable ZIP is attached to the latest GitHub Release:

```powershell
irm https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1 | iex
```

Repo: `digaocoite/canvasmcplocal`. Before first use, publish a GitHub Release with the portable Windows ZIP (see `ONE_LINE_INSTALL.md`).

See `ONE_LINE_INSTALL.md` for the full release process.
