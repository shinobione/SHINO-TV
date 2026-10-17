# SHINO // LINK — Windows PC-only pilot

## Mission 9 Phase P: host-only Digest compatibility

Owner [Phase P instruction](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6047604159)
dated 7 October 2026; host validation completed 8 October 2026 from exact clean
`e0aeedbb928c0a8bb90ace341dc55a9f42891188` on the existing Mission 9 branch
and Draft/open/unmerged PR42. The owner-reported StageA controlled comparison
isolated legacy-only host realm registration. This pass adds the explicit closed
`DIGEST_REALMS = ("SHINO-FirstBoot", "SHINO-StageA")` and registers the same
existing private Digest user/password for both. Legacy profile0/profile2 and
profile1 StageA use the existing RAM-only POST `/api/v1/bridge/metrics`.
No new credentials or realm option; no challenge-supplied realm enrollment,
Basic authentication, proxy, redirect or alternate endpoint.

The Digest handler/challenge cache, credential format, endpoint/payload, sender
retry logic and `shino_link.py` are unchanged. Accepted LINK samples remain
2 s apart; failures retain 2/4/8/16/30 s capped backoff and existing opener
discard/recreate rules. Firmware, writer binding, frozen BIN, physical receipts
and normal gate verdicts are unchanged. The earlier pilot/install instructions
below are historical operating guidance, not operations performed by Phase P.

Host-only validation: **19 sender +28 LINK tests PASS**, zero failures/errors/
skips. Real urllib Digest handlers run against deterministic in-memory HTTP
transport; DNS, socket connection and HTTP connection guards assert zero calls.
Both approved realms prove acceptance with the same synthetic generated-format
credentials, challenge reuse, rotated challenges, interrupted-handshake recovery,
bounded retry/recreation, accepted cadence and sanitized diagnostics. Unlisted,
empty/case-altered realms and Basic challenges fail; cached challenges cannot
enroll an unlisted realm. Synthetic fixtures only; owner-private credentials
were not opened. A first test run exposed a fixture retaining two transports;
using a separate opener for each realm fixed the test setup without changing
production behavior.

Focused commands (PC-only; no sender launch):

```powershell
py -3 -m unittest discover -s companion -p test_push_fsless_metrics.py -v
py -3 -m unittest discover -s companion -p test_shino_link.py -v
```

Local validation used Python 3.12 with fixture TEMP/TMP under ignored
`research-local/m9-phase-p/`. Existing Linux companion CI and Windows LINK smoke
run the extended suites; final commit and exact-head CI links are recorded in
PR42's description after push. Local source comparison confirms all tracked
`firmware/**`, `tools/**`, physical receipts and `companion/shino_link.py` unchanged.

Exact changed files:

- `companion/push_fsless_metrics.py`
- `companion/test_push_fsless_metrics.py`
- `companion/test_shino_link.py`
- `companion/SHINO_LINK.md`
- `docs/AGENT_HANDOFF.md`
- `docs/ROADMAP.md`

**DEVICE CONTACTS=0; SERIAL I/O=0; FLASH WRITES=0; RTC WRITES=0; REBOOTS=0;
DEVICE FILESYSTEM WRITES=0. No device/telemetry network request in this pass.
STOP before every device operation. DO NOT REBOOT/FLASH/MERGE.**

## Earlier pilot operating guidance

Software-only pilot for the already installed, validated private SHINO-TV V2.1 review-003. It uses the **existing bounded, per-build HTTP Digest RAM-only** POST /api/v1/bridge/metrics. It does **not** change firmware, write TV flash or files, contact update/OTA/factory-return routes, change Wi-Fi connections or upload artwork. All four existing LCD metrics stay in place. Old manual sender remains available.

## This pilot delivers

- One Windows companion process that collects psutil CPU/actual RAM and NVIDIA GPU data using the existing sampler, then sends every ~2s when accepted. Failure/rejection retries at 2, 4, 8, 16, capped 30 seconds, without spinning or logging raw credential/network errors.
- Authentication/network failures discard the HTTP/Digest opener before the next scheduled attempt. A fresh opener recovers from interrupted Digest handshakes without restarting the companion. Successful sampling retains its opener; three consecutive malformed replies also trigger fresh client state. The existing tray states/menu and telemetry endpoint/schema stay unchanged.
- Within each client, successful Digest challenges are reused only for the exact configured telemetry endpoint. A rejected challenge is renewed normally; interrupted Digest exchanges clear urllib's recursion counter in `finally`. Steady-state POSTs avoid repeatedly sending anonymous samples and rotating the firmware's shared challenge. No challenge/header/credential value is logged.
- Optional `--diagnostics-file <path>` with `--run` or `--tray` writes an atomic bounded snapshot of the last 64 attempts: accepted sample, no route/timeout, refused/reset connection, HTTP 401/403, other HTTP error, malformed response, invalid sample or client error. It records attempt counts, client generation and timing; never URLs, private paths, exception text, credentials, Authorization headers or Digest nonce values. The default remains no diagnostic file.
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
# P1 household LAN continuation (offline candidate)

The P1 branch supports `--set-target --host <actual-private-DHCP-IP>` and
`--recovery-target` on an existing LINK configuration. A running tray/foreground
sender reloads its target on the next scheduled attempt and refreshes Digest;
these commands do not start a second sender, change autostart or switch Windows
Wi-Fi. Identify the lease through the router / authenticated P1 status. Keep the
matching HTTP credentials file private. Household Wi-Fi passwords are entered
only with the separate masked local provisioning command after exact-image
approval; see [P1 procedure and HOLD gates](../docs/home-lan/README.md).
