$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $project
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Build the frontend first: npm --prefix frontend run build' }
& '.\.venv\Scripts\python.exe' backend\run.py
if ($LASTEXITCODE -ne 0) { throw 'DATUS stopped unexpectedly. Check local configuration and database availability.' }
