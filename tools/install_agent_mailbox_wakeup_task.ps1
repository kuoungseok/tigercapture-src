param(
    [string]$TaskName = "TigerStudio-AgentMailboxWakeup",
    [string]$RepoRoot = "",
    [int]$IntervalMinutes = 5,
    [string]$WakeCommand = "",
    [switch]$NoAlwaysWake
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python.exe"
}

$watcher = Join-Path $RepoRoot "tools\agent_mailbox_wakeup.py"
if (-not (Test-Path -LiteralPath $watcher)) {
    throw "Watcher script not found: $watcher"
}

$alwaysArg = if ($NoAlwaysWake) { "" } else { " --always-wake" }
$wakePrefix = ""
if (-not [string]::IsNullOrWhiteSpace($WakeCommand)) {
    $escapedWake = $WakeCommand.Replace("'", "''")
    $wakePrefix = "`$env:CODEX_MAILBOX_WAKE_COMMAND='$escapedWake'; "
}

$command = "$wakePrefix& '$python' '$watcher' --repo-root '$RepoRoot' --once$alwaysArg"
$argument = "-NoProfile -ExecutionPolicy Bypass -Command `"$command`""

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argument -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Poll Tiger Studio agent mailbox and emit Codex wake messages." `
    -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Repo root: $RepoRoot"
Write-Host "Interval minutes: $IntervalMinutes"
Write-Host "Wake command configured: $([bool](-not [string]::IsNullOrWhiteSpace($WakeCommand)))"
