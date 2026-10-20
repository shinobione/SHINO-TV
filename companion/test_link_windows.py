"""Windows V1: safe entry, frozen commands, existing protocol and no inspector."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import shino_link as link
import link_windows as app


class WindowsV1Tests(unittest.TestCase):
    def test_frozen_autostart_uses_real_exe_even_with_spaces(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', 'C:/Apps/SHINO LINK.exe'):
            self.assertEqual(app.autostart_command(), subprocess.list2cmdline(['C:/Apps/SHINO LINK.exe', '--tray']))

    def test_frozen_autostart_preserves_explicit_clock_opt_in(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', 'C:/Apps/LINK.exe'):
            self.assertIn('--clock-b52-host 192.168.1.70', app.autostart_command('192.168.1.70'))

    def test_offline_preview_never_loads_config_or_sends(self):
        with patch.object(link, 'load_config', side_effect=AssertionError('private config')), patch.object(link, 'make_engine', side_effect=AssertionError('sender')), patch.object(app, 'run_tray', return_value=0) as tray, patch.object(link, 'link_instance'):
            self.assertEqual(app.main(['--offline-preview']), 0)
            self.assertIsNone(tray.call_args.args[0])

    def test_default_launch_acquires_instance_before_configuration(self):
        with patch.object(link, 'link_instance', side_effect=link.LinkError('LINK already running or instance lock unavailable')), patch.object(link, 'load_config', side_effect=AssertionError('config')), patch.object(app, 'message') as msg:
            self.assertEqual(app.main([]), 1)
            self.assertIn('déjà', msg.call_args.args[0])

    def test_missing_config_is_visible_and_never_builds_sender(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(link, 'config_path', return_value=Path(folder)/'link.json'), patch.object(link, 'make_engine', side_effect=AssertionError('sender')), patch.object(app, 'message') as msg:
            self.assertEqual(app.main([]), 1)
            self.assertIn('configuration', msg.call_args.args[0])

    def test_invalid_options_show_error_before_private_io(self):
        with patch.object(link, 'load_config', side_effect=AssertionError('config')), patch.object(app, 'message') as msg:
            self.assertEqual(app.main(['--not-an-option']), 2)
            self.assertTrue(msg.called)

    def test_offline_preview_rejects_clock_assertion(self):
        with patch.object(app, 'message'), patch.object(link, 'make_engine', side_effect=AssertionError('sender')):
            self.assertEqual(app.main(['--offline-preview', '--clock-b52-host', '192.168.1.70']), 2)

    def test_dependency_failure_has_sanitized_message(self):
        with patch.object(link, 'link_instance'), patch.object(link, 'load_config', return_value={'host':'192.168.1.70'}), patch.object(link, 'make_engine', side_effect=ImportError('SECRET')), patch.object(app, 'message') as msg:
            self.assertEqual(app.main([]), 1)
            self.assertNotIn('SECRET', msg.call_args.args[0])

    def test_autostart_refuses_other_entry_without_writing(self):
        registry = {'value':'existing pythonw.exe --tray', 'writes':0}
        class Key:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Reg:
            HKEY_CURRENT_USER=1; KEY_QUERY_VALUE=1; KEY_SET_VALUE=2; REG_SZ=1
            def OpenKey(self, *args): return Key()
            def QueryValueEx(self, *args): return registry['value'], 1
            def SetValueEx(self, *args): registry['writes'] += 1
        with patch.object(app, '_registry', return_value=Reg()), patch.object(link, 'load_config'), patch.object(app, 'autostart_command', return_value='new.exe --tray'):
            with self.assertRaises(link.LinkError): app.autostart('enable', Path('unused'))
        self.assertEqual(registry['writes'], 0)

    def test_status_missing_registry_key_does_not_create_it(self):
        class Reg:
            HKEY_CURRENT_USER=1; KEY_QUERY_VALUE=1; KEY_SET_VALUE=2
            def OpenKey(self, *args): raise FileNotFoundError()
        with patch.object(app, '_registry', return_value=Reg()):
            self.assertEqual(app.autostart('status', Path('unused')), 'Désactivé')

    def test_picture_state_colors_are_distinct_and_small(self):
        images = [app.tray_picture(state) for state in ('CONNECTED','RETRYING','DISCONNECTED')]
        self.assertTrue(all(im.size == (64,64) for im in images))
        self.assertEqual(len({im.tobytes() for im in images}), 3)

    def test_existing_config_schema_is_reused_without_copying_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'link.json'
            path.write_text(json.dumps({'schema':1,'host':'192.168.1.70','credentials_file':str(Path(folder)/'private.txt')}))
            before=path.read_bytes()
            self.assertEqual(link.load_config(path)['host'], '192.168.1.70')
            self.assertEqual(path.read_bytes(),before)


if __name__ == '__main__': unittest.main()
