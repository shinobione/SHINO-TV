"""Explicit offline qualification of the frozen EXE. Never a live sender.

Hard-deny sockets/DNS; synthetic fixture clearly labelled; private test profile;
actual Win32 tray/menu and existing LINK engine, no inspector or registry access.
"""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from unittest.mock import patch

import shino_link as link
from link_display_modes import DisplayMode


def run(destination):
    import link_windows as app
    import psutil
    from PIL import Image
    from metrics_server import collect_metrics
    destination = Path(destination).absolute()
    # Do not replace evidence or use the real profile, even when called directly.
    with destination.open('x', encoding='utf-8') as stream:
        stream.write('{}')
    profile = destination.parent / (destination.stem + '-profile')
    profile.mkdir(exist_ok=False)
    states = []
    actions = []
    checks = {}
    denied = []

    def deny(*args, **kwargs):
        denied.append('NETWORK_ATTEMPT')
        raise AssertionError('Network forbidden')

    sample = dict(ok=True,cpu_usage=22.5,gpu_usage=60.0,memory_used_gb=7.25,
                  memory_total_gb=16.0,gpu_vram_mb=2700.0,gpu_temp_c=49.0,
                  gpu_power=85.0,gpu_available=True)
    responses = iter([False, True, False, True])
    requests = []
    class Reply:
        headers = {'Content-Length':'50'}
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def getcode(self): return 200
        def read(self, limit):
            return b'{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}'
    class FakeHTTP:
        def open(self, request, timeout):
            assert request.full_url == 'http://192.168.1.70/api/v1/bridge/metrics'
            assert request.get_method() == 'POST' and timeout == 3.0
            assert json.loads(request.data) == sample
            requests.append('POST_LINK_METRICS')
            if not next(responses, True): raise TimeoutError()
            return Reply()
    engine = link.LinkEngine('192.168.1.70', FakeHTTP(), lambda:sample.copy(),
                             sender=link.coordinated_link_sender, opener_factory=FakeHTTP)
    original_run = engine.run
    def tracked_run(stop, report, **kwargs):
        def tracked(state):
            states.append(state)
            report(state)
        return original_run(stop, tracked, **kwargs)
    engine.run = tracked_run

    def setup(icon, stop, worker, controller, status):
        checks['tray_visible'] = icon.visible
        checks['win32_hwnd'] = bool(icon._hwnd)
        checks['native_menu_handle'] = bool(icon._menu_handle[0])
        checks['single_worker'] = sum(t.name=='SHINO-LINK-metrics' for t in threading.enumerate()) == 1
        checks['worker_guard_excludes_duplicate'] = not engine._worker_guard.acquire(False)
        entries = icon.menu.items
        checks['inspector_disabled'] = any(item.text == app.HOLD_LABEL and not item.enabled for item in entries)
        radio = entries[1].submenu.items
        for index, mode in enumerate(DisplayMode):
            radio[index](icon)
            assert controller.mode() is mode
        checks['preview_radio_callbacks'] = True
        # Deliberate dashboard menu activation is intercepted; no browser/network.
        entries[-4](icon)
        checks['dashboard_action'] = actions == ['dashboard']
        entries[-3](icon)
        checks['status_action'] = actions[-1] == 'status'
        deadline = time.monotonic() + 17
        while len(states) < 4 and time.monotonic() < deadline:
            time.sleep(.05)
        checks['disconnect_reconnect'] = states[:4] == ['RETRYING','CONNECTED','RETRYING','CONNECTED']
        checks['accepted_telemetry'] = engine.accepted >= 2
        checks['tooltip_connected'] = 'CONNECTED' in icon.title
        entries[-1](icon)

    try:
        with patch.dict(os.environ, {'LOCALAPPDATA':str(profile)}), \
             patch.object(socket, 'socket', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'gethostbyname', deny), \
             patch.object(link, 'config_path', return_value=profile/'link.json'), \
             patch.object(app.webbrowser, 'open', side_effect=lambda *_:actions.append('dashboard')), \
             patch.object(app, 'message', side_effect=lambda *_args, **_kwargs:actions.append('status')):
            checks['no_console'] = not ctypes.windll.kernel32.GetConsoleWindow()
            checks['frozen'] = bool(getattr(sys,'frozen',False))
            resource = Path(__file__).with_name('link_windows.ico')
            with Image.open(resource) as image:
                checks['bundled_icon'] = image.format == 'ICO'
            # Real sensors are collected offline. GPU absence remains explicit.
            data = collect_metrics(psutil, lambda:None)
            checks['actual_cpu_ram_collection'] = bool(link.encode_sample(data)) and not data['gpu_available']
            lock_report = profile/'lock.json'
            with link.link_instance(directory=profile/'test-instance'):
                command = [sys.executable, '--self-test-lock', str(lock_report)]
                if not checks['frozen']:
                    command = [sys.executable, str(Path(app.__file__).with_name('shino_link_windows.pyw')), '--self-test-lock', str(lock_report)]
                child = subprocess.run(command, timeout=25, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            checks['process_exclusion'] = child.returncode == 0 and json.loads(lock_report.read_text())['instance']=='EXCLUDED'
            with link.link_instance(directory=profile/'test-instance'):
                checks['lock_released_after_exit'] = True
            result = app.run_tray(engine, setup_hook=setup)
            checks['clean_tray_exit'] = result == 0
            checks['worker_stopped'] = not any(t.name=='SHINO-LINK-metrics' for t in threading.enumerate())
            checks['real_protocol_fake_http'] = len(requests) >= 4
            checks['worker_lock_released'] = engine._worker_guard.acquire(False)
            if checks['worker_lock_released']: engine._worker_guard.release()
            def preview_setup(icon, stop, worker, controller, status):
                checks['offline_preview_visible'] = icon.visible and 'APERÇU HORS LIGNE' in icon.title
                checks['offline_preview_has_no_worker'] = worker is None
                checks['offline_dashboard_disabled'] = not icon.menu.items[-4].enabled
                icon.menu.items[-1](icon)
            checks['offline_preview_exit'] = app.run_tray(None, setup_hook=preview_setup) == 0
            checks['zero_network_attempts'] = not denied
    except Exception as error:
        checks['exception'] = type(error).__name__
    ok = bool(checks) and all(value is True for value in checks.values())
    destination.write_text(json.dumps(dict(verdict='PASS' if ok else 'FAIL',
        scope='FROZEN_WIN32_OFFLINE_SYNTHETIC_FIXTURE_NOT_DEVICE',checks=checks,
        states=states, owner_desktop_smoke='NOT_RUN'), indent=2), encoding='utf-8')
    return 0 if ok else 1
