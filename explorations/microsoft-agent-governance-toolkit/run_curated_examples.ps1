[CmdletBinding()]
param(
    [ValidateSet("email", "support", "all")]
    [string]$Example = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Join-Path $root "upstream\agent-governance-toolkit"
$python = Join-Path $root ".venv\Scripts\python.exe"
$email = Join-Path $root "examples\acs-email-tool"
$support = Join-Path $root "examples\support_agent\app\run_demo.py"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $repo)) {
    throw "Setup is incomplete. Run .\setup_demo.ps1 first."
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

if ($Example -in @("email", "all")) {
    if (-not (Test-Path -LiteralPath $email)) {
        throw "The curated ACS email example was not found."
    }
    Write-Host "Running curated ACS email example..." -ForegroundColor Cyan
    Push-Location $email
    try {
        & $python -m pytest -q -p no:cacheprovider
        if ($LASTEXITCODE -ne 0) {
            throw "The curated email example tests failed."
        }
        & $python run.py
        if ($LASTEXITCODE -ne 0) {
            throw "The curated email example failed."
        }
    } finally {
        Pop-Location
    }
}

if ($Example -in @("support", "all")) {
    if (-not (Test-Path -LiteralPath $support)) {
        throw "The curated support-agent example was not found."
    }
    Write-Host "Running curated support-agent example..." -ForegroundColor Cyan
    & $python $support
    if ($LASTEXITCODE -ne 0) {
        throw "The curated support-agent example failed."
    }
}

Write-Host "Curated examples complete." -ForegroundColor Green
