Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$repo = Join-Path $root "upstream\agent-governance-toolkit"
$harness = Join-Path $root "harness\run_experiments.py"
$outputDirectory = Join-Path $root "evidence\runtime-output"
$outputLog = Join-Path $outputDirectory "boundary-demo.jsonl"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $repo)) {
    throw "Setup is incomplete. Run .\setup_demo.ps1 first."
}

$env:AGT_REPO = $repo
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
Set-Content -LiteralPath $outputLog -Value $null
$env:AGT_OUTPUT_LOG = $outputLog

$experiments = [ordered]@{
    "01" = "Governed email allow"
    "02" = "External recipient deny"
    "03" = "Approval resolution boundary"
    "04" = "Policy failure behavior"
    "05-create" = "Pending approval before restart"
    "05-inspect" = "Restart persistence inspection"
    "06" = "Approval identity and changed arguments"
    "07" = "Direct-call bypass"
}
foreach ($experiment in $experiments.GetEnumerator()) {
    $env:AGT_EXPERIMENT = $experiment.Key
    Write-Host "`n=== Experiment $($experiment.Key) - $($experiment.Value) ===" -ForegroundColor Cyan
    & $python $harness $experiment.Key
    if ($LASTEXITCODE -ne 0) {
        throw "Boundary experiment $($experiment.Key) failed."
    }
}

Write-Host "Boundary path complete. The harness used the curated email policy and demonstrates host/application responsibilities, not native evaluator behavior." -ForegroundColor Green
Write-Host "Raw JSON evidence: $outputLog" -ForegroundColor DarkGray
