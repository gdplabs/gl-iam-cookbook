Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Join-Path $root "upstream\agent-governance-toolkit"
$sdkPython = Join-Path $repo "policy-engine\sdk\python"
$python = Join-Path $root ".venv\Scripts\python.exe"

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

Write-Host "Validating the policy-engine dependency (native ACS extension + SDK test suite)..." -ForegroundColor Cyan
Push-Location $sdkPython
try {
    & $python -m pytest -q tests -k "not rejects_non_opa_executable" -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) {
        throw "The selected ACS SDK validation failed."
    }
} finally {
    Pop-Location
}

Write-Host "Policy-engine dependency validated: native extension imported and SDK tests passed. The one deselected test expects the POSIX executable /bin/true." -ForegroundColor Green
