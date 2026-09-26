# Windows telemetry bridge (prototype)

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
