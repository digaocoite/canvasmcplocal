# DELETE AFTER SETUP — CoursePack One-Line Installer Instructions

This file is a temporary setup handoff for an AI assistant or developer working on the CoursePack Local project. After the GitHub one-line installer is working and tested, delete this file from the project/repository.

## Goal

Make CoursePack Local installable on Windows with a one-line PowerShell command like:

```powershell
irm https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1 | iex
```

The installer should:

1. Download the latest portable Windows release ZIP from GitHub Releases.
2. Install it into the user folder, not `C:\Program Files`.
3. Avoid admin privileges.
4. Create Desktop and Start Menu shortcuts if possible.
5. Start CoursePack Local and open the browser when possible.
6. Do **not** auto-connect CoursePack to Claude Desktop during install. Claude connection should happen later from inside the CoursePack web UI after the user converts a course.
7. Show clear status messages so the user knows what is happening.

## Starting project file

Use the latest CoursePack package, currently named something like:

```text
coursepack_mvp_web_mcp_v7.zip
```

Unzip it before working.

Expected project features already present:

- `install.ps1`
- `Build Windows Portable App.bat`
- `Start CoursePack Local.bat`
- `Connect CoursePack to Claude.bat`
- local web app
- converter
- MCP server
- Claude connector logic

## Step 1 — Create or choose the GitHub repository

Create a repository, for example:

```text
OWNER/coursepack
```

Recommended repo name:

```text
coursepack
```

Upload/commit the CoursePack project files to the repo.

Important: do not commit generated build artifacts such as `.venv`, `dist`, `build`, `__pycache__`, temporary course outputs, uploaded Canvas exports, or user course data.

Recommended `.gitignore` entries:

```gitignore
.venv/
build/
dist/
__pycache__/
*.pyc
*.pyo
*.spec
CoursePackLocal/
coursepack_output*/
converted-course*/
uploads/
workspace/
*.imscc
*.zip
!coursepack-local-portable-win64.zip
```

## Step 2 — Edit `install.ps1`

Open `install.ps1` and find the placeholder repo line. It may look like this:

```powershell
$DefaultRepo = "YOUR_GITHUB_USERNAME/coursepack"
```

Replace it with the actual GitHub repo, for example:

```powershell
$DefaultRepo = "OWNER/coursepack"
```

Make sure the script is designed to install into:

```powershell
$env:LOCALAPPDATA\CoursePackLocal\app
```

Do not install into:

```text
C:\Program Files
```

because that usually requires admin privileges.

The installer should download a release asset named:

```text
coursepack-local-portable-win64.zip
```

or whatever exact asset name the script expects. The asset name in the script and the GitHub Release must match.

## Step 3 — Build the Windows portable app

On a Windows computer, run:

```text
Build Windows Portable App.bat
```

This should create a portable build under something like:

```text
dist\CoursePack Local\
```

or produce a ZIP directly.

If it does not create a ZIP automatically, manually ZIP the contents of the portable app folder. The ZIP should contain the runnable app and helper scripts, not a nested unrelated parent folder.

The final ZIP uploaded to GitHub Releases should be named:

```text
coursepack-local-portable-win64.zip
```

## Step 4 — Create a GitHub Release

Create a release in GitHub.

Recommended tag:

```text
v0.1.0
```

Recommended release title:

```text
CoursePack Local v0.1.0
```

Upload the portable app ZIP as a release asset:

```text
coursepack-local-portable-win64.zip
```

The one-line installer depends on this release asset.

## Step 5 — Commit and push `install.ps1`

Make sure `install.ps1` exists in the root of the repository on the default branch, usually `main`.

The raw URL should work in a browser:

```text
https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1
```

Replace `OWNER/REPO` with the actual repo.

## Step 6 — Test the one-line installer

On a Windows test machine, open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1 | iex
```

Expected behavior:

1. PowerShell downloads the installer script.
2. Installer shows status messages.
3. Installer downloads the latest release ZIP.
4. Installer extracts CoursePack to `%LOCALAPPDATA%\CoursePackLocal\app`.
5. Installer creates Desktop and Start Menu shortcuts if possible.
6. Installer starts CoursePack Local and opens the local browser page when possible.
7. Browser opens at:

```text
http://127.0.0.1:3333
```

8. Installer should **not** attempt to configure Claude MCP access during install.
9. The installer should tell the user: convert a course first, then click Claude Desktop > Connect CoursePack to Claude Desktop inside the CoursePack app.

## Step 7 — Test CoursePack itself

Use a small Canvas `.imscc` export.

Test:

- upload `.imscc`
- convert course
- view course dashboard
- view conversion report
- search course
- download converted Markdown ZIP
- verify skipped files are logged instead of crashing conversion

Expected behavior: images, audio, video, and unsupported/large files should be skipped and logged.

## Step 8 — Test Claude Desktop connection if available

If Claude Desktop is installed:

1. In CoursePack, click the Claude connection button.
2. Confirm the page immediately shows a progress message like “Starting Claude connection...” or “Connecting...”.
3. Confirm it does not allow repeated clicks while connecting.
4. Confirm it reports success, already connected, or a clear error.
5. Fully quit Claude Desktop.
6. Reopen Claude Desktop.
7. Ask Claude something like:

```text
Use CoursePack to list my converted courses.
```

If Claude sees the CoursePack tools, the MCP connection works.

If it fails, inspect Claude config:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

The config should contain a `coursepack` entry under `mcpServers`.

## Step 9 — Make README instructions simple

Update the README so normal users see this first:

```powershell
irm https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1 | iex
```

Then include safer/manual options:

```powershell
irm https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1 -OutFile install.ps1
notepad install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Also mention:

- CoursePack runs locally.
- Canvas exports are converted on the user’s computer.
- Images/audio/video are skipped by default.
- Claude Desktop is optional.
- AI chat requires a configured AI provider/API key or future university endpoint.

## Step 10 — Delete this file

After everything works:

1. Delete this file from the project/repository:

```text
DELETE_AFTER_SETUP_CoursePack_OneLine_Installer_Instructions.md
```

2. Commit the deletion:

```bash
git rm DELETE_AFTER_SETUP_CoursePack_OneLine_Installer_Instructions.md
git commit -m "Remove temporary setup instructions"
git push
```

If this file was never committed, simply delete it from the local folder.

## Final success checklist

The setup is complete only when all of these are true:

- [ ] `install.ps1` is in the root of the GitHub repo.
- [ ] `install.ps1` has the real `OWNER/REPO` value.
- [ ] A GitHub Release exists.
- [ ] The release contains `coursepack-local-portable-win64.zip` or the exact asset name expected by `install.ps1`.
- [ ] The one-line command installs CoursePack without admin privileges.
- [ ] CoursePack opens at `http://127.0.0.1:3333`.
- [ ] A Canvas `.imscc` file converts successfully.
- [ ] Skipped files are logged instead of causing failure.
- [ ] Claude Desktop connection is optional, user-triggered from the web UI, and not run automatically by the installer.
- [ ] This temporary instruction file has been deleted.
