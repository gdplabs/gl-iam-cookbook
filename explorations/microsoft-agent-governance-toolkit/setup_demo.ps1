[CmdletBinding()]
param(
    [string]$AgtCommit = "1a896e70aca8ced2a243d5702cb0359d4ded5c50"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$upstreamRoot = Join-Path $root "upstream"
$repo = Join-Path $upstreamRoot "agent-governance-toolkit"
$policyEngine = Join-Path $repo "policy-engine"
$sdkPython = Join-Path $policyEngine "sdk\python"
$venv = Join-Path $root ".venv"
$cargoTarget = Join-Path $env:LOCALAPPDATA "agt-acs-cargo-target"

foreach ($command in @("git", "py", "rustup")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command '$command' was not found. See README.md prerequisites."
    }
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

Write-Host "[1/6] Fetching the pinned AGT source..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $upstreamRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $repo ".git"))) {
    # AGT contains paths that can exceed the legacy Windows path limit when the
    # cookbook itself is checked out deeply. Apply the setting for the initial
    # checkout, then persist it locally below for repeat runs.
    & git -c core.longpaths=true clone https://github.com/microsoft/agent-governance-toolkit.git $repo
    $cloneExitCode = $LASTEXITCODE
    if ($cloneExitCode -ne 0 -and -not (Test-Path -LiteralPath (Join-Path $repo ".git"))) {
        throw "Failed to clone the AGT repository."
    }
    if ($cloneExitCode -ne 0) {
        Write-Warning "Git created a partial checkout. Continuing with long-path support enabled."
    }
}

$origin = (& git -C $repo remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $origin -notmatch "microsoft/agent-governance-toolkit(?:\.git)?$") {
    throw "The existing upstream/agent-governance-toolkit folder is not the expected Microsoft AGT checkout."
}
& git -C $repo config core.longpaths true
if ($LASTEXITCODE -ne 0) {
    throw "Failed to enable Git long-path support for the AGT checkout."
}
& git -C $repo fetch origin $AgtCommit
if ($LASTEXITCODE -ne 0) {
    throw "Failed to fetch AGT commit $AgtCommit."
}
& git -C $repo checkout --detach $AgtCommit
if ($LASTEXITCODE -ne 0) {
    throw "Failed to check out AGT commit $AgtCommit. Preserve any local edits in the upstream checkout and retry."
}

Write-Host "[2/6] Creating the Python 3.11 environment..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $venv)) {
    & py -3.11 -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python 3.11 virtual environment."
    }
}
$python = Join-Path $venv "Scripts\python.exe"
$env:VIRTUAL_ENV = $venv
$env:Path = "$(Join-Path $venv 'Scripts');$(Split-Path -Parent $opaPath);$env:Path"
$env:ACS_OPA_PATH = $opaPath

Write-Host "[3/6] Installing Python build and test tools..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}
& $python -m pip install "maturin==1.8.7" pytest
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Maturin and pytest."
}

Write-Host "[4/6] Installing and selecting Rust 1.89 MSVC..." -ForegroundColor Cyan
& rustup toolchain install "1.89.0-x86_64-pc-windows-msvc"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Rust 1.89 MSVC."
}
Push-Location $policyEngine
try {
    & rustup override set "1.89.0-x86_64-pc-windows-msvc"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to select Rust 1.89 MSVC for policy-engine."
    }
} finally {
    Pop-Location
}

Write-Host "[5/6] Building and installing the native ACS Python extension..." -ForegroundColor Cyan
# link.exe can fail to create build-script executables when Cargo writes its
# target directory beneath a deeply nested Windows checkout. Keep only build
# artifacts in a short local path; the checked-out AGT source remains in this
# exploration folder.
New-Item -ItemType Directory -Path $cargoTarget -Force | Out-Null
$env:CARGO_TARGET_DIR = $cargoTarget
Push-Location $sdkPython
try {
    & $python -m maturin develop --release
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build and install the native ACS extension."
    }
} finally {
    Pop-Location
}

Write-Host "[6/6] Verifying OPA and the native extension..." -ForegroundColor Cyan
& $opaPath version
if ($LASTEXITCODE -ne 0) {
    throw "OPA validation failed."
}
& $python -c "import agent_control_specification._native; print('ACS native runtime available')"
if ($LASTEXITCODE -ne 0) {
    throw "The native ACS extension could not be imported."
}

Write-Host "Setup complete. Run .\run_official_demo.ps1, .\run_curated_examples.ps1, or .\run_boundary_demo.ps1 next." -ForegroundColor Green
