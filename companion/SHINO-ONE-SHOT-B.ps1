# SHINO // TV -- one-shot corrected B OTA; offline inspection by default.
# The installed A is NOT changed by reading this script or by -Offline.
# -Execute is physically state-changing. Run only after owner-authorized fresh
# normal USB-C boot, SHINO Wi-Fi connection, and with LINK stopped.
[CmdletBinding()]
param([switch]$Execute)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$root = "research-local\m9-owner\ota-b-1e179b4-20261010"
$bin = Join-Path $root ".pio\build\esp12e_m9_4m2m_normal_qualification\firmware.bin"
$manifest = Join-Path $root "release.json"
$report = Join-Path $root "report.json"
$receipt = Join-Path $root "OTA-B-single-upload-receipt.json"
$marker = Join-Path $root "OTA-B-single-upload-attempt.marker"
$legacyLock = Join-Path $root "OTA-B-first-attempt.lock"
$legacyReceipt = Join-Path $root "OTA-B-first-attempt-receipt.json"
$expectedA = "5c1ce8a86766282d84547fe71e2f4bb19db5077442829e2c8526e376072aa964"
$expectedB = "1effdaf7172f2ce7caebd44a64e840164c418ccde95477c88ea9a28b4166aa48"
$source = "1e179b4103f8792be3c1c04186b7451a8ce2bc1d"

foreach ($file in @($bin, $manifest, $report)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: Private B release file missing. No device contact."
    }
}
if ((Test-Path -LiteralPath $receipt) -or (Test-Path -LiteralPath $marker) -or
    (Test-Path -LiteralPath $legacyLock) -or (Test-Path -LiteralPath $legacyReceipt)) {
    throw "STOP: A previous or uncertain attempt is registered. NO RETRY."
}
$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
$r = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$actual = (Get-FileHash -LiteralPath $bin -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expectedB -or $m.sha256 -ne $expectedB -or $r.sha256 -ne $expectedB -or
    $m.bytes -ne 407376 -or $r.bytes -ne 407376 -or
    (Get-Item -LiteralPath $bin).Length -ne 407376 -or
    $r.private -ne $true -or $r.source_dirty -ne $false -or $r.source_commit -ne $source) {
    throw "STOP: B SHA, size, provenance, or build report mismatch. No device contact."
}
# Python performs a second, independent exact release image/manifest check.
python companion/shino_update.py --bin $bin --manifest $manifest
if ($LASTEXITCODE -ne 0) { throw "STOP: Binary offline inspection failed." }

Write-Host "B CORRECTED: OFFLINE VERIFIED / NO DEVICE CONTACT" -ForegroundColor Green
Write-Host "B SHA256: $expectedB"
if (-not $Execute) {
    Write-Host "PRINT_ONLY: no network, no upload. -Execute is required for a one-shot OTA." -ForegroundColor Cyan
    return
}

Write-Host "ONE-SHOT WIFI OTA: user must have freshly power-cycled A and stopped LINK." -ForegroundColor Yellow
Write-Host "Only ONE authenticated status read before the single authorized upload." -ForegroundColor Yellow
Write-Host "If firmware A, memory floors, device or B differ, uploader aborts before POST." -ForegroundColor Yellow
# No separate status GET here. The Python updater reads running A ONCE,
# validates it, atomically creates $marker, then makes exactly one POST.
python companion/shino_update.py --bin $bin --manifest $manifest --install `
    --confirm-sha256 $expectedB --expected-current-sha256 $expectedA `
    --attempt-marker $marker --receipt $receipt
if ($LASTEXITCODE -ne 0) {
    Write-Host "OTA NOT CONFIRMED. DO NOT RESTART THIS LAUNCHER." -ForegroundColor Red
    exit 2
}
Write-Host "OTA BOOT_AND_TELEMETRY_CONFIRMED. Run read-only postboot checks." -ForegroundColor Green
