"""Issue #83: HOST-only end-to-end tray -> one-shot Digest GET -> view model."""
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from shino_b5_get_diagnostic import DiagnosticStop
from test_shino_b5_get_diagnostic import (
    HOST, PASSWORD, RELEASE, Server, PassiveTimer, update_payload,
)
from link_firmware_identity import (
    ENDPOINT, FirmwareMenuAction, IdentityOnlyReader, local_ota_hold,
    matching_receipt, read_firmware_identity, validate_identity,
)
from link_mode_tray import ModeTrayController, build_preview_menu
from link_display_modes import Signals
from test_link_mode_tray import PYSTRAY, FakeIcon


class ModelTests(unittest.TestCase):
    def test_full_source_equivalent_identity_and_non_ota_release_filter(self):
        original = update_payload()
        actual = validate_identity(original)
        self.assertEqual(actual["bytes"], RELEASE["bytes"])
        self.assertEqual(actual["build_id"], RELEASE["build_id"])
        modified = dict(original, heap=1500, block=1000, stack=1800,
                        fs_ok=False, ota_enabled=False, last_update="STAGED_PENDING_BOOT")
        self.assertEqual(validate_identity(modified)["last_update"], "STAGED_PENDING_BOOT")

    def test_invalid_schema_never_fabricates_a_version(self):
        source = update_payload()
        candidates = [
            dict(source, bytes=True), dict(source, bytes=-1),
            dict(source, device="wrong"), dict(source, sha256="f"*63),
            dict(source, protocol="unexpected"), dict(source, boot_id="Q"*32),
            dict(source, descriptor="Forged"), dict(source, last_update="x\nSECRET"),
            dict(source, ota_enabled=1), dict(source, extra="unvalidated"),
            {k:v for k,v in source.items() if k != "bytes"},
            dict(source, block=90000), dict(source, frag=101),
        ]
        for item in candidates:
            with self.subTest(sample=list(item)), self.assertRaises(DiagnosticStop):
                validate_identity(item)

    def test_byte_inspected_catalog_only_or_unknown(self):
        ident=validate_identity(update_payload())
        with tempfile.TemporaryDirectory() as root:
            home=Path(root)
            catalog=home/"firmware-receipts.json"
            release={k: ident[k] for k in ("device","build_id","sha256","bytes")}
            good_bin=home/"exact.bin"
            good_manifest=home/"exact.json"
            good_bin.write_bytes(b"test")
            good_manifest.write_text("{}")
            entry={"name":"P0+Updater512", "bin":str(good_bin),
                   "manifest":str(good_manifest)}
            catalog.write_text(json.dumps({"schema":1,"receipts":[entry]}))
            # Real inspect() already cryptographically validates BIN+manifest.
            with patch("link_firmware_identity.inspect_release",
                       return_value=(release,b"bytes")) as checked:
                self.assertEqual(matching_receipt(ident,catalog),"P0+Updater512")
                checked.assert_called_once()
            other=dict(release,sha256="e"*64)
            with patch("link_firmware_identity.inspect_release",
                       return_value=(other,b"bytes")):
                self.assertIsNone(matching_receipt(ident,catalog))
            catalog.write_text('{"schema":1,"schema":1,"receipts":[]}')
            self.assertIsNone(matching_receipt(ident,catalog))
            catalog.unlink()
            self.assertIsNone(matching_receipt(ident,catalog))

    def test_known_one_shot_attempt_blocks_before_any_credentials(self):
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)
            (directory/"physical-ota.attempt").write_text("STOP_UNKNOWN_NO_RETRY")
            self.assertTrue(local_ota_hold(directory))
            with patch("link_firmware_identity.read_credentials",
                       side_effect=AssertionError("Do not read secrets")):
                result=read_firmware_identity(HOST,directory/"nope",directory)
            self.assertEqual(result["state"],"HOLD")
            self.assertFalse(result.get("receipt"))
            self.assertTrue((directory/"physical-ota.attempt").exists())


class ActualDigestTransportTests(unittest.TestCase):
    def setUp(self):
        self.server=Server()

    def reader(self):
        return IdentityOnlyReader(
            HOST,PASSWORD,connection_factory=self.server.connection,
            timer_factory=PassiveTimer,
        )

    def test_real_transport_one_401_one_200_no_post(self):
        data=self.reader().identity()
        self.assertEqual(data["sha256"],RELEASE["sha256"])
        self.assertEqual([x["method"] for x in self.server.requests],["GET","GET"])
        self.assertEqual([x["path"] for x in self.server.requests],[ENDPOINT,ENDPOINT])

    def test_unexpected_identity_is_valid_but_unknown(self):
        modified=dict(update_payload(),sha256="e"*64)
        self.server.payloads[ENDPOINT]=modified
        result=self.reader().identity()
        self.assertEqual(result["sha256"],"e"*64)

    def test_invalid_digest_or_response_never_confirms(self):
        samples=[("always_401",True),("unauthenticated_200",True),
                 ("forced_status",403),("forced_status",302),
                 ("body_override",b"<html>bad</html>"),
                 ("body_override",b"{" + b"X"*5000 + b"}")]
        for attribute,value in samples:
            with self.subTest(attribute=attribute,value=str(value)[:24]):
                server=Server()
                setattr(server,attribute,value)
                reader=IdentityOnlyReader(HOST,PASSWORD,
                       connection_factory=server.connection,
                       timer_factory=PassiveTimer)
                with self.assertRaises(DiagnosticStop):
                    reader.identity()
                self.assertLessEqual(len(server.requests),2)
                self.assertTrue(all(req["method"]=="GET" and req["path"]==ENDPOINT for req in server.requests))

    def test_unknown_or_wrong_device_output_does_not_claim_receipt(self):
        self.server.payloads[ENDPOINT]=dict(update_payload(),
                     device="fedcba9876543210",
                     descriptor="SHINO-HTTP-OTA-1|fedcba9876543210|"+
                                RELEASE["build_id"]+"|4m2m|APP_ONLY")
        result=self.reader().identity()
        self.assertEqual(result["device"],"fedcba9876543210")


class MenuIntegrationTests(unittest.TestCase):
    def test_menu_click_is_async_single_flight_no_poll(self):
        called=threading.Event()
        release=threading.Event()
        done=threading.Event()
        def slow():
            called.set()
            self.assertTrue(release.wait(3))
            done.set()
            return {"state":"READ", "version":"Version inconnue — identité lue",
                    "build":"b"*12,"sha":"a"*12,"bytes":65536,
                    "checked":"2026-10-19 20:00 CET","ota":"activée (déclarée)",
                    "fs":"OK déclaré", "last_update":"NONE", "receipt":False}
        action=FirmwareMenuAction(slow)
        mode=ModeTrayController(lambda:Signals())
        menu=build_preview_menu(PYSTRAY,mode,status_supplier=lambda:"CONNECTED",
            open_dashboard=lambda *x: None,quit_app=lambda *x:None,
            firmware_action=action)
        icon=FakeIcon()
        self.assertEqual(len(menu.items[1].action.items),4)
        self.assertIn("Vérifier le firmware",menu.items[4].label())
        self.assertFalse(called.is_set())
        menu.items[4].action(icon,menu.items[4])
        self.assertTrue(called.wait(2))
        self.assertEqual(action.snapshot()["state"],"READING")
        self.assertIn("lecture en cours", menu.items[5].action.items[0].label())
        self.assertFalse(action.start(icon))
        release.set()
        self.assertTrue(done.wait(2))
        for _ in range(100):
            if action.snapshot()["state"]=="READ":break
            time.sleep(0.01)
        self.assertEqual(action.snapshot()["state"],"READ")
        self.assertIn("inconnue",menu.items[5].action.items[0].label())
        action.close()

    def test_catch_sanitized_errors_without_retry(self):
        times=[]
        done=threading.Event()
        def fails():
            times.append("GET")
            done.set()
            raise DiagnosticStop("SECOND_401")
        action=FirmwareMenuAction(fails)
        icon=FakeIcon()
        self.assertTrue(action.start(icon))
        self.assertTrue(done.wait(2))
        for _ in range(100):
            if action.snapshot()["state"]=="ERROR":break
            time.sleep(0.01)
        self.assertEqual(len(times),1)
        self.assertIn("Authentification",action.line("version"))
        action.close()

    def test_click_path_reads_credentials_and_real_model_only_on_user_action(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"creds.txt"
            path.write_text("not real credentials")
            calls=[]
            class FakeReader:
                def __init__(self,host,password):
                    calls.append(("init",host))
                def identity(self):
                    calls.append(("read",ENDPOINT))
                    return validate_identity(update_payload())
            with patch("link_firmware_identity.read_credentials",
                       return_value=("shino", PASSWORD)):
                result=read_firmware_identity(HOST,path,Path(root),
                       reader_factory=FakeReader,
                       now=datetime(2026,10,19,20,0,tzinfo=timezone.utc))
            self.assertEqual(result["state"],"READ")
            self.assertEqual(result["version"],"Version inconnue — identité lue")
            self.assertEqual(result["build"],"b"*12)
            self.assertEqual(result["bytes"],65536)
            self.assertEqual(calls,[("init",HOST),("read",ENDPOINT)])


if __name__=="__main__":
    unittest.main()
