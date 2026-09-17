Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$repo = Join-Path $root "upstream\agent-governance-toolkit"
$harness = Join-Path $root "harness\run_experiments.py"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $repo)) {
    throw "Setup is incomplete. Run .\setup_demo.ps1 first."
}

$env:AGT_REPO = $repo
foreach ($experiment in @("01", "02", "03", "04", "05-create", "05-inspect", "06", "07")) {
    Write-Host "`n=== Experiment $experiment ===" -ForegroundColor Cyan
    & $python $harness $experiment
    if ($LASTEXITCODE -ne 0) {
        throw "Boundary experiment $experiment failed."
    }
}

Write-Host "Boundary path complete. This custom harness demonstrates host/application responsibilities, not native evaluator behavior." -ForegroundColor Green
