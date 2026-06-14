# One-line installer setup

After you push this project to GitHub and build a Windows portable release ZIP, users can install CoursePack with one PowerShell line.

## 1. Edit `install.ps1`

Change this line:

```powershell
$DefaultRepo = "YOUR_GITHUB_USERNAME/coursepack"
```

to your real GitHub repository, for example:

```powershell
$DefaultRepo = "diogenes/coursepack"
```

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
irm https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/coursepack/main/install.ps1 | iex
```

Example:

```powershell
irm https://raw.githubusercontent.com/diogenes/coursepack/main/install.ps1 | iex
```

## What the installer does

- Downloads the latest GitHub Release ZIP.
- Installs CoursePack into `%LOCALAPPDATA%\CoursePackLocal\app`.
- Creates Desktop and Start Menu shortcuts.
- Starts CoursePack Local and opens the browser when possible.
- Does **not** automatically connect Claude Desktop during installation. Users connect Claude later from inside CoursePack after converting a course.
- Does not require admin rights.

## Advanced override commands

Use a different repo without editing the script:

```powershell
$env:COURSEPACK_REPO="yourname/coursepack"; irm https://raw.githubusercontent.com/yourname/coursepack/main/install.ps1 | iex
```

Use a direct ZIP URL:

```powershell
$env:COURSEPACK_DOWNLOAD_URL="https://example.com/coursepack-local-portable-win64.zip"; irm https://raw.githubusercontent.com/yourname/coursepack/main/install.ps1 | iex
```


## After first install

Users should not run the one-line command every time. After installation, they open CoursePack with:

```text
Desktop shortcut: CoursePack Local
Start Menu shortcut: CoursePack Local
```

If the browser does not open automatically after launching CoursePack, open:

```text
http://127.0.0.1:3333
```

## Claude Desktop connection

The installer intentionally does not auto-connect Claude Desktop. Recommended flow:

```text
1. Install CoursePack.
2. Open CoursePack.
3. Convert a Canvas export.
4. Click Claude Desktop > Connect CoursePack to Claude Desktop.
5. Fully quit and reopen Claude Desktop.
```
