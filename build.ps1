# TigerCapture build script
# Usage:
#   .\build.ps1              # PyInstaller only (dist\TigerCapture)
#   .\build.ps1 -NSIS        # PyInstaller + NSIS (installer_output\TigerCapture-Setup-*.exe)
#   .\build.ps1 -Installer   # alias for -NSIS
#   .\build.ps1 -InnoSetup   # PyInstaller + Inno Setup
#   .\build.ps1 -Clean       # clean build artifacts first

param(
    [switch]$Installer,
    [switch]$NSIS,
    [switch]$InnoSetup,
    [switch]$Clean
)

if ($Installer) { $NSIS = $true }

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "venv not found at $python. Run `py -3.13 -m venv .venv` and install requirements first."
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

# 2. PyInstaller build
Write-Host "[pyinstaller] building dist\TigerCapture..." -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm (Join-Path $root "TigerCapture.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exePath = Join-Path $root "dist\TigerCapture\TigerCapture.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Build failed: $exePath missing."
    exit 1
}
Write-Host "[pyinstaller] OK: $exePath" -ForegroundColor Green

# 3a. NSIS installer (preferred)
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
    Write-Host "[nsis] building installer via $makensis" -ForegroundColor Cyan
    & $makensis (Join-Path $root "installer.nsi")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "[nsis] OK: installer_output\TigerCapture-Setup-*.exe" -ForegroundColor Green
}

# 3b. Inno Setup installer (alternative)
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
    Write-Host "[iscc] OK: installer_output\TigerCapture-Setup-*.exe" -ForegroundColor Green
}

Write-Host "Done." -ForegroundColor Green
