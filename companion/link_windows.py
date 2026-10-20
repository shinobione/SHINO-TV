"""SHINO // LINK Windows V1. Same LINK protocol/engine; no firmware inspector.

Only explicit launch starts telemetry. --offline-preview never reads config,
credentials or sensors and has no sender. Nothing enables startup implicitly.
"""
from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import webbrowser

import shino_link as link
from link_mode_tray import ModeTrayController, build_preview_menu, passive_link_signals
from link_display_modes import Signals

VERSION = '1.0.0'
HOLD_LABEL = 'Diagnostic firmware #83 indisponible : coordination OTA HOLD'


def message(text, *, error=False):
    # Fixed/sanitized text only. Works with sys.stdout/sys.stderr == None.
    ctypes.windll.user32.MessageBoxW(None, text, 'SHINO // LINK V1', 0x10 if error else 0x40)


def tray_picture(state):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (64,64), '#141820')
    draw = ImageDraw.Draw(image)
    color = {'CONNECTED':'#80d9aa','RETRYING':'#ffbd59'}.get(state, '#d67575')
    draw.rounded_rectangle((5,5,58,58), radius=12, fill='#242e3a', outline='#c4a779', width=3)
    draw.line([(15,42),(24,22),(32,34),(41,17),(49,24)], fill=color, width=5, joint='curve')
    return image


def run_tray(engine, *, clock_host=None, setup_hook=None):
    import pystray
    offline = engine is None
    stop = threading.Event()
    status = {'value':'DISCONNECTED'}
    errors = []
    controller = ModeTrayController(lambda: passive_link_signals(engine, ttl_ms=link.METRICS_TTL_MS)
                                   if engine else Signals())

    def title():
        return 'SHINO // LINK V1' + (' · APERÇU HORS LIGNE' if offline else '') + ' · ' + status['value']

    def changed(value):
        status['value'] = value if value in ('CONNECTED','RETRYING') else 'DISCONNECTED'
        icon.title = title()
        icon.icon = tray_picture(status['value'])
        icon.update_menu()

    def dashboard(icon_, item):
        if engine:
            webbrowser.open('http://' + link.validate_host(engine.host) + '/')

    def details(icon_, item):
        if engine:
            data = engine.diagnostics()
            text = f"{status['value']}\nMesures acceptées : {data['accepted']} / {data['attempts']}\n"
            text += 'CPU / GPU / RAM / GPU temp : protocole LINK existant.\n'
            text += 'GPU indisponible si le pilote NVIDIA / nvidia-smi est absent.\n'
            text += 'Horloge : ' + ('option explicite active' if clock_host else 'option désactivée')
        else:
            text = 'DISCONNECTED — aperçu PC hors ligne. Aucun envoi, aucune mesure simulée.'
        message(text + '\nModes : aperçu PC uniquement.\n' + HOLD_LABEL)

    def quit_app(icon_, item):
        stop.set()
        icon_.stop()

    base = build_preview_menu(pystray, controller, status_supplier=lambda:status['value'],
                              open_dashboard=dashboard, quit_app=quit_app)
    items = list(base.items)
    # Preserve the existing preview menu and actions; do not instantiate #83.
    items[-2] = pystray.MenuItem('Ouvrir le dashboard SHINO // TV', dashboard, enabled=not offline)
    items[-1:-1] = [pystray.MenuItem('Consulter l’état', details),
                    pystray.MenuItem(HOLD_LABEL, lambda *_:None, enabled=False)]
    icon = pystray.Icon('SHINO_LINK_V1', tray_picture('DISCONNECTED'), title(), pystray.Menu(*items))

    def work():
        try:
            engine.run(stop, changed, target_supplier=lambda:link.load_config(link.config_path())['host'])
        except Exception:
            # Never expose an exception, URL, Digest header or credential path.
            errors.append('WORKER_STOPPED')
            changed('DISCONNECTED')

    worker = threading.Thread(target=work, name='SHINO-LINK-metrics', daemon=False) if engine else None

    def ready(ready_icon):
        ready_icon.visible = True
        if worker:
            worker.start()
        if setup_hook:
            try:
                setup_hook(ready_icon, stop, worker, controller, status)
            except Exception:
                errors.append('SMOKE_FAILED')
                quit_app(ready_icon, None)

    try:
        icon.run(setup=ready)
    finally:
        stop.set()
        if worker and worker.ident is not None:
            # Keep the shared instance lock until the in-flight operation ends.
            worker.join()
    return 1 if errors else 0


def autostart_command(clock_host=None):
    if getattr(sys, 'frozen', False):
        command = [sys.executable, '--tray']
    else:
        windowed = Path(sys.executable).with_name('pythonw.exe')
        if not windowed.is_file():
            raise link.LinkError('Windowed Python missing')
        command = [str(windowed), str(Path(__file__).with_name('shino_link_windows.pyw')), '--tray']
    if clock_host:
        command += ['--clock-b52-host', link.validate_host(clock_host)]
    return subprocess.list2cmdline(command)


def _registry():
    import winreg
    return winreg


def autostart(action, path, clock_host=None):
    reg = _registry()
    if action == 'enable':
        config = link.load_config(path)
        if clock_host and config['host'] != link.validate_host(clock_host):
            raise link.LinkError('Clock assertion mismatch')
    command = autostart_command(clock_host) if action != 'status' else None
    access = reg.KEY_QUERY_VALUE | (reg.KEY_SET_VALUE if action != 'status' else 0)
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, link.RUN_KEY, 0, access)
    except FileNotFoundError:
        if action != 'enable': return 'Désactivé'
        key = reg.CreateKeyEx(reg.HKEY_CURRENT_USER, link.RUN_KEY, 0, access)
    with key:
        try: existing, kind = reg.QueryValueEx(key, link.RUN_VALUE)
        except FileNotFoundError: existing, kind = None, None
        if action == 'status': return 'Activé' if existing is not None else 'Désactivé'
        if existing is not None and (kind != reg.REG_SZ or existing != command):
            raise link.LinkError('Auto-start entry differs; preserved')
        if action == 'enable': reg.SetValueEx(key, link.RUN_VALUE, 0, reg.REG_SZ, command)
        elif existing is not None: reg.DeleteValue(key, link.RUN_VALUE)
    return 'Activé' if action == 'enable' else 'Désactivé'


class ArgumentError(ValueError): pass


class Parser(argparse.ArgumentParser):
    def error(self, text): raise ArgumentError()
    def exit(self, status=0, message=None): raise ArgumentError()


def main(argv=None):
    parser = Parser(add_help=False)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--tray', action='store_true')
    actions.add_argument('--offline-preview', action='store_true')
    actions.add_argument('--configure', action='store_true')
    actions.add_argument('--autostart', choices=('status','enable','disable'))
    actions.add_argument('--self-test', type=Path)
    actions.add_argument('--self-test-lock', type=Path)
    actions.add_argument('--help', action='store_true')
    parser.add_argument('--host', default=link.DEFAULT_HOST)
    parser.add_argument('--credentials-file', type=Path)
    parser.add_argument('--clock-b52-host')
    try:
        args = parser.parse_args(argv)
        if args.clock_b52_host and (args.offline_preview or args.self_test or args.configure or args.help):
            raise ArgumentError()
        if args.help:
            message('SHINO // LINK V1\nDouble-clic : télémétrie avec configuration existante.\n'
                    '--offline-preview : tray hors ligne sans configuration ni réseau.\n'
                    '--configure --host IP --credentials-file FICHIER : configuration locale.\n'
                    '--autostart status|enable|disable : action explicite uniquement.\n'
                    '--clock-b52-host IP : option horloge explicite pour cible vérifiée.')
            return 0
        if args.self_test:
            from link_windows_smoke import run
            return run(args.self_test)
        if args.self_test_lock:
            import json
            try:
                with link.link_instance(directory=args.self_test_lock.parent/'test-instance'):
                    value = 'UNEXPECTED_ACQUIRED'
            except link.LinkError:
                value = 'EXCLUDED'
            with args.self_test_lock.open('x', encoding='utf-8') as stream:
                json.dump({'instance':value}, stream)
            return 0 if value == 'EXCLUDED' else 1
        if args.offline_preview:
            with link.link_instance(directory=link.config_path().parent/'preview-instance'):
                return run_tray(None)
        if args.configure:
            if args.credentials_file is None: raise ArgumentError()
            link.save_config(link.config_path(), args.host, args.credentials_file)
            message('Configuration locale enregistrée. Aucun envoi. Démarrage automatique inchangé.')
            return 0
        if args.autostart:
            value = autostart(args.autostart, link.config_path(), args.clock_b52_host)
            message('Démarrage automatique : ' + value)
            return 0
        try:
            with link.link_instance():
                config = link.load_config(link.config_path())
                engine = link.make_engine(config, clock_b52_host=args.clock_b52_host)
                return run_tray(engine, clock_host=args.clock_b52_host)
        except link.LinkError as exc:
            if str(exc) == 'LINK already running or instance lock unavailable':
                message('LINK est déjà en cours, ou son verrou est indisponible. Aucun nouvel envoi.', error=True)
                return 1
            raise
    except ArgumentError:
        message('Options invalides. Utilisez --help pour les commandes de SHINO // LINK V1.', error=True)
        return 2
    except (link.LinkError, link.SenderError, ValueError, OSError):
        message('Impossible de démarrer : configuration locale absente, invalide ou inaccessible, '
                'identifiants indisponibles, ou action autostart refusée.\n'
                'Configuration attendue : %LOCALAPPDATA%\\SHINO-TV\\link.json.\n'
                'Pour essayer sans réseau : SHINO-LINK.exe --offline-preview.', error=True)
        return 1
    except ImportError:
        message('Dépendance Windows indisponible. Le paquet EXE doit être reconstruit.', error=True)
        return 1
    except Exception:
        message('SHINO // LINK arrêté suite à une erreur locale. Aucun diagnostic privé affiché.', error=True)
        return 1
