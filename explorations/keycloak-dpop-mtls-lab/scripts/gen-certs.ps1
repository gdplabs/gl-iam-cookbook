[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Find-OpenSsl {
    $command = Get-Command openssl.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    $git = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($git) {
        $gitRoot = Split-Path -Parent (Split-Path -Parent $git.Source)
        $candidates = @(
            (Join-Path $gitRoot "mingw64\bin\openssl.exe"),
            (Join-Path $gitRoot "usr\bin\openssl.exe")
        )
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }

    throw "OpenSSL was not found. Install OpenSSL or Git for Windows, then retry."
}

function Invoke-OpenSsl {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & $script:OpenSsl @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL failed with exit code $LASTEXITCODE."
    }
}

$script:OpenSsl = Find-OpenSsl
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $projectRoot "certs"
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

Push-Location $outputDirectory
try {
    Write-Host "Generating CA certificate..."
    Invoke-OpenSsl @(
        "req", "-x509", "-newkey", "rsa:4096", "-sha256", "-days", "3650", "-nodes",
        "-keyout", "ca.key", "-out", "ca.crt", "-subj", "/CN=lab-ca",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        "-addext", "subjectKeyIdentifier=hash"
    )

    Write-Host "Generating server certificate..."
    Invoke-OpenSsl @(
        "req", "-newkey", "rsa:2048", "-nodes",
        "-keyout", "server.key", "-out", "server.csr", "-subj", "/CN=localhost"
    )
    Set-Content -LiteralPath "server.ext" -Encoding ascii -Value @(
        "subjectAltName=DNS:localhost,IP:127.0.0.1",
        "extendedKeyUsage=serverAuth"
    )
    Invoke-OpenSsl @(
        "x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
        "-CAcreateserial", "-out", "server.crt", "-days", "365", "-sha256", "-extfile", "server.ext"
    )

    Write-Host "Generating client certificate..."
    Invoke-OpenSsl @(
        "req", "-newkey", "rsa:2048", "-nodes",
        "-keyout", "client.key", "-out", "client.csr", "-subj", "/CN=lab-client"
    )
    Set-Content -LiteralPath "client.ext" -Encoding ascii -Value "extendedKeyUsage=clientAuth"
    Invoke-OpenSsl @(
        "x509", "-req", "-in", "client.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
        "-CAcreateserial", "-out", "client.crt", "-days", "365", "-sha256", "-extfile", "client.ext"
    )
}
finally {
    Remove-Item -LiteralPath "server.csr", "server.ext", "client.csr", "client.ext", "ca.srl" -Force -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "Wrote CA, server, and client certificates to $outputDirectory"
