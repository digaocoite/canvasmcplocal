# Next upload — rename to **Canvas CoursePack Local**

When the next CoursePack zip is uploaded to aurora (`/home/dio/apps/canvasmcplocal/`), apply this rebrand **before** pushing to GitHub and cutting a release.

## Display name (target)

**Canvas CoursePack Local**

Use everywhere users see the product name (installer text, web UI title, shortcuts, README, Help page).

## Keep unchanged unless intentional

| Item | Current | Note |
|------|---------|------|
| GitHub repo | `digaocoite/canvasmcplocal` | OK as-is |
| MCP server id in Claude config | `coursepack` | Changing breaks existing Claude setups |
| Data folder | `%LOCALAPPDATA%\CoursePackLocal` | Renaming loses user data unless migrated |
| Portable ZIP asset | `coursepack-local-portable-win64.zip` | Installer matches on filename pattern |

## Files to update (checklist)

- [ ] `README.md` — title and headings
- [ ] `install.ps1` — banner messages, shortcut names (`Canvas CoursePack Local.lnk`)
- [ ] `coursepack/webapp.py` — `<title>`, nav, Help page
- [ ] `build_portable.py` — PyInstaller `APP_NAME`, `.exe` name, batch file text
- [ ] `Start CoursePack Local.bat` → consider `Start Canvas CoursePack Local.bat`
- [ ] `Connect CoursePack to Claude.bat`, uninstall scripts — user-visible strings
- [ ] `Install-CoursePack.cmd` — window title
- [ ] `ONE_LINE_INSTALL.md` — user-facing name

## Optional (bigger change)

- Rename exe: `CoursePack Local.exe` → `Canvas CoursePack Local.exe` (update Claude MCP `command` path in configs)
- Migrate `%LOCALAPPDATA%\CoursePackLocal` → `CanvasCoursePackLocal` with one-time move in installer

## Agent reminder

On next upload, read this file first and rename user-facing strings to **Canvas CoursePack Local**, then deploy as usual (merge → GitHub → CI build → release).
