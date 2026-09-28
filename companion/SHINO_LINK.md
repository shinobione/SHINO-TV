# SHINO // LINK — Windows PC-only pilot

Software-only pilot for the already installed, validated private SHINO-TV V2.1 review-003. It uses the **existing bounded, per-build HTTP Digest RAM-only** POST /api/v1/bridge/metrics. It does **not** change firmware, write TV flash or files, contact update/OTA/factory-return routes, change Wi-Fi connections or upload artwork. All four existing LCD metrics stay in place. Old manual sender remains available.

## This pilot delivers

- One Windows companion process that collects psutil CPU/actual RAM and NVIDIA GPU data using the existing sampler, then sends every ~2s when accepted. Failure/rejection retries at 2, 4, 8, 16, capped 30 seconds, without spinning or logging raw credential/network errors.
- Optional tray icon: CONNECTED/RETRYING state, open dashboard, Exit. Optional explicit current-user Windows auto-start via HKCU Run, not enabled automatically and requiring an installed pythonw.exe.
- Private config outside Git at %LOCALAPPDATA%\SHINO-TV\link.json stores only **the ABSOLUTE FILE PATH** to owner-local matching credentials, never password text. Device target is a manually configured private literal IPv4. It does not discover device or connect Windows to a Wi-Fi AP for you.
- PC-local --dry-run; no secrets/device access. --configure stores only config, no device contact. --once and --run/--tray are **owner-initiated RAM-only telemetry**, not flash.
- No media/GSMTC or cover delivery yet; current V2.1 numeric endpoint cannot accept music/image data. Separate future PC-only adapter and device scene work need independent review.

## Setup and safe owner test

Open PowerShell inside the *separate pilot branch checkout*. Preserve private review-003 and installed firmware; never copy credentials into Git. Install dependencies, then validate locally:

```powershell
py -3 -m pip install -r companion/requirements-link.txt
py -3 companion/shino_link.py --dry-run
```

Explicitly configure for the owner-current firmware, using the existing private **review-003** credentials file. These commands do NOT connect to the device or enable Windows auto-start:

```powershell
py -3 companion/shino_link.py --configure --host 192.168.4.1 --credentials-file "$HOME\SHINO-PRIVATE\review-003\credentials.txt"
```

Windows must be connected to the SHINO private WPA2 AP (or otherwise have a local route to 192.168.4.1). Using that AP may interrupt the PC's domestic Internet with only one Wi-Fi radio. The app never switches networks. To send exactly one RAM-only sample (same schema/endpoint as proven manual sender):

```powershell
py -3 companion/shino_link.py --once
```

Expected: One RAM-only sample: CONNECTED. A rejected network sample exits with code 1 and never tries any firmware writer. To run foreground with Ctrl+C stop, or start the optional tray UI:

```powershell
py -3 companion/shino_link.py --run
py -3 companion/shino_link.py --tray
```

After configuration and installed tray dependencies, you can also double-click the repository-root **start-shino-link.cmd** to request a no-console tray launch through Windows' pyw launcher. This does not configure auto-start. If pyw is unavailable, use the explicit PowerShell --tray command above. Do not run both the old manual continuous sender and SHINO // LINK at the same time: they would both send metrics to the same display.

System tray Exit stops its worker. You may optionally opt in to Windows start at user sign-in. These three commands use **HKCU for current user only**, no admin/service/task, and never start automatically just from --configure:

```powershell
py -3 companion/shino_link.py --autostart status
py -3 companion/shino_link.py --autostart enable
py -3 companion/shino_link.py --autostart disable
```

Auto-start uses pythonw.exe adjacent to the running Python interpreter; it refuses to replace an unexpected existing SHINO_LINK registry value. Do NOT enable it against a temporary folder you plan to delete. This pilot is source-based, not yet a signed EXE.

## Safety and behavioral contract

After about 6s without accepted telemetry, the device's existing RAM-only TTL marks measurements STALE, not zero or falsely live. Device power depends on USB-C remaining powered when PC turns off. GPU temporarily unavailable is explicit; sampler exceptions or invalid samples cannot replace a good numeric payload. No browser cookie reuse grants POST permission; the same per-build Digest credentials are used on every real connection. No log/registry entry contains credential values. No new SHINO application BIN, OTA, filesystem image, cover or second firmware writer.

Develop/test the software on the isolated V2.2 work branch; do not merge/cherry-pick any changes into the **frozen review-003 V2.1** source/PR #20. The separate roadmap is PR #21. The software-only Windows UX pilot needs no device reflash.