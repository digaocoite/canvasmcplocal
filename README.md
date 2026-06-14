# CoursePack Local MVP v9

CoursePack Local converts Canvas `.imscc` course exports into a clean, local Markdown coursepack. It now includes a local web interface, course viewer, search, safe skip logging, and a read-only MCP server connection for Claude Desktop.

The project is still an MVP, but v9 is closer to a deployable instructor workflow:

1. Double-click `Start CoursePack Local.bat`.
2. Browser opens at `http://127.0.0.1:3333`.
3. Upload a Canvas `.imscc` export.
4. Review the converted course, skipped files, and report.
5. Search the converted course.
6. Connect the local read-only MCP server to Claude Desktop.

## What changed in v9

- Added a stronger **Recent Courses** page with last-updated information, quick actions, and local delete buttons.
- Added built-in local reports that do not require AI: date findings, link findings, missing local links, policy mentions, skipped-file summary, and workload by module.
- Reports are saved as `reports/reports.md` and `reports/reports.json` in each converted course.
- Added a Help page explaining how instructors open CoursePack again after the first install.
- Added a user-level uninstall helper: `Uninstall CoursePack Local.bat` and `uninstall.ps1`.
- Added MCP tools for Claude to read the built-in reports.
- Kept v8 behavior: the one-line installer does not auto-connect Claude Desktop during installation.
- Kept v8 behavior: installer starts CoursePack first, opens the local browser page when possible, and creates Desktop/Start Menu shortcuts.
- Kept v8 behavior: Claude connection has immediate browser feedback and is idempotent.

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
- Runs a local web app for upload, review, search, reports, and download.
- Provides built-in rule-based reports that work without AI.
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


## Using CoursePack after the first install

Instructors do not run the one-line installer every time. The one-line command is only for first install or reinstall/update.

After CoursePack is installed, use one of these:

```text
Desktop shortcut: CoursePack Local
Start Menu shortcut: CoursePack Local
Manual address after starting: http://127.0.0.1:3333
```

Converted courses and app data are stored in the user's local profile:

```text
%LOCALAPPDATA%\CoursePackLocal
```

If CoursePack is already running and the instructor clicks the shortcut again, the app should simply open the browser page instead of failing because the port is already in use.

## Claude connection timing

CoursePack does not need a converted course before the MCP connector can be registered with Claude Desktop, but Claude will not have useful course content until at least one Canvas export is converted.

Recommended flow:

```text
1. Install CoursePack.
2. Open the local CoursePack page.
3. Convert a Canvas export.
4. Click Claude Desktop > Connect CoursePack to Claude Desktop.
5. Fully quit and reopen Claude Desktop.
```

The installer intentionally does not auto-connect Claude anymore. This prevents a Claude/Windows security problem from blocking the app startup.

## Check the install

After running CoursePack once, double-click:

```text
Check CoursePack Install.bat
```

This checks Python, required packages, local app files, and Claude configuration readability.

To remove the local app later, use the Start Menu shortcut or run:

```text
Uninstall CoursePack Local.bat
```

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

Source/dev mode still requires:

- Python installed on the computer
- first-run package installation into `.venv`
- Windows batch files for startup

Portable/release mode bundles Python with PyInstaller. Some managed university computers may still block unknown unsigned executables. In that case, use the source/dev mode or ask IT to allow/sign the executable.

## Recommended next steps

1. Test v9 on Windows with and without Claude Desktop installed.
2. Test with several Canvas exports from different course types.
3. If managed computers block the unsigned portable executable, add code signing or an IT-deployed MSI.
4. Add optional AI chat inside the local browser UI.
5. Add a Claude Desktop `.mcpb` extension package later for the cleanest Claude install experience.

## One-line Windows installer

Recommended (window stays open on managed PCs):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command "iex (irm 'https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1')"
```

Repo: `digaocoite/canvasmcplocal`. See `ONE_LINE_INSTALL.md` for details.
