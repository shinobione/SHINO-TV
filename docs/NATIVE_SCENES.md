# SHINO // TV — Native scenes v1 (software-only candidate)

This is an **extension to the imported Times-Z ESP8266 firmware**, not a feature of the owner's current factory Ultra-V9.0.44. No hardware flash is approved. The default behavior is preserved: with `METRICS_URL` configured the Times-Z six-tile dashboard remains the startup scene; otherwise the upstream startup screen remains. The optional metrics mode can still be selected by command when configured.

## Device API (after a future, separately approved installation)

Both routes require the existing upstream Bearer authentication via `Authorization: Bearer <token>`. An unconfigured/empty token is rejected.

- `GET /api/v1/shino/scene`: reports scene kind, whether metrics is compiled/configured, and stale-data state.
- `POST /api/v1/shino/scene`: selects an in-memory scene. Only JSON objects with a known `kind`, required fields and no extra fields are accepted. Maximum request body: 512 bytes. Invalid JSON leaves the previous scene unchanged.

| Kind | Exact JSON shape | Behaviour |
|---|---|---|
| metrics | `{"kind":"metrics"}` | Returns to original Times-Z PC dashboard, only if `METRICS_URL` exists. |
| music | `{"kind":"music","artist":"SHINOBIWAN","track":"MACHINE FEVER","progress":38}` | Native panel and bounded progress bar. |
| agent | `{"kind":"agent","status":"RUNNING","task":"Build firmware scenes","progress":72}` | Coding-agent status and progress. |
| release | `{"kind":"release","artist":"SHINOBIWAN","track":"DANCE AT MY FUNERAL","days":12}` | Release countdown. |

All strings must be **printable ASCII** (the upstream built-in bitmap font is not Unicode-aware). Field maxima: artist 32, track 48, status 18, task 56 chars. Progress must be an integer 0–100; days an integer 0–9999. No embedded HTML, arbitrary draw operations, image URLs, file paths or firmware commands are accepted.

This initial renderer is fixed-layout and deliberately not yet a movable-widget editor; the independent `simulator/` has an additional `title` display field which must be **omitted** from the device wire protocol. The `companion/scene_client.py` validates the exact v1 device shape.

## Freshness and memory

- Rendered content is held in RAM only; JSON updates never call LittleFS writes.
- Custom scene values show `DATA STALE` after 60 seconds without a fresh POST and recover upon new data.
- Active metrics reuses the upstream `DashboardManager` including its HTTP polling and offline handling; the metrics URL is a **PC LAN address**, not the TV address.
- Scene selection does not persist through a power cycle.
- Firmware is bounded by the ESP8266's RAM and will still require hardware validation after full owner-unit backup.

## Preview on PC — no device requests

```powershell
python companion/scene_client.py companion/examples/music.json
python companion/scene_client.py companion/examples/agent.json
```

These print validated JSON only. No network access.

Only **after** the owner has backed up V9.0.44, approved a flash and verified custom firmware is really installed may an explicit send be considered:

```powershell
$env:SHINO_TV_TOKEN = "YOUR_CUSTOM_FIRMWARE_API_TOKEN"
python companion/scene_client.py companion/examples/music.json --url http://YOUR_TV_LAN_IPV4 --send --confirm-custom-firmware
```

The script accepts only a private IPv4 or loopback HTTP address, and needs both explicit confirmation flags. Do **not** attempt this on the current factory V9.0.44 or expose the device service to the public Internet.

## Software checks

The firmware CI runs the ESP8266 PlatformIO and LittleFS builds. The companion CI tests scene-validation limits and performs a mocked HTTP POST with no physical device involved. Neither CI workflow publishes a flashable release image.
