param(
    [string]$Manifest = "qa_corpus\actor_corpus_manifest.json",
    [string]$Out = "debugCapture\actor_corpus_regression_full.json",
    [string]$StatusOut = "debugCapture\actor_corpus_status.json",
    [string]$Baseline = "",
    [switch]$UpdateGolden
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root ".venv\Scripts\python.exe"
if (!(Test-Path $python)) {
    $python = "python"
}

$args = @(
    "tools\actor_corpus_regression.py",
    "--manifest", $Manifest,
    "--render",
    "--out", $Out,
    "--status-out", $StatusOut
)
if ($Baseline) {
    $args += @("--baseline", $Baseline)
}
if ($UpdateGolden) {
    $args += "--update-golden"
}

Push-Location $root
try {
    & $python @args
    & $python "tools\actor_golden_manager.py" "--manifest" $Manifest
} finally {
    Pop-Location
}
