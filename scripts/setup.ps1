param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $project
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with the Windows launcher first.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r backend\requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
if (-not (Test-Path -LiteralPath '.env')) {
    & '.\.venv\Scripts\python.exe' scripts\configure.py
    if ($LASTEXITCODE -ne 0) { throw 'Configuration failed.' }
}
if (-not $SkipFrontend) {
    Push-Location frontend
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Dependencies ready. Configure DATABASE_URL in .env, then run the migration and owner commands in README.md.'
