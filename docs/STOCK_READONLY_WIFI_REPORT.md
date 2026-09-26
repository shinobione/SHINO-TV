# Phase 0B — owner-operated stock V9.0.44 READ-ONLY Wi-Fi report

This diagnostic is designed for **the owner's existing single SmallTV-Ultra**, still running official Ultra-V9.0.44. No spare board, soldering, UART adapter or physical change is needed. The repository, its CI and the assistant do NOT have access to the owner's private 192.168.x.x network. Only the owner can run the tool locally.

## Quick Windows workflow

1. Download the ZIP of branch `research/stock-v9044-readonly-report` from [SHINO-TV](https://github.com/shinobione/SHINO-TV/tree/research/stock-v9044-readonly-report) (Code → Download ZIP), then extract it.
2. Connect Windows to the same local network as the SmallTV. Confirm the SmallTV's actual private IP on its UI; it has previously appeared as `192.168.1.70`, but this may change.
3. Double-click `run-stock-readonly.cmd`. Requires installed Python 3 with Windows `py` launcher; the probe uses **only Python's standard library** and requires no PlatformIO or flashing tools.
4. Enter the IP and optionally answer `O` to read the existing `/update` page's **form structure**, NOT to upload a file. Leaving that at `N` uses only the three previously observed JSON routes.
5. The sanitized report is written to `research-local/stock-report.json` (gitignored, **never overwritten**). Review it before sharing; it does not record the device IP, full app settings, raw page HTML, form field values or tokens.

Alternative terminal command from extracted repository root:

```powershell
py -3 tools/stock_readonly_report.py --host 192.168.1.70 --include-update-page --out research-local/stock-report.json
```

For the terminal version, create the `research-local` directory first. If you want the report in the terminal without writing a file, omit `--out`. If you do not want the optional update-page GET, omit `--include-update-page`.

## Exactly what happens

| Route | Method | What is kept | What is deliberately discarded |
|---|---|---|---|
| `/v.json` | GET | `m` and `v` capped to 48 characters | All other JSON fields |
| `/space.json` | GET | Nonnegative integer `total` and `free` | Other fields; **never** interprets this as OTA capacity |
| `/app.json` | GET | Nonnegative integer `theme` only | Wi-Fi or any other settings |
| `/update` (optional) | GET | Bounded form method, sanitized local action path, enctype, file-field **names**, script count | Hidden/file field **values**, HTML, script contents, external resources, URL query strings |

The script constructs only four hardcoded GET paths. It requires an IPv4 literal within `10/8`, `172.16/12` or `192.168/16`. No redirects are followed; no DNS resolution, port sweep, URL guessing, authentication discovery, javascript execution, upload, `POST`, `PUT`, erase or flash command occurs. Responses larger than 64 KiB are discarded. Each request uses a short timeout and errors are reported without raw server bodies.

**A GET is a request to the running device, not a firmware change.** Only these previously observed JSON routes and the owner-observed update HTML page were selected. If a route behaves unexpectedly it is not retried with different parameters.

## What we hope to learn — and what we cannot

- Reconfirm the exact model/version and time of observation.
- Check currently reported photo/GIF filesystem storage, while clearly separating it from the *unknown stock application OTA slot*.
- Optional: determine whether `/update` presents a normal multipart form with a local action/field name or a JavaScript-driven interface. This helps plan, **not execute**, a future manually approved upload path.
- No GET or HTML form inspection can prove how many free application OTA bytes the proprietary firmware reserves, its validation rules, actual acceptance of the loader, or that the OEM FS layout survives SHINO's alternate partition arrangement. If the original source has no safe read-only OTA-size endpoint, the correct result remains **UNKNOWN**.
- An official 494,144-byte OTA BIN is **not** a 4-MiB owner flash backup; a working updater is required to restore it.

The resulting report is research evidence only: its `permission_to_flash` remains `false`, even if all sampled routes return HTTP 200. **Do not upload test files to `/update` simply to test capacity.** A deliberately rejected ZIP/BIN may still exercise the manufacturer's writer or validation paths in ways we cannot guarantee.

## Validation

`tools/test_stock_readonly_report.py` runs entirely with fake in-memory response objects and checks: strict private-IP parsing, GET-only route allowlist, opt-in `/update`, refusal of redirects, body size limit, no raw secrets/full HTML/IP in report, unknown OTA space and no implied flash permission. GitHub CI runs it with the rest of the offline tests. GitHub Actions never contacts the owner's TV.

Follow-up decision after owner runs it: inspect the report and the **official V9.0.44 image's embedded stock update/layout evidence** off-device; document whether a credible safe read-only capacity disclosure exists. No assumption or OTA upload without explicit new owner approval.
