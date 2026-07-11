# TigerCapture build script
# Usage:
#   .\build.ps1              # PyInstaller only (dist\TigerCapture)
#   .\build.ps1 -NSIS        # PyInstaller + NSIS (installer_output\TigerCapture-Setup-*.exe)
#   .\build.ps1 -Installer   # alias for -NSIS
#   .\build.ps1 -InnoSetup   # PyInstaller + Inno Setup (installer_output\TigerCapture-InnoSetup-*.exe)
#   .\build.ps1 -Clean       # clean build artifacts first
#   .\build.ps1 -Version 1.3.0 -NSIS   # explicit version override

param(
    [switch]$Installer,
    [switch]$NSIS,
    [switch]$InnoSetup,
    [switch]$Clean,
    [string]$Version = ""
)

if ($Installer) { $NSIS = $true }

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

# Parse version from version_info.txt if not supplied explicitly
if (-not $Version) {
    $viPath = Join-Path $root "version_info.txt"
    if (Test-Path $viPath) {
        $match = Select-String -Path $viPath -Pattern "filevers=\((\d+),\s*(\d+),\s*(\d+)" | Select-Object -First 1
        if ($match) {
            $g = $match.Matches[0].Groups
            $Version = "$($g[1].Value).$($g[2].Value).$($g[3].Value)"
        }
    }
}
if (-not $Version) { $Version = "1.3.0" }
$vParts = $Version.Split('.')
$vMajor = if ($vParts.Count -gt 0) { $vParts[0] } else { "1" }
$vMinor = if ($vParts.Count -gt 1) { $vParts[1] } else { "0" }
$vBuild = if ($vParts.Count -gt 2) { $vParts[2] } else { "0" }
Write-Host "[version] $Version" -ForegroundColor Cyan

if (-not (Test-Path $python)) {
    Write-Error "venv not found at $python. Run `py -3.13 -m venv .venv` and install requirements first."
    exit 1
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller is not installed in .venv. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
    exit 1
}

if ($Clean) {
    Write-Host "[clean] removing dist, build, installer_output..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force -ErrorAction Ignore (Join-Path $root "dist")
    Remove-Item -Recurse -Force -ErrorAction Ignore (Join-Path $root "build")
    Remove-Item -Recurse -Force -ErrorAction Ignore (Join-Path $root "installer_output")
}

# 1. Icon — checked into resources/tigercapture.ico (extracted from the
#    reference pixel-art tiger). The legacy ``make_icon.py`` regenerator
#    is no longer wired in here; it produced a generic placeholder that
#    would overwrite the brand icon on every build.
$icoPath = Join-Path $root "resources\tigercapture.ico"
if (-not (Test-Path $icoPath)) {
    Write-Error "Missing $icoPath — commit it before building."
    exit 1
}

# 2. Native worker build. The PyInstaller spec picks this binary up from
#    native\tigercapture_worker\target\release and places it under
#    bundled\native in the frozen app.
$cargo = Get-Command cargo.exe -ErrorAction Ignore
$workerDir = Join-Path $root "native\tigercapture_worker"
$workerExe = Join-Path $workerDir "target\release\tigercapture-worker.exe"
if ($cargo -and (Test-Path $workerDir)) {
    Write-Host "[cargo] building native worker..." -ForegroundColor Cyan
    Push-Location $workerDir
    try {
        & $cargo.Source build --release
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
    if (-not (Test-Path $workerExe)) {
        Write-Error "Native worker build finished but $workerExe is missing."
        exit 1
    }
    Write-Host "[cargo] OK: $workerExe" -ForegroundColor Green
} else {
    Write-Warning "cargo.exe not found; building without bundled native worker."
}

# 3. PyInstaller build
Write-Host "[pyinstaller] building dist\TigerCapture..." -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm (Join-Path $root "TigerCapture.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exePath = Join-Path $root "dist\TigerCapture\TigerCapture.exe"
$studioExePath = Join-Path $root "dist\TigerCapture\TigerStudio.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Build failed: $exePath missing."
    exit 1
}
if (-not (Test-Path $studioExePath)) {
    Write-Error "Build failed: $studioExePath missing."
    exit 1
}
Write-Host "[pyinstaller] OK: $exePath" -ForegroundColor Green
Write-Host "[pyinstaller] OK: $studioExePath" -ForegroundColor Green

# 3b. Root launcher
# PyInstaller uses an onedir layout, so copying dist\TigerCapture\TigerCapture.exe
# to the repository root would break its _internal lookup. Build a tiny native
# launcher instead: it starts .venv\Scripts\pythonw.exe main.py in a source
# checkout, then falls back to the frozen app when no source venv is present.
$launcherSource = Join-Path $root "tools\windows_launcher\TigerCaptureLauncher.cs"
$launcherExe = Join-Path $root "TigerCapture.exe"
$studioLauncherExe = Join-Path $root "TigerStudio.exe"
if (Test-Path $launcherSource) {
    $csc = $null
    $cscCandidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    foreach ($candidate in $cscCandidates) {
        if (Test-Path $candidate) { $csc = $candidate; break }
    }
    if (-not $csc) {
        $foundCsc = Get-Command csc.exe -ErrorAction Ignore
        if ($foundCsc) { $csc = $foundCsc.Source }
    }
    if ($csc) {
        Write-Host "[launcher] building root TigerCapture.exe..." -ForegroundColor Cyan
        & $csc /nologo /target:winexe /optimize+ /platform:anycpu "/win32icon:$icoPath" /reference:System.Windows.Forms.dll "/out:$launcherExe" "$launcherSource"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "[launcher] OK: $launcherExe" -ForegroundColor Green
        Write-Host "[launcher] building root TigerStudio.exe..." -ForegroundColor Cyan
        & $csc /nologo /target:winexe /optimize+ /platform:anycpu "/win32icon:$icoPath" /reference:System.Windows.Forms.dll "/out:$studioLauncherExe" "$launcherSource"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "[launcher] OK: $studioLauncherExe" -ForegroundColor Green
    } else {
        Write-Warning "csc.exe not found; root TigerCapture.exe launcher was not rebuilt."
    }
}

# 4a. NSIS installer (preferred)
if ($NSIS) {
    $makensis = $null
    $candidates = @(
        "C:\Program Files (x86)\NSIS\makensis.exe",
        "C:\Program Files\NSIS\makensis.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $makensis = $c; break }
    }
    if (-not $makensis) {
        $found = Get-Command makensis.exe -ErrorAction Ignore
        if ($found) { $makensis = $found.Source }
    }
    if (-not $makensis) {
        Write-Error "NSIS (makensis.exe) not found. Install from https://nsis.sourceforge.io/Download"
        exit 1
    }

    New-Item -ItemType Directory -Force (Join-Path $root "installer_output") | Out-Null
    Write-Host "[nsis] building installer via $makensis (v$Version)" -ForegroundColor Cyan
    & $makensis "/DVERSIONMAJOR=$vMajor" "/DVERSIONMINOR=$vMinor" "/DVERSIONBUILD=$vBuild" (Join-Path $root "installer.nsi")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "[nsis] OK: installer_output\TigerCapture-Setup-$Version.exe" -ForegroundColor Green
}

# 4b. Inno Setup installer (alternative)
if ($InnoSetup) {
    $iscc = $null
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $iscc = $c; break }
    }
    if (-not $iscc) {
        $found = Get-Command iscc.exe -ErrorAction Ignore
        if ($found) { $iscc = $found.Source }
    }
    if (-not $iscc) {
        Write-Error "Inno Setup Compiler (ISCC.exe) not found. Install from https://jrsoftware.org/isdl.php"
        exit 1
    }

    Write-Host "[iscc] building installer via $iscc" -ForegroundColor Cyan
    & $iscc (Join-Path $root "installer.iss")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "[iscc] OK: installer_output\TigerCapture-InnoSetup-*.exe" -ForegroundColor Green
}

Write-Host "Done." -ForegroundColor Green
