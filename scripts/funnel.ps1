# Run on the shop PC, under the same Windows account that runs DATUS.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateSet('Prepare','Enable','Disable','Status')][string]$Action)
$ErrorActionPreference = 'Stop'
$ts = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if (-not (Test-Path -LiteralPath $ts)) { throw 'Install Tailscale from https://tailscale.com/download/windows and sign in first.' }
$dataPath = Join-Path $env:LOCALAPPDATA 'DATUS'
$configPath = Join-Path $dataPath 'remote-access.json'

function Read-Tailscale([string[]]$Arguments) {
    $result = & $ts @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Tailscale command failed. Check sign-in and permissions in Tailscale.' }
    return ($result | ConvertFrom-Json)
}
function Read-Existing {
    return Read-Tailscale -Arguments @('serve', 'status', '--json')
}
function Has-Servers($config) {
    return (($null -ne $config.TCP -and @($config.TCP.PSObject.Properties).Count -gt 0) -or
            ($null -ne $config.Web -and @($config.Web.PSObject.Properties).Count -gt 0))
}

if ($Action -eq 'Status') {
    & $ts funnel status
    if ($LASTEXITCODE -ne 0) { throw 'Could not read Funnel status.' }
    if (Test-Path -LiteralPath $configPath) {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        Write-Output "DATUS remote address: $($config.origin)"
    }
    exit 0
}
if ($Action -eq 'Prepare') {
    if (-not (Test-Path -LiteralPath (Join-Path $dataPath 'owner.ready'))) { throw 'Install DATUS and create your shop owner account first.' }
    $versionFile = Join-Path $env:LOCALAPPDATA 'Programs\DATUS\_internal\version.txt'
    if (-not (Test-Path -LiteralPath $versionFile)) { throw 'Install DATUS 0.2.2 or later first.' }
    if ([version](Get-Content -LiteralPath $versionFile -Raw).Trim() -lt [version]'0.2.2') { throw 'Upgrade to DATUS 0.2.2 or later first.' }
    if (Get-Process -Name DATUS -ErrorAction SilentlyContinue) { throw 'Close the DATUS controller before Prepare, then reopen it afterwards.' }
    $state = Read-Tailscale -Arguments @('status', '--json')
    if ($state.BackendState -ne 'Running') { throw 'Sign in to Tailscale on this computer first.' }
    $dnsName = $state.Self.DNSName.TrimEnd('.').ToLowerInvariant()
    if ($dnsName -notmatch '^[a-z0-9-]+(?:\.[a-z0-9-]+)+\.ts\.net$') { throw 'Tailscale did not return a valid device DNS name. Enable MagicDNS in your tailnet.' }
    $origin = 'https://' + $dnsName
    if (Test-Path -LiteralPath $configPath) {
        $existing = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if ($existing.origin -ne $origin) { throw 'The Tailscale hostname changed. Disable the previous Funnel and review remote-access.json before reconfiguring.' }
    } else {
        if (Has-Servers (Read-Existing)) { throw 'This device already has Serve/Funnel services. Use a dedicated shop device or review those services first; nothing was replaced.' }
        $settings = Get-Content -LiteralPath (Join-Path $dataPath 'database-admin.json') -Raw | ConvertFrom-Json
        do {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
            $listener.Start()
            $remotePort = $listener.LocalEndpoint.Port
            $listener.Stop()
        } while ($remotePort -in @($settings.http_port, $settings.database_port))
        $json = @{ origin = $origin; port = $remotePort } | ConvertTo-Json
        [System.IO.File]::WriteAllText($configPath, $json, [System.Text.UTF8Encoding]::new($false))
    }
    Write-Output "Prepared $origin. Reopen DATUS, then run this script with -Action Enable. Nothing is public yet."
    exit 0
}
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Run -Action Prepare first.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($config.origin -notmatch '^https://[a-z0-9-]+(?:\.[a-z0-9-]+)+\.ts\.net$' -or
    $config.port -lt 1024 -or $config.port -gt 65535) { throw 'Invalid remote-access.json.' }
$target = 'http://127.0.0.1:' + [int]$config.port
$existing = Read-Existing
if ($Action -eq 'Disable') {
    if (-not (Has-Servers $existing)) { Write-Output 'No Serve/Funnel listeners are configured.'; exit 0 }
    # Refuse to modify an unrelated service, even if someone changed Tailscale later.
    $hostKey = ([uri]$config.origin).Host + ':443'
    $web = $existing.Web.PSObject.Properties[$hostKey].Value
    if ($null -eq $web -or $web.Handlers.PSObject.Properties['/'].Value.Proxy -ne $target -or
        @($web.Handlers.PSObject.Properties).Count -ne 1) { throw 'Port 443 no longer matches only DATUS. Review tailscale funnel status; nothing was changed.' }
    & $ts funnel --bg --https=443 $target off
    if ($LASTEXITCODE -ne 0) { throw 'Funnel could not be disabled. Check tailscale funnel status.' }
    Write-Output 'DATUS Funnel disabled. Local trading still works; the private remote listener stays configured.'
    exit 0
}
if (Has-Servers $existing) { throw 'Serve/Funnel is already configured. Check -Action Status; disable DATUS before enabling again. Existing services were not replaced.' }
$state = Read-Tailscale -Arguments @('status', '--json')
if ($state.BackendState -ne 'Running' -or ('https://' + $state.Self.DNSName.TrimEnd('.').ToLowerInvariant()) -ne $config.origin) { throw 'Sign in to the matching Tailscale device before enabling.' }
$health = Invoke-RestMethod -Uri ($target + '/api/health') -Headers @{ Host = ([uri]$config.origin).Host } -TimeoutSec 10
if ($health.application -ne 'DATUS' -or $health.status -ne 'ok' -or $health.remote_access -ne $true) { throw 'The dedicated remote listener is not ready. Reopen the updated DATUS controller first.' }
Write-Output "Publishing the DATUS login at $($config.origin). Anyone can reach this login; DATUS accounts are still required."
& $ts funnel --bg --https=443 $target
if ($LASTEXITCODE -ne 0) { throw 'Funnel was not enabled. Complete any Tailscale HTTPS/Funnel approval and retry.' }
& $ts funnel status
Write-Output 'Verify from a phone using mobile data: log in, view a receipt, and log out. Leave the shop PC awake and DATUS running.'
