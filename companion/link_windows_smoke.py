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


def native_menu_cycles(icon, controller, *, cycles=3, modes=True, quit_at_end=True):
    """Actual TrackPopupMenuEx and WM_CHAR/Escape selection, own HWNDs only.

    No direct Python MenuItem calls, mocked popup result or global keyboard input.
    WM_CANCELMODE is insufficient for this backend: EndMenu is dispatched on
    the real Win32 loop thread through this test-only private message handler.
    """
    from ctypes import wintypes as W
    api=ctypes.windll.user32
    api.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
    api.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    api.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    api.GetSubMenu.argtypes=[W.HMENU,ctypes.c_int];api.GetSubMenu.restype=W.HMENU
    api.GetMenuStringW.argtypes=[W.HMENU,ctypes.c_uint,W.LPWSTR,ctypes.c_int,ctypes.c_uint]
    api.GetMenuState.argtypes=[W.HMENU,ctypes.c_uint,ctypes.c_uint]
    api.GetMenuItemCount.argtypes=[W.HMENU]
    callback_type=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    log=[]
    checks={}
    cancel_message=0x8062
    gui_thread=api.GetWindowThreadProcessId(icon._hwnd,None)

    def own_windows(kind):
        result=[]
        def each(hwnd,_):
            pid=W.DWORD();api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            name=ctypes.create_unicode_buffer(128);api.GetClassNameW(hwnd,name,128)
            if pid.value==os.getpid() and name.value==kind and api.IsWindowVisible(hwnd):result.append(hwnd)
            return True
        callback=callback_type(each);api.EnumWindows(callback,0)
        return result

    def until(fn,seconds=3):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            value=fn()
            if value:return value
            time.sleep(.02)
        raise AssertionError('Native menu deadline')

    def char(hwnd,value):
        api.PostMessageW(hwnd,0x102,ord(value),0)
        time.sleep(.05)

    def cancel(*_):
        assert threading.get_native_id()==gui_thread
        api.EndMenu()

    icon._message_handlers[cancel_message]=cancel

    def open_root():
        assert not own_windows('#32768')
        api.PostMessageW(icon._hwnd,1035,0,0x205)
        root=until(lambda:own_windows('#32768'))[0]
        assert not own_windows('#32770'),'Tray must never open a dialog'
        return root

    def submenu(root,letter):
        char(root,letter)
        return until(lambda:[h for h in own_windows('#32768') if h!=root])[0]

    try:
        for cycle in range(cycles):
            root=open_root()
            sub=submenu(root,'c')
            position=next(i for i,item in enumerate(icon.menu.items) if item.text=='Consulter l’état')
            handle=api.GetSubMenu(icon._menu_handle[0],position)
            assert handle,'Status must be a native submenu'
            lines=[]
            count=api.GetMenuItemCount(handle)
            for i in range(count):
                text=ctypes.create_unicode_buffer(512)
                api.GetMenuStringW(handle,i,text,512,0x400)
                assert api.GetMenuState(handle,i,0x400)&3,'Status lines must be disabled'
                lines.append(text.value)
            assert lines and not own_windows('#32770')
            api.PostMessageW(sub,0x100,0x1b,0) # Escape only in our actual submenu.
            until(lambda:len(own_windows('#32768'))==1)
            api.PostMessageW(icon._hwnd,cancel_message,0,0)
            until(lambda:not own_windows('#32768'))
            log.append(dict(cycle=cycle,status_lines=lines,submenu_escape_closed=True,root_closed=True))
        checks['native_status_cycles']=len(log)==cycles
        checks['native_no_dialog']=not own_windows('#32770')
        if modes:
            for mode,keys in ((DisplayMode.AUTO,'a'),(DisplayMode.CLOCK_WEATHER,'h'),
                              (DisplayMode.MONITORING,'m'),(DisplayMode.MUSIC,'mm')):
                root=open_root();sub=submenu(root,'m')
                for key in keys:char(sub,key)
                if keys.startswith('m'):
                    api.PostMessageW(sub,0x100,0x0d,0)
                until(lambda:not own_windows('#32768'))
                until(lambda:controller.mode() is mode)
            checks['native_four_radio_selections']=True
        if quit_at_end:
            root=open_root();char(root,'q')
            until(lambda:not own_windows('#32768'))
            checks['native_quit_selected']=True
        return dict(checks=checks,cycles=log,win32_thread=gui_thread,
                    selection='ACTUAL_NATIVE_POPUP_WM_CHAR_NOT_DIRECT_CALLBACK')
    finally:
        if own_windows('#32768'):
            api.PostMessageW(icon._hwnd,cancel_message,0,0)



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
    native = []
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
        # Dashboard is deliberately intercepted, never a browser or device.
        entries[-4](icon)
        checks['dashboard_action'] = actions == ['dashboard']
        native.append(native_menu_cycles(icon, controller, quit_at_end=False))
        deadline = time.monotonic() + 17
        while len(states) < 4 and time.monotonic() < deadline:
            time.sleep(.05)
        checks['disconnect_reconnect'] = states[:4] == ['RETRYING','CONNECTED','RETRYING','CONNECTED']
        checks['accepted_telemetry'] = engine.accepted >= 2
        checks['tooltip_connected'] = 'CONNECTED' in icon.title
        native.append(native_menu_cycles(icon, controller, cycles=1, modes=False))
        checks['native_status_refresh'] = (native[0]['cycles'][0]['status_lines'] !=
                                           native[1]['cycles'][0]['status_lines'])
        checks['native_connected_status'] = 'Connexion : CONNECTED' in native[1]['cycles'][0]['status_lines']

    try:
        with patch.dict(os.environ, {'LOCALAPPDATA':str(profile)}), \
             patch.object(socket, 'socket', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'gethostbyname', deny), \
             patch.object(link, 'config_path', return_value=profile/'link.json'), \
             patch.object(app.webbrowser, 'open', side_effect=lambda *_:actions.append('dashboard')), \
             patch.object(app, 'message', side_effect=AssertionError('NO_TRAY_MODAL')):
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
                native.append(native_menu_cycles(icon, controller))
            checks['offline_preview_exit'] = app.run_tray(None, setup_hook=preview_setup) == 0
            checks['native_menu_checks'] = all(all(v is True for v in proof['checks'].values()) for proof in native) and len(native)==3
            checks['zero_network_attempts'] = not denied
    except Exception as error:
        checks['exception'] = type(error).__name__
    ok = bool(checks) and all(value is True for value in checks.values())
    destination.write_text(json.dumps(dict(verdict='PASS' if ok else 'FAIL',
        scope='FROZEN_WIN32_OFFLINE_SYNTHETIC_FIXTURE_NOT_DEVICE',checks=checks,
        states=states, native_menus=native, owner_desktop_smoke='OWNER_RETEST_NOT_RUN'), indent=2), encoding='utf-8')
    return 0 if ok else 1
