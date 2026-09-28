"""SHINO // LINK — opt-in Windows tray companion for the already-installed V2.1.

PC-side ONLY. Uses the existing validated per-build Digest RAM telemetry sender.
No firmware routes, OTA, media/image upload, Wi-Fi switching, device discovery,
registry modification except a *separately requested* per-user auto-start action.
Neither a config command nor a dry run contacts the SmallTV.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser

from metrics_server import collect_metrics, query_nvidia
from push_fsless_metrics import (
    SenderError, encode_sample, make_opener, read_credentials, send_one, validate_host,
)

APP_NAME = "SHINO // LINK"
DEFAULT_HOST = "192.168.4.1"
RUN_VALUE = "SHINO_LINK"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CONFIG_SCHEMA = 1
CONNECTED_INTERVAL_SECONDS = 2.0
MAX_RETRY_SECONDS = 30.0
MAX_CONFIG_BYTES = 2048


class LinkError(ValueError):
    """A deliberately sanitized user-facing error (never include credentials)."""


def config_path() -> Path:
    # No files, password values or configuration are placed inside the Git repo.
    local = os.environ.get("LOCALAPPDATA")
    return (Path(local) if local else Path.home() / "AppData" / "Local") / "SHINO-TV" / "link.json"


def private_config(path: Path) -> Path:
    path = Path(path).expanduser()
    if path.is_symlink():
        raise LinkError("Configuration symlinks are forbidden")
    return path


def exact_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise LinkError("Duplicate configuration field")
        result[key] = value
    return result


def load_config(path: Path) -> dict[str, str]:
    path = private_config(path)
    if not path.is_file() or path.stat().st_size > MAX_CONFIG_BYTES:
        raise LinkError("No valid local SHINO // LINK configuration. Run --configure first.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=exact_keys)
    except (UnicodeError, ValueError) as exc:
        raise LinkError("Local configuration is not valid JSON") from exc
    if not isinstance(data, dict) or set(data) != {"schema", "host", "credentials_file"}:
        raise LinkError("Unexpected local configuration format")
    if type(data["schema"]) is not int or data["schema"] != CONFIG_SCHEMA:
        raise LinkError("Unsupported configuration version")
    if type(data["host"]) is not str or type(data["credentials_file"]) is not str:
        raise LinkError("Invalid local target or credential path")
    host = validate_host(data["host"])
    creds = Path(data["credentials_file"])
    if not creds.is_absolute() or creds.is_symlink():
        raise LinkError("Credentials must be an existing private regular absolute path")
    return {"host": host, "credentials_file": str(creds)}


def save_config(path: Path, host: str, credentials: Path) -> None:
    path = private_config(path)
    host = validate_host(host)
    credentials = Path(credentials).expanduser().absolute()
    # Existing sender validates the exact matching-format credential file.
    read_credentials(credentials)
    if path.exists() and not path.is_file():
        raise LinkError("Configuration destination must be a regular file")
    parent = path.parent
    if parent.is_symlink():
        raise LinkError("Configuration parent must not be a symlink")
    parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": CONFIG_SCHEMA, "host": host,
            "credentials_file": str(credentials)}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=parent,
                                         prefix=".shino-link-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class LinkEngine:
    """Purely PC-side rate-limited state machine; no startup network side effects."""

    def __init__(self, host: str, opener, sampler, sender=send_one,
                 clock=time.monotonic):
        self.host = validate_host(host)
        self.opener = opener
        self.sampler = sampler
        self.sender = sender
        self.clock = clock
        self.next_due = 0.0
        self.failures = 0
        self.state = "WAITING"

    def step(self, now: float | None = None) -> str:
        use_live_clock = now is None
        now = self.clock() if use_live_clock else now
        if now < self.next_due:
            return self.state
        try:
            sample = self.sampler()
            encode_sample(sample)  # Do not send invalid, stale or unbounded readings.
            accepted = self.sender(self.host, self.opener, sample, timeout=3.0)
        except Exception:
            # Never log exception bodies: they may include local paths or HTTP headers.
            accepted = False
        if accepted:
            self.failures = 0
            self.state = "CONNECTED"
            delay = CONNECTED_INTERVAL_SECONDS
        else:
            self.failures += 1
            self.state = "RETRYING"
            delay = min(MAX_RETRY_SECONDS, 2.0 * (2 ** min(self.failures - 1, 4)))
        # Delay is measured AFTER collection/HTTP completes, so a 3s timeout
        # cannot accidentally turn a 2s retry into an immediate retry storm.
        completed = self.clock() if use_live_clock else now
        self.next_due = completed + delay
        return self.state

    def run(self, stop: threading.Event, report) -> None:
        last_state = None
        while not stop.is_set():
            state = self.step()
            if state != last_state:
                report(state)
                last_state = state
            # Never spin or immediately retry on a network/collection failure.
            stop.wait(max(0.01, self.next_due - self.clock()))


def make_engine(config: dict[str, str]) -> LinkEngine:
    # Lazy import: --dry-run/configure/autostart status never need to read secrets
    # or contact the device. The credentials file is never copied into link.json.
    user, password = read_credentials(Path(config["credentials_file"]))
    opener = make_opener(config["host"], user, password)
    import psutil
    psutil.cpu_percent(interval=None)  # Prime nonblocking first CPU sample.
    return LinkEngine(config["host"], opener,
                      lambda: collect_metrics(psutil, query_nvidia))


def run_tray(config: dict[str, str]) -> int:
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise LinkError("Tray dependencies missing. Install companion/requirements-link.txt") from exc
    engine = make_engine(config)
    stop = threading.Event()
    status = {"value": "WAITING"}
    picture = Image.new("RGB", (64, 64), "#141820")
    draw = ImageDraw.Draw(picture)
    draw.rounded_rectangle((5, 5, 58, 58), radius=12,
                           fill="#242e3a", outline="#c4a779", width=3)
    draw.line([(15, 42), (24, 22), (32, 34), (41, 17), (49, 24)],
              fill="#80d9aa", width=5, joint="curve")

    def state_changed(value: str) -> None:
        status["value"] = value
        icon.title = APP_NAME + " · " + value
        icon.update_menu()

    def open_dashboard(icon_, item) -> None:
        # Only the explicitly configured and validated private host is opened.
        webbrowser.open("http://" + engine.host + "/")

    def quit_app(icon_, item) -> None:
        stop.set()
        icon_.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: "State: " + status["value"],
                         lambda icon_, item: None, enabled=False),
        pystray.MenuItem("Open SHINO // TV", open_dashboard),
        pystray.MenuItem("Exit SHINO // LINK", quit_app),
    )
    icon = pystray.Icon("SHINO_LINK", picture, APP_NAME + " · WAITING", menu)
    worker = threading.Thread(target=engine.run, args=(stop, state_changed),
                              name="SHINO-LINK-metrics", daemon=True)
    worker.start()
    try:
        icon.run()
    finally:
        stop.set()
        worker.join(timeout=4)
    return 0


def autostart_command() -> str:
    if os.name != "nt":
        raise LinkError("Per-user auto-start is Windows-only")
    windowed = Path(sys.executable).with_name("pythonw.exe")
    if not windowed.is_file():
        raise LinkError("pythonw.exe not found next to the active Python interpreter")
    return subprocess.list2cmdline([str(windowed), str(Path(__file__).resolve()), "--tray"])


def autostart(action: str, path: Path) -> str:
    if os.name != "nt":
        raise LinkError("Per-user auto-start is Windows-only")
    import winreg
    if action == "enable":
        load_config(path)
        try:
            import pystray
            from PIL import Image
        except ImportError as exc:
            raise LinkError("Install companion/requirements-link.txt before enabling auto-start") from exc
    command = autostart_command() if action == "enable" else None
    access = winreg.KEY_QUERY_VALUE | (winreg.KEY_SET_VALUE if action != "status" else 0)
    # Status / disable must not silently CREATE any registry key.
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)
    except FileNotFoundError:
        if action == "status":
            return "Disabled"
        if action == "disable":
            return "Already disabled"
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)
    with key:
        try:
            existing, kind = winreg.QueryValueEx(key, RUN_VALUE)
        except FileNotFoundError:
            existing, kind = None, None
        if action == "status":
            return "Enabled" if existing is not None else "Disabled"
        if action == "enable":
            if existing is not None and (kind != winreg.REG_SZ or existing != command):
                raise LinkError("Auto-start entry differs: refuse to overwrite an unexpected value")
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
            return "Enabled for current Windows user only"
        if action == "disable":
            if existing is None:
                return "Already disabled"
            # Explicitly owned value, not an arbitrary startup application.
            # Avoid logging the registry contents because they can contain paths.
            expected_script = str(Path(__file__).resolve()).lower()
            if (kind != winreg.REG_SZ or expected_script not in existing.lower()
                    or not existing.endswith(' --tray')):
                raise LinkError("Unexpected auto-start entry: refuse automatic deletion")
            winreg.DeleteValue(key, RUN_VALUE)
            return "Disabled for current Windows user"
    raise LinkError("Unsupported auto-start action")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--dry-run", action="store_true",
                         help="Local PC schema validation only, NO secrets or network")
    actions.add_argument("--configure", action="store_true",
                         help="Save local host and private credential FILE PATH, never password values")
    actions.add_argument("--once", action="store_true",
                         help="One explicitly initiated RAM telemetry sample to configured SHINO")
    actions.add_argument("--run", action="store_true",
                         help="Foreground 2s sampling with bounded reconnect backoff")
    actions.add_argument("--tray", action="store_true",
                         help="Opt-in Windows system tray companion, same RAM-only protocol")
    actions.add_argument("--autostart", choices=("enable", "disable", "status"),
                         help="Explicit per-user HKCU Run change; never enabled by configure")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Private IPv4 destination for --configure (default 192.168.4.1)")
    parser.add_argument("--credentials-file", type=Path,
                        help="Private matching-build file; used ONLY for --configure, no password on CLI")
    args = parser.parse_args(argv)
    try:
        if args.dry_run:
            import psutil
            psutil.cpu_percent(interval=None)
            data = collect_metrics(psutil, query_nvidia)
            encoded = encode_sample(data)
            print("OFFLINE ONLY | validated bounded PC telemetry | bytes=" + str(len(encoded)))
            return 0
        path = config_path()
        if args.configure:
            if args.credentials_file is None:
                parser.error("--configure requires --credentials-file")
            save_config(path, args.host, args.credentials_file)
            print("Local SHINO // LINK configuration saved. No password copied; no device contacted.")
            print("Auto-start remains opt-in and unchanged.")
            return 0
        if args.autostart:
            print("SHINO // LINK auto-start:", autostart(args.autostart, path))
            return 0
        config = load_config(path)
        if args.tray:
            return run_tray(config)
        engine = make_engine(config)
        if args.once:
            state = engine.step()
            print("One RAM-only sample:", state)
            return 0 if state == "CONNECTED" else 1
        stop = threading.Event()
        print("SHINO // LINK started (RAM-only metrics, Ctrl+C to stop).")
        try:
            engine.run(stop, lambda state: print("SHINO // LINK:", state, flush=True))
        except KeyboardInterrupt:
            stop.set()
            print("\nSHINO // LINK stopped; device metrics expire after six seconds.")
        return 0
    except (LinkError, SenderError, OSError) as exc:
        # These are deliberately sanitized errors; never print raw credentials,
        # HTTP challenges, config content or third-party tracebacks.
        print("SHINO // LINK STOP:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
