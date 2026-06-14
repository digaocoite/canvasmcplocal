# One-line installer setup

Repo: `digaocoite/canvasmcplocal` — `install.ps1` is already configured.

## Recommended install command (window stays open)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command "iex (irm 'https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1')"
```

Or double-click `Install-CoursePack.cmd` from the repo.

## What the installer does

- Downloads the latest GitHub Release ZIP.
- Installs CoursePack into `%LOCALAPPDATA%\CoursePackLocal\app`.
- Creates Desktop and Start Menu shortcuts (plus Uninstall in Start Menu when available).
- Starts CoursePack and waits up to 90s for `http://127.0.0.1:3333` (non-fatal on slow/managed PCs).
- Writes a log to `%LOCALAPPDATA%\CoursePackLocal\install-last.log`.
- Pauses with **Press any key** before closing (works even when `irm | iex` would close too fast).
- Does **not** auto-connect Claude Desktop during install.
- Does not require admin rights.

## If download fails on campus Wi‑Fi (truncated ZIP)

Download the ZIP manually in a browser:

https://github.com/digaocoite/canvasmcplocal/releases/latest

Then install from the saved file:

```powershell
$env:COURSEPACK_LOCAL_ZIP="C:\Users\ddstk8\Downloads\coursepack-local-portable-win64.zip"
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command "iex (irm 'https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1')"
```

(Change the path to where your browser saved the file.)

## Build new Windows portable (maintainers)

GitHub Actions → **Build Windows portable** → Run workflow, then create a release with `coursepack-local-portable-win64.zip`.

Or on Windows: `Build Windows Portable App.bat`

## After first install

Open CoursePack with the **CoursePack Local** Desktop or Start Menu shortcut — not the one-line installer every time.

```text
http://127.0.0.1:3333
```

## Uninstall

Start Menu → **Uninstall CoursePack Local** (v9+), or run `Uninstall CoursePack Local.bat` from the install folder.
