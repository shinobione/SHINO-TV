# Minimal read-only API probe (Windows)

Run locally on a computer on the same LAN as the owner's device, after confirming the address on the device UI. This document does not imply the project has LAN access.

The following three endpoints were previously observed working on the owner's stock Ultra-V9.0.44 and are read-only:

```powershell
$TV = 'http://192.168.1.70'
foreach ($endpoint in @('/v.json', '/app.json', '/space.json')) {
    Write-Host "GET $endpoint"
    try {
        Invoke-RestMethod -Uri ($TV + $endpoint) -Method Get -TimeoutSec 5 |
          ConvertTo-Json -Compress -Depth 5
    } catch {
        Write-Host ("Failed: " + $_.Exception.Message)
    }
}
```

No automatic scan, no login discovery, and no `/set`, `/update`, upload or delete requests are issued. Preserve reported timestamps when comparing storage values after owner-initiated changes.

If any additional route must be tested, review its likely side effects first, and keep a record of HTTP method, request, response, version and time.

## Safer reusable report (phase 0B)

The newer [strict Windows GET-only report](STOCK_READONLY_WIFI_REPORT.md) uses the same previously observed JSON routes, projects only model/version, theme and filesystem counts, and optionally inspects `GET /update` form metadata while discarding raw HTML, passwords, hidden field values and arbitrary settings. Run `run-stock-readonly.cmd` from branch `research/stock-v9044-readonly-report` and review its ignored local `research-local/stock-report.json`. Neither form inspection nor the reported photo/GIF free bytes measures the actual proprietary stock OTA slot.
