# Tailscale Funnel on the shop computer

Requires DATUS 0.2.2 or newer. This is an opt-in public HTTPS endpoint: anyone on the internet can reach the login page. Visitors do not need Tailscale; they still need a DATUS account and its permissions. Tailscale Serve is the alternative for private access.

## Prepare the other Windows computer

1. Close DATUS and install the updated DATUS installer under the shop Windows account. Existing data is retained. If this is a new installation, open DATUS and create the shop/owner first.
2. Install Tailscale from https://tailscale.com/download/windows and sign in to your own tailnet on that computer. Complete the Tailscale account/device approvals yourself. Do not send passwords or auth keys to anyone.
3. Close the DATUS controller. Open PowerShell as the same Windows account and run:

```powershell
$setup = "$env:LOCALAPPDATA\Programs\DATUS\_internal\setup\funnel.ps1"
& $setup -Action Prepare
```

Prepare discovers this device's Tailscale DNS name and reserves a separate local application port in `%LOCALAPPDATA%\DATUS\remote-access.json`. It does not publish anything, change router/firewall rules, or alter database credentials. It refuses to overwrite existing Serve/Funnel services. If PowerShell blocks unsigned scripts, review the script and use your organization's approved script-signing/execution process; this guide does not change machine execution policy.

4. Reopen DATUS and wait for the local workspace to be ready. Run:

```powershell
& $setup -Action Enable
```

The script checks the dedicated remote listener before calling Tailscale Funnel. Follow any HTTPS/Funnel enablement URL Tailscale presents; a tailnet administrator may need to approve it. If the command exits unsuccessfully, complete that approval and rerun Enable. The printed `https://...ts.net` address is the public workspace. Funnel provides the TLS certificate. It uses the device's Tailscale hostname, not your separately hosted domain.

5. On a phone using mobile data, open that exact HTTPS URL. Verify: unauthenticated sales/reports are unavailable; owner/staff login works; permitted reports and receipts load; logout removes access. Test a checkout and return using a disposable shop/test dataset before real remote trading. Never use real payment data for a connectivity test.

## Status and disabling

```powershell
& $setup -Action Status
& $setup -Action Disable
```

Disable only acts when the root handler on port 443 matches DATUS. It does not reset other Tailscale services. If someone changes that configuration, inspect `tailscale funnel status` and resolve it manually. Disable leaves the private remote listener configuration in place for later reuse; local trading continues normally. To remove the listener too, first disable Funnel, close DATUS, archive `remote-access.json`, and reopen DATUS.

`--bg` makes the Funnel configuration persist across restarts. Closing DATUS stops both application listeners; Funnel can remain configured but cannot serve DATUS until the controller reopens. Disable Funnel explicitly when you no longer want public access. The PC must be awake, online and running DATUS for remote users. Local trading stays on the original loopback address and continues without internet.

## Design and limits

- Local and remote HTTP listeners both bind exclusively to `127.0.0.1`. Only the separate remote listener is forwarded. PostgreSQL, files, backups and recovery keys are not published.
- The remote Flask application uses Secure/HttpOnly authentication cookies, SameSite Strict, CSRF checks, exact Host matching and exact HTTPS Origin checks on mutations including login. HTML form posts and foreign origins are rejected.
- The app does not trust caller-supplied forwarded IP headers. Remote login attempts share the existing ten-per-minute proxy-IP throttle. This may also temporarily affect legitimate logins; it is process-local and resets on restart. There is no MFA or distributed abuse protection yet.
- There is no ProxyFix/header-based privilege bypass: the TLS proxy preserves Host, and the remote app's cookie/security policy is configured explicitly. A reverse proxy that rewrites Host needs separate adaptation.
- The launcher uses the same business database with a second application instance. Public exposure is not a second offline database or backup.
- Keep the designated Windows account secured. Another local process able to change the app/configuration or access its secrets remains within the trust boundary.
- Invalid remote configuration or an occupied remote port prevents successful controller startup until corrected; disabling Funnel and archiving the remote configuration restores local-only startup.

Automated tests cover host/origin rejection, secure authentication cookies, CSRF, authentication/logout, spoofed-forwarded-IP throttling and coexistence with local operation. The installer acceptance test opens the real dedicated loopback listener and checks its health. Live Tailscale sign-in, tailnet policy approval, public TLS and a remote mobile browser must be verified on the shop computer; no live Funnel is created by a build or test.

References: [Funnel](https://tailscale.com/docs/features/tailscale-funnel), [CLI and disabling](https://tailscale.com/docs/reference/tailscale-cli/funnel).
