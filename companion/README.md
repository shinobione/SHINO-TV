# Windows telemetry bridge (prototype)

## Current owner V2.1 workflow (28 September 2026)

The owner's **private review-003 V2.1 has been installed and shown to boot** with four live CPU/GPU/RAM/GPU TEMP values on the physical 240x240 LCD; the original manually initiated RAM-only sender returned `RAM telemetry accepted`. To pilot the NEW opt-in Windows tray companion without reflashing, see **[SHINO // LINK instructions](SHINO_LINK.md)** and `companion/shino_link.py`. Matching secrets stay only under owner-private `review-003/credentials.txt`, never in Git. Earlier factory/Times-Z research and manual sender explanations below remain historical, not current owner device status.

This is the first PC-side integration for the **existing** six-tile `DashboardManager` from Times-Z. It samples CPU/RAM with `psutil` and GPU utilization, VRAM, power and temperature from `nvidia-smi` (when present). It does **not** modify the factory SmallTV or upload images.

## Set up on Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r companion/requirements.txt
python companion/metrics_server.py
```

Local test: open `http://127.0.0.1:8765/metrics`. The server's default binding is **localhost only**.

To allow a SmallTV on the same trusted LAN to poll the PC, find your actual **PC LAN address** and explicitly bind to that interface, e.g.:

```powershell
python companion/metrics_server.py --bind YOUR_PC_LAN_IPV4 --port 8765
```

Restrict Windows Firewall inbound TCP 8765 to the specific SmallTV IP; do not forward this port to the Internet. The firmware's `METRICS_URL` compilation flag must reference `http://YOUR_PC_LAN_IPV4:8765/metrics`, **not** the device's own IP. The upstream firmware is not yet flashed, and no direct integration with factory Ultra-V9.0.44 is claimed.

Returns the keys required by upstream: `ok`, `gpu_usage`, `cpu_usage`, `gpu_vram_mb`, `memory_used_gb`, `gpu_power`, `gpu_temp_c`. An extra `gpu_available` indicates whether NVIDIA telemetry succeeded. GPU readings are zero if unavailable; CPU/RAM still report. Sensor sampling runs in the background every second to keep HTTP GET responsive to the upstream firmware's 800 ms timeout. No API keys, listening on every interface, writes to the TV, remote command execution or CORS.

Tests: `python -m unittest discover -s companion -p 'test_*.py' -v` (the tests do not require psutil or a real NVIDIA GPU).


## New: RAM-only telemetry push to FS-less native SHINO bridge

The source-only first-boot bridge now includes a flash-resident 240×240 CPU/GPU/RAM display and native Web UI. Unlike the existing localhost `GET /metrics` service, `push_fsless_metrics.py` is an **explicit client** which sends short numeric PC samples to `POST /api/v1/bridge/metrics` on the bridge's private AP using per-build HTTP Digest credentials. Never point it at the factory TV's `/update` URL.

PC-only dry-run: `py companion/push_fsless_metrics.py --dry-run` (requires `psutil`, never reads secrets or contacts device). Real sending is only meaningful after a separately authorized SHINO firmware installation: connect Windows to SHINO's private AP and supply the private, *matching-build* `firmware/private/credentials.txt` file. Example: `py companion/push_fsless_metrics.py --host 192.168.4.1 --credentials-file firmware/private/credentials.txt --once`. This is **not a flash/install operation**. Metrics remain in device RAM and expire in six seconds. If the PC has only one Wi-Fi adapter, joining the private AP can disrupt home Wi-Fi/Internet; an Ethernet connection may help. More detail: [FS-less native dashboard](../docs/FSLESS_NATIVE_DASHBOARD.md).
