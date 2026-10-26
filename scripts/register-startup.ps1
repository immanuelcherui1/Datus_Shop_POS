# Optional: run explicitly as the Windows account that should own the local POS process.
param([string]$TaskName = 'DATUS POS')
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw 'Task exists. Review it in Task Scheduler before replacing it.' }
$action = New-ScheduledTaskAction -Execute (Join-Path $project '.venv\Scripts\pythonw.exe') -Argument ('"' + (Join-Path $project 'backend\run.py') + '"') -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'DATUS local POS server. PostgreSQL must be running.'
Write-Host 'Startup task registered. It starts at Windows sign-in; this is not a Windows service.'
