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
#>

$ErrorActionPreference = "Stop"

# TODO: Change this before publishing to GitHub.
$DefaultRepo = "digaocoite/canvasmcplocal"

$Repo = if ($env:COURSEPACK_REPO) { $env:COURSEPACK_REPO } else { $DefaultRepo }
$InstallRoot = Join-Path $env:LOCALAPPDATA "CoursePackLocal"
$InstallDir = Join-Path $InstallRoot "app"
$TempDir = Join-Path $env:TEMP ("coursepack-install-" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempDir "coursepack.zip"

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

try {
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

    Write-Step "Creating desktop shortcut"
    $Desktop = [Environment]::GetFolderPath("Desktop")
    if (Test-Path $StartBat) {
        New-Shortcut -TargetPath $StartBat -ShortcutPath (Join-Path $Desktop "CoursePack Local.lnk") -WorkingDirectory $InstallDir
    } elseif (Test-Path $ExePath) {
        New-Shortcut -TargetPath $ExePath -ShortcutPath (Join-Path $Desktop "CoursePack Local.lnk") -WorkingDirectory $InstallDir
    } else {
        Write-Warn "Start file was not found, but files were installed."
    }

    Write-Step "Checking Claude Desktop connection"
    if (Test-Path $ExePath) {
        try {
            & $ExePath --connect-claude
            Write-Ok "Claude connector step completed. Fully quit and reopen Claude Desktop."
        } catch {
            Write-Warn "Claude connector did not complete: $($_.Exception.Message)"
            Write-Warn "CoursePack will still work in the browser. You can connect Claude later from the app."
        }
    } else {
        Write-Warn "Packaged executable was not found, so Claude auto-connect was skipped."
    }

    Write-Step "Starting CoursePack Local"
    if (Test-Path $StartBat) {
        Start-Process -FilePath $StartBat -WorkingDirectory $InstallDir
    } elseif (Test-Path $ExePath) {
        Start-Process -FilePath $ExePath -WorkingDirectory $InstallDir
    }

    Write-Host ""
    Write-Ok "CoursePack Local installed."
    Write-Host "Open http://127.0.0.1:3333 if the browser does not open automatically."
    Write-Host "If using Claude Desktop, fully quit and reopen Claude Desktop after installation."
}
catch {
    Write-Host ""
    Write-Host "CoursePack install failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Tip: make sure the GitHub Release has a portable Windows ZIP asset attached." -ForegroundColor Yellow
    exit 1
}
finally {
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
