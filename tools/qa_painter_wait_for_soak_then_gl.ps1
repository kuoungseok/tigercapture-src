param(
    [Parameter(Mandatory = $true)]
    [int]$SoakProcessId,
    [int]$SettleSeconds = 10,
    [int]$Cycles = 3,
    [int]$StrokesPerCycle = 100
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$diagnosticPath = Join-Path $PSScriptRoot "qa_painter_gl_context_churn.py"

Wait-Process -Id $SoakProcessId -ErrorAction SilentlyContinue
Start-Sleep -Seconds ([Math]::Max(0, $SettleSeconds))

& $pythonPath $diagnosticPath `
    --cycles ([Math]::Max(1, $Cycles)) `
    --strokes-per-cycle ([Math]::Max(1, $StrokesPerCycle))
exit $LASTEXITCODE
