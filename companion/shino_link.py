"""SHINO // LINK — opt-in Windows tray companion for the already-installed V2.1.

PC-side ONLY. Uses the existing validated per-build Digest RAM telemetry sender.
No OTA, media/image upload, Windows Wi-Fi switching, device scanning,
registry modification except a *separately requested* per-user auto-start action.
Neither a config command nor a dry run contacts the SmallTV.
"""
from __future__ import annotations

import argparse
from collections import deque
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
    SenderError, SendStatus, encode_sample, make_opener, read_credentials, send_sample, validate_host,
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

    def __init__(self, host: str, opener, sampler, sender=send_sample,
                 clock=time.monotonic, opener_factory=None):
        self.host = validate_host(host)
        self.opener = opener
        self.sampler = sampler
        self.sender = sender
        self.clock = clock
        self.opener_factory = opener_factory
        self.generation = 1
        self.attempts = 0
        self.accepted = 0
        self.last_result = None
        self.history = deque(maxlen=64)
        self.next_due = 0.0
        self.failures = 0
        self.state = "WAITING"

    def retarget(self, host: str) -> None:
        host=validate_host(host)
        if host==self.host: return
        self.host=host
        self.opener=None
        self.failures=0
        self.next_due=0
        self.state="WAITING"

    def step(self, now: float | None = None) -> str:
        use_live_clock = now is None
        now = self.clock() if use_live_clock else now
        if now < self.next_due:
            return self.state
        started = self.clock()
        try:
            sample = self.sampler()
            encode_sample(sample)  # Do not send invalid, stale or unbounded readings.
        except Exception:
            result = SendStatus.INVALID_SAMPLE
        else:
            try:
                if self.opener is None:
                    self.opener = self.opener_factory()
                    self.generation += 1
                sent = self.sender(self.host, self.opener, sample, timeout=3.0)
                # Existing injected bool senders stay supported; enum truthiness is not success.
                result = sent if isinstance(sent, SendStatus) else SendStatus.ACCEPTED if sent is True else SendStatus.CLIENT_ERROR
            except Exception:
                result = SendStatus.CLIENT_ERROR
        self.last_result = result
        self.attempts += 1
        accepted = result is SendStatus.ACCEPTED
        if accepted:
            self.accepted += 1
            self.failures = 0
            self.state = "CONNECTED"
            delay = CONNECTED_INTERVAL_SECONDS
        else:
            self.failures += 1
            self.state = "RETRYING"
            delay = min(MAX_RETRY_SECONDS, 2.0 * (2 ** min(self.failures - 1, 4)))
            if self.opener_factory and (result in (
                    SendStatus.NO_ROUTE_TIMEOUT, SendStatus.CONNECTION, SendStatus.NETWORK_ERROR,
                    SendStatus.HTTP_401, SendStatus.HTTP_403, SendStatus.CLIENT_ERROR) or
                    (result is SendStatus.MALFORMED and self.failures % 3 == 0)):
                # Fresh state on NEXT scheduled attempt. No immediate POST/retry loop.
                self.opener = None
        # Delay is measured AFTER collection/HTTP completes, so a 3s timeout
        # cannot accidentally turn a 2s retry into an immediate retry storm.
        completed = self.clock() if use_live_clock else now
        self.next_due = completed + delay
        self.history.append({'attempt': self.attempts, 'result': result.value,
                             'http_status': 200 if accepted else 401 if result is SendStatus.HTTP_401 else 403 if result is SendStatus.HTTP_403 else None,
                             'generation': self.generation, 'failures': self.failures,
                             'completed_monotonic': completed, 'retry_seconds': delay,
                             'duration_ms': round(max(0, self.clock() - started) * 1000, 3)})
        return self.state

    def diagnostics(self) -> dict:
        return {'state': self.state, 'attempts': self.attempts, 'accepted': self.accepted,
                'generation': self.generation, 'failures': self.failures,
                'history': list(self.history)}

    def run(self, stop: threading.Event, report, observe=None, target_supplier=None) -> None:
        last_state = None
        last_attempt = 0
        while not stop.is_set():
            if target_supplier:
                try: self.retarget(target_supplier())
                except (OSError,ValueError): pass
            state = self.step()
            if state != last_state:
                report(state)
                last_state = state
            if observe and self.attempts != last_attempt:
                last_attempt = self.attempts
                try:
                    observe(self.diagnostics())
                except OSError:
                    pass # Diagnostics must not stop telemetry or expose local paths.
            # Never spin or immediately retry on a network/collection failure.
            stop.wait(max(0.01, self.next_due - self.clock()))


def make_engine(config: dict[str, str]) -> LinkEngine:
    # Lazy import: --dry-run/configure/autostart status never need to read secrets
    # or contact the device. The credentials file is never copied into link.json.
    user, password = read_credentials(Path(config["credentials_file"]))
    factory = lambda: make_opener(config["host"], user, password)
    opener = factory()
    import psutil
    psutil.cpu_percent(interval=None)  # Prime nonblocking first CPU sample.
    engine=LinkEngine(config["host"], opener,
                      lambda: collect_metrics(psutil, query_nvidia), opener_factory=factory)
    engine.opener_factory=lambda: make_opener(engine.host,user,password)
    return engine


def diagnostics_writer(path: Path):
    """Opt-in bounded sanitized snapshot, never a raw HTTP/credential log."""
    def write(data):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                             prefix='.shino-diag-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, allow_nan=False)
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return write


def run_tray(config: dict[str, str], observe=None) -> int:
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
    worker = threading.Thread(target=engine.run, args=(stop, state_changed, observe, lambda: load_config(config_path())["host"]),
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
    actions.add_argument("--set-target",action="store_true",help="Change existing sender's LAN IP without starting another sender")
    actions.add_argument("--recovery-target",action="store_true",help="Retarget existing sender to private AP; does not change Windows Wi-Fi")
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
    parser.add_argument('--diagnostics-file', type=Path,
                        help='Optional bounded sanitized status snapshot for --run/--tray')
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
        if args.set_target or args.recovery_target:
            current=load_config(path)
            save_config(path,DEFAULT_HOST if args.recovery_target else args.host,Path(current["credentials_file"]))
            print("Existing sender target updated locally; no device contacted or new sender started.")
            return 0
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
        observe = diagnostics_writer(args.diagnostics_file) if args.diagnostics_file else None
        if args.tray:
            return run_tray(config, observe)
        engine = make_engine(config)
        if args.once:
            state = engine.step()
            print("One RAM-only sample:", state)
            return 0 if state == "CONNECTED" else 1
        stop = threading.Event()
        print("SHINO // LINK started (RAM-only metrics, Ctrl+C to stop).")
        try:
            engine.run(stop, lambda state: print("SHINO // LINK:", state, flush=True), observe,
                       lambda: load_config(path)["host"])
        except KeyboardInterrupt:
            stop.set()
            print("\nSHINO // LINK stopped; device metrics expire after six seconds.")
        return 0
    except (LinkError, SenderError) as exc:
        # These are deliberately sanitized errors; never print raw credentials,
        # HTTP challenges, config content or third-party tracebacks.
        print("SHINO // LINK STOP:", exc, file=sys.stderr)
        return 1
    except OSError:
        print('SHINO // LINK STOP: local file unavailable', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
