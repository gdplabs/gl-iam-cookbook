Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Join-Path $root "upstream\agent-governance-toolkit"
$example = Join-Path $repo "examples\acs-email-tool"
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $example)) {
    throw "Setup is incomplete, or the upstream example was not found. Run .\setup_demo.ps1 first."
}

$opaPath = $env:OPA_EXE
if (-not $opaPath) {
    $opaCommand = Get-Command opa -ErrorAction SilentlyContinue
    if ($opaCommand) {
        $opaPath = $opaCommand.Source
    }
}
if (-not $opaPath -or -not (Test-Path -LiteralPath $opaPath)) {
    throw "OPA was not found. Put opa.exe on PATH or set OPA_EXE to its absolute path."
}
$env:Path = "$(Split-Path -Parent $opaPath);$env:Path"
$env:ACS_OPA_PATH = $opaPath

Write-Host "Running the unmodified upstream ACS email example (from the pinned clone, not the curated copy)..." -ForegroundColor Cyan
Push-Location $example
try {
    & $python -m pytest -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) {
        throw "The upstream email example tests failed."
    }
    & $python run.py
    if ($LASTEXITCODE -ne 0) {
        throw "The upstream email example failed."
    }
} finally {
    Pop-Location
}

Write-Host "Upstream path complete: this ran Microsoft's own example file, unmodified, straight from the pinned checkout." -ForegroundColor Green
