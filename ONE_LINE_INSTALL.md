# One-line installer setup

After you push this project to GitHub and build a Windows portable release ZIP, users can install CoursePack with one PowerShell line.

## 1. Edit `install.ps1`

Change this line:

```powershell
$DefaultRepo = "digaocoite/canvasmcplocal"
```

(Already set in `install.ps1` for this repo.)

## 2. Build the portable app on Windows

Run:

```text
Build Windows Portable App.bat
```

This creates a portable ZIP similar to:

```text
coursepack-local-portable-win32.zip
```

## 3. Create a GitHub Release

On GitHub:

1. Go to Releases.
2. Create a new release, such as `v0.1.0`.
3. Upload the portable ZIP created by the build script.
4. Publish the release.

The ZIP asset name should contain one of these phrases so the installer can find it:

```text
coursepack-local-portable
CoursePackLocal
CoursePack-Local
```

Recommended name:

```text
coursepack-local-portable-win64.zip
```

## 4. One-line install command

Users can run:

```powershell
irm https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1 | iex
```

## What the installer does

- Downloads the latest GitHub Release ZIP.
- Installs CoursePack into `%LOCALAPPDATA%\CoursePackLocal\app`.
- Creates a desktop shortcut.
- Attempts to connect CoursePack to Claude Desktop.
- Starts CoursePack Local.
- Does not require admin rights.

## Advanced override commands

Use a different repo without editing the script:

```powershell
$env:COURSEPACK_REPO="digaocoite/canvasmcplocal"; irm https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1 | iex
```

Use a direct ZIP URL:

```powershell
$env:COURSEPACK_DOWNLOAD_URL="https://example.com/coursepack-local-portable-win64.zip"; irm https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1 | iex
```
