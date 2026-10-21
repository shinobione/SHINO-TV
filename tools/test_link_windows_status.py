"""Status menu is passive, dynamic and never a modal tray callback."""
import socket
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
import link_windows as app
from test_link_mode_tray import PYSTRAY


class StatusMenuTests(unittest.TestCase):
    def test_offline_status_is_disabled_submenu_without_modal_or_private_io(self):
        with patch.object(app,'message',side_effect=AssertionError('MODAL')), patch.object(socket,'socket',side_effect=AssertionError('NETWORK')):
            menu=app.status_menu(PYSTRAY,None,lambda:'DISCONNECTED')
            labels=[item.label() for item in menu.items]
            self.assertTrue(all(not item.enabled for item in menu.items))
            self.assertIn('Connexion : DISCONNECTED',labels)
            self.assertTrue(any('aucun envoi' in line for line in labels))
            self.assertTrue(any('aperçu PC' in line for line in labels))

    def test_live_fields_update_without_sampling_or_mutating_engine(self):
        engine=SimpleNamespace(accepted=2,attempts=3,failures=1,last_success=99.,clock=lambda:100.)
        state=['RETRYING']
        menu=app.status_menu(PYSTRAY,engine,lambda:state[0])
        first=[item.label() for item in menu.items]
        engine.accepted=3;engine.attempts=4;engine.failures=0;state[0]='CONNECTED'
        second=[item.label() for item in menu.items]
        self.assertIn('Mesures acceptées : 2 / 3',first)
        self.assertIn('Mesures acceptées : 3 / 4',second)
        self.assertIn('Connexion : CONNECTED',second)
        self.assertTrue(any('1000 ms' in line for line in second))
        self.assertEqual(engine.last_success,99.)

    def test_invalid_or_future_ack_does_not_claim_freshness(self):
        for stamp in (None,float('nan'),101.,'SECRET'):
            engine=SimpleNamespace(accepted=0,attempts=0,failures=0,last_success=stamp,clock=lambda:100.)
            labels=[item.label() for item in app.status_menu(PYSTRAY,engine,lambda:'DISCONNECTED').items]
            self.assertIn('Dernier ACK PC : indisponible',labels)
            self.assertFalse(any('SECRET' in line for line in labels))

    def test_native_popup_rebuilds_dynamic_labels_before_open_only(self):
        events=[]
        class Backend:
            def update_menu(self):events.append('refresh')
            def _on_notify(self,wparam,lparam):events.append(('notify',lparam))
        icon=app.tray_type(Backend)()
        icon._on_notify(0,0x205)
        self.assertEqual(events,['refresh',('notify',0x205)])
        events.clear();icon._on_notify(0,0x202)
        self.assertEqual(events,[('notify',0x202)])


if __name__=='__main__':unittest.main()
