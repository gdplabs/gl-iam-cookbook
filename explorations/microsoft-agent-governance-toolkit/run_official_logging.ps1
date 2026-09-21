Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$repo = Join-Path $root "upstream\agent-governance-toolkit"
$harness = Join-Path $root "harness\run_experiments.py"
$outputDirectory = Join-Path $root "evidence\runtime-output"
$outputLog = Join-Path $outputDirectory "official-logging.jsonl"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $repo)) {
    throw "Setup is incomplete. Run .\setup_demo.ps1 first."
}

$env:AGT_REPO = $repo
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
Set-Content -LiteralPath $outputLog -Value $null
$env:AGT_OUTPUT_LOG = $outputLog

$experiments = [ordered]@{
    "01"           = "Governed email allow"
    "01-transform" = "Governed email transform"
    "02"           = "External recipient deny"
}
foreach ($experiment in $experiments.GetEnumerator()) {
    $env:AGT_EXPERIMENT = $experiment.Key
    Write-Host "`n=== Experiment $($experiment.Key) - $($experiment.Value) ===" -ForegroundColor Cyan
    & $python $harness $experiment.Key
    if ($LASTEXITCODE -ne 0) {
        throw "Official-path experiment $($experiment.Key) failed."
    }
}

Write-Host "`nOfficial path complete: allow, transform and deny observed through AgentControl.run_tool (pre- and post-tool call)." -ForegroundColor Green
Write-Host "This uses the curated email policy through the host-orchestration contract with a substitute runtime, not the native evaluator." -ForegroundColor Green
Write-Host "Native evaluator behavior is proven separately by .\test_policy_engine_sdk.ps1 and .\run_upstream_example.ps1." -ForegroundColor Green
Write-Host "Raw JSON evidence: $outputLog" -ForegroundColor DarkGray
