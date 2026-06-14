<#
CoursePack Local one-line installer for Windows.

Recommended one-line command after you publish this file to GitHub:

  irm https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1 | iex

Before publishing, edit $DefaultRepo below to your real GitHub repo, for example:

  $DefaultRepo = "digaocoite/canvasmcplocal"

This installer expects your GitHub latest Release to include a portable Windows ZIP asset
created by Build Windows Portable App.bat. The asset name should contain one of:

  coursepack-local-portable
  CoursePackLocal
  CoursePack-Local

It installs into the current user's profile, so admin rights should not be needed.

v8 installer behavior:
- Does NOT auto-connect Claude during installation.
- Starts CoursePack Local after install and opens http://127.0.0.1:3333 when possible.
- Creates a Desktop shortcut and a Start Menu shortcut for later use.
- Tells the user to connect Claude from inside CoursePack after converting a course.
#>

$ErrorActionPreference = "Stop"

$LogDir = Join-Path $env:LOCALAPPDATA "CoursePackLocal"
$LogFile = Join-Path $LogDir "install-last.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
try { Start-Transcript -Path $LogFile -Force | Out-Null } catch {}

# TODO: Change this before publishing to GitHub.
$DefaultRepo = "digaocoite/canvasmcplocal"

$Repo = if ($env:COURSEPACK_REPO) { $env:COURSEPACK_REPO } else { $DefaultRepo }
$InstallRoot = Join-Path $env:LOCALAPPDATA "CoursePackLocal"
$InstallDir = Join-Path $InstallRoot "app"
$TempDir = Join-Path $env:TEMP ("coursepack-install-" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempDir "coursepack.zip"
$LocalUrl = "http://127.0.0.1:3333"
$HealthUrl = "$LocalUrl/api/health"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Wait-ForEnter($Prompt = "Press any key to close this window") {
    if ($env:COURSEPACK_INSTALL_NO_PAUSE -eq "1") { return }
    Write-Host ""
    Write-Host $Prompt -ForegroundColor Gray
    Write-Host "Install log saved to: $LogFile" -ForegroundColor DarkGray
    Write-Host ""
    # Read-Host often fails when the script was piped in via: irm ... | iex
    cmd /c pause | Out-Null
}

function Get-LatestReleaseAssetUrl($RepoName) {
    if ($RepoName -match "YOUR_GITHUB_USERNAME") {
        throw "Edit install.ps1 first: set `$DefaultRepo to your real GitHub repo, like 'digaocoite/canvasmcplocal'."
    }

    $ApiUrl = "https://api.github.com/repos/$RepoName/releases/latest"
    Write-Step "Checking latest GitHub release: $RepoName"
    $release = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "User-Agent" = "CoursePackLocalInstaller" }

    if (-not $release.assets -or $release.assets.Count -eq 0) {
        throw "No release assets were found. Create a GitHub Release and attach the portable Windows ZIP."
    }

    $asset = $release.assets | Where-Object {
        $_.name -match "(?i)(coursepack[-_ ]?local[-_ ]?portable|coursepacklocal|coursepack[-_ ]?local).*\.zip$"
    } | Select-Object -First 1

    if (-not $asset) {
        $names = ($release.assets | ForEach-Object { $_.name }) -join ", "
        throw "Could not find a CoursePack portable ZIP asset. Release assets found: $names"
    }

    Write-Ok "Found release asset: $($asset.name)"
    return $asset.browser_download_url
}

function Find-CoursePackAppFolder($Root) {
    $candidates = Get-ChildItem -Path $Root -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "CoursePack Local.exe" -or $_.Name -eq "Start CoursePack Local.bat"
    }

    if (-not $candidates -or $candidates.Count -eq 0) {
        throw "Downloaded ZIP did not contain CoursePack Local.exe or Start CoursePack Local.bat."
    }

    # Prefer the folder containing the executable.
    $exe = $candidates | Where-Object { $_.Name -eq "CoursePack Local.exe" } | Select-Object -First 1
    if ($exe) { return $exe.Directory.FullName }

    return ($candidates | Select-Object -First 1).Directory.FullName
}

function New-Shortcut($TargetPath, $ShortcutPath, $WorkingDirectory) {
    try {
        $shortcutDir = Split-Path -Parent $ShortcutPath
        if ($shortcutDir -and !(Test-Path $shortcutDir)) {
            New-Item -ItemType Directory -Force -Path $shortcutDir | Out-Null
        }
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($ShortcutPath)
        $shortcut.TargetPath = $TargetPath
        $shortcut.WorkingDirectory = $WorkingDirectory
        $shortcut.Save()
        Write-Ok "Created shortcut: $ShortcutPath"
    } catch {
        Write-Warn "Could not create shortcut: $($_.Exception.Message)"
    }
}

function Test-CoursePackRunning() {
    try {
        $result = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
        return ($null -ne $result -and $result.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Start-CoursePack($StartBat, $ExePath, $InstallDir) {
    $priorErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    Write-Step "Starting CoursePack Local"
    Write-Host "First launch can take 1-2 minutes on university/managed PCs (security scan, unpack)." -ForegroundColor Yellow
    try {
        if (Test-Path $StartBat) {
            # Launch through cmd.exe so .bat startup works consistently from PowerShell/one-line installs.
            Start-Process -FilePath $env:ComSpec -ArgumentList @('/c', 'start', '"CoursePack Local"', ('"' + $StartBat + '"')) -WorkingDirectory $InstallDir | Out-Null
            Write-Ok "Started CoursePack using Start CoursePack Local.bat"
        } elseif (Test-Path $ExePath) {
            Start-Process -FilePath $ExePath -WorkingDirectory $InstallDir | Out-Null
            Write-Ok "Started CoursePack executable"
        } else {
            Write-Warn "Start file was not found. Use the installed folder manually: $InstallDir"
            return
        }
    } catch {
        Write-Warn "CoursePack did not start automatically: $($_.Exception.Message)"
        Write-Warn "Try the Desktop shortcut named 'CoursePack Local'."
        return
    }

    # Optional: wait for the local web server. Install already succeeded if we reach here.
    $maxWaitSec = 90
    for ($i = 1; $i -le $maxWaitSec; $i++) {
        Start-Sleep -Seconds 1
        if (Test-CoursePackRunning) {
            Write-Ok "CoursePack Local is running at $LocalUrl"
            try { Start-Process $LocalUrl | Out-Null } catch {}
            $ErrorActionPreference = $priorErrorAction
            return
        }
        if ($i % 15 -eq 0) {
            Write-Host "Still waiting for CoursePack to respond... ($i/$maxWaitSec seconds)" -ForegroundColor DarkGray
        }
    }

    Write-Warn "CoursePack was installed, but http://127.0.0.1:3333 did not respond within $maxWaitSec seconds."
    Write-Warn "Open the Desktop shortcut 'CoursePack Local' and wait for its window to finish starting."
    Write-Warn "If Windows blocks the app, contact IT or run from a personal (non-UM) profile."
    $ErrorActionPreference = $priorErrorAction
}

try {
    $script:InstallFailed = $false
    Write-Host "CoursePack Local installer" -ForegroundColor White
    Write-Host "This installs only for the current user. No admin rights should be needed."

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

    $DownloadUrl = if ($env:COURSEPACK_DOWNLOAD_URL) {
        $env:COURSEPACK_DOWNLOAD_URL
    } else {
        Get-LatestReleaseAssetUrl -RepoName $Repo
    }

    Write-Step "Downloading CoursePack Local"
    Write-Host $DownloadUrl
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
    Write-Ok "Downloaded installer ZIP"

    Write-Step "Extracting files"
    $ExtractDir = Join-Path $TempDir "extracted"
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
    $AppFolder = Find-CoursePackAppFolder -Root $ExtractDir
    Write-Ok "Found app folder: $AppFolder"

    Write-Step "Installing to user folder"
    if (Test-Path $InstallDir) {
        $BackupDir = Join-Path $InstallRoot ("app-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        Move-Item -Path $InstallDir -Destination $BackupDir -Force
        Write-Ok "Previous app backed up to: $BackupDir"
    }
    Copy-Item -Path $AppFolder -Destination $InstallDir -Recurse -Force
    Write-Ok "Installed to: $InstallDir"

    $StartBat = Join-Path $InstallDir "Start CoursePack Local.bat"
    $ExePath = Join-Path $InstallDir "CoursePack Local.exe"

    Write-Step "Creating shortcuts"
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $Programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $ShortcutTarget = if (Test-Path $StartBat) { $StartBat } elseif (Test-Path $ExePath) { $ExePath } else { $null }
    if ($ShortcutTarget) {
        New-Shortcut -TargetPath $ShortcutTarget -ShortcutPath (Join-Path $Desktop "CoursePack Local.lnk") -WorkingDirectory $InstallDir
        New-Shortcut -TargetPath $ShortcutTarget -ShortcutPath (Join-Path $Programs "CoursePack Local.lnk") -WorkingDirectory $InstallDir
    } else {
        Write-Warn "Start file was not found, but files were installed."
    }

    Write-Step "Claude Desktop connection"
    Write-Host "Claude is not connected automatically during install." -ForegroundColor Yellow
    Write-Host "After you convert a course, open CoursePack and click 'Claude Desktop' > 'Connect CoursePack to Claude Desktop'."

    Start-CoursePack -StartBat $StartBat -ExePath $ExePath -InstallDir $InstallDir

    Write-Host ""
    Write-Ok "CoursePack Local installed."
    Write-Host "Use it now: open the 'CoursePack Local' shortcut, then $LocalUrl"
    Write-Host "Use it later: Desktop or Start Menu shortcut 'CoursePack Local'."
    Write-Host "Installed files: $InstallDir"
    Write-Host "Your converted courses are saved under: $InstallRoot"
}
catch {
    Write-Host ""
    Write-Host "CoursePack install failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Tip: make sure the GitHub Release has a portable Windows ZIP asset attached." -ForegroundColor Yellow
    $script:InstallFailed = $true
}
finally {
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    try { Stop-Transcript | Out-Null } catch {}
    if ($script:InstallFailed) {
        Wait-ForEnter "Install failed. Press any key to close this window"
        exit 1
    }
    Wait-ForEnter "Install finished. Press any key to close this window"
}
