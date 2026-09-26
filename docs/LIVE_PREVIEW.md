# SHINO // TV — Windows live PC preview (no SmallTV firmware change)

This preview runs **on the PC only**. It uses the already implemented `companion/metrics_server.py` bridge and serves the 240×240 Canvas UI from the *same loopback origin*. It **does not** upload images, query the SmallTV, perform OTA, open a device serial connection or write device flash.

## Start in Windows

Download or clone the `feature/local-live-preview` branch (not `main` while the stacked PRs remain Draft). Install Python 3 if not already available.

One-time dependency:

```powershell
py -m pip install -r companion/requirements.txt
```

Then **double-click `start-preview.cmd`** (or run `py companion/metrics_server.py` from the repository root), and open:

**http://127.0.0.1:8765/**

Select **CONNECT LIVE PC METRICS**. Real CPU load, RAM load and (if NVIDIA drivers expose it) GPU load/temperature update about once per second. The **PC HEALTH DEMO** button returns to illustrative data; MUSIC, CODEX and RELEASE still use demo data. **SAVE PNG** exports the visible scene at 240×240 locally. No external APIs or authentication are involved in this localhost-only preview.

If NVIDIA metrics aren't available, the preview explicitly shows GPU N/A; it doesn't claim a measured zero load. The server's /metrics JSON additionally reports the total installed RAM so the Canvas can calculate RAM utilisation percentage. Its original Times-Z six-tile fields remain compatible with the firmware-side monitoring contract.

If the bridge is stopped/disconnected, the preview shows `PC OFFLINE` and can recover when the local server responds again (restart/refresh as needed). Running the preview as a static file or with a generic Web server does not provide live PC metrics: use the included local bridge.

## Security and network behavior

- The default server binds to **127.0.0.1:8765**. The HTML/JS UI is explicitly allowlisted and served only to loopback clients.
- Explicit `--bind PRIVATE_PC_LAN_IPV4` is intended for a *future* firmware integration and serves **/metrics** and **/health**, **not the preview page**. Restrict Windows Firewall to the intended TV IP if ever enabling it.
- No wildcard CORS, no Internet port forwarding, no arbitrary file server, no command execution route, no write endpoint, no credential exchange.
- GET /metrics contains local PC performance information. Do not expose it publicly.
- This is a simulated appearance, not proof of LCD rendering equivalence or a device-hardware test. The proposed native firmware scene protocol differs from this richer desktop preview model.

## Local checks

```powershell
py -m unittest discover -s companion -p "test_*.py" -v
node --test simulator/scene.test.mjs simulator/live.test.mjs
```

## No-flash gate unchanged

The owner's device still reports stock **Ultra-V9.0.44**. There is no owner-specific complete flash backup nor confirmed USB-UART pinout; firmware flash/OTA remains out of scope.
