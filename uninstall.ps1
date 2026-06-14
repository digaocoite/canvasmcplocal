<#
CoursePack Local user-level uninstaller.
Removes the app installed under %LOCALAPPDATA%\CoursePackLocal and removes shortcuts.
It does not touch Canvas, Claude Desktop, or any original course export files.
#>
$ErrorActionPreference = "Continue"
$InstallRoot = Join-Path $env:LOCALAPPDATA "CoursePackLocal"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "CoursePack Local.lnk"
$StartShortcut = Join-Path (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs") "CoursePack Local.lnk"

Write-Host "CoursePack Local uninstaller" -ForegroundColor White
Write-Host "This removes the local app and converted CoursePack data from this Windows user profile."
$answer = Read-Host "Delete CoursePack Local from this user account? Type YES to continue"
if ($answer -ne "YES") {
    Write-Host "Uninstall cancelled."
    exit 0
}

foreach ($shortcut in @($DesktopShortcut, $StartShortcut)) {
    if (Test-Path $shortcut) {
        Remove-Item $shortcut -Force -ErrorAction SilentlyContinue
        Write-Host "Removed shortcut: $shortcut" -ForegroundColor Green
    }
}

if (Test-Path $InstallRoot) {
    Remove-Item $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $InstallRoot) {
        Write-Host "Could not fully remove $InstallRoot. Close CoursePack Local and run this again." -ForegroundColor Yellow
    } else {
        Write-Host "Removed: $InstallRoot" -ForegroundColor Green
    }
} else {
    Write-Host "CoursePack Local install folder was not found."
}

Write-Host "Done."
