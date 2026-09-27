"""No-device tests of the opt-in read-only status/heap snapshot tool."""
from contextlib import redirect_stdout
from email.message import Message
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
import unittest

import read_fsless_heap as probe

ROOT=Path(__file__).resolve().parent.parent


def status(**changes):
    body={
        "mode":"FIRST_BOOT_BRIDGE","pc_metrics_storage":"RAM_ONLY",
        "native_ota_writer_compiled":False,
        "physical_flash_installation_authorized":False,
        "physical_flash_or_application_OTA_writes_performed_by_diagnostics":False,
        "filesystem_migration_writes_compiled":False,
        "application_littlefs_begin_called":False,
        "application_eeprom_commit_called":False,
        "available_heap_bytes":31520,"running_application_bytes":399152,
    }
    body.update(changes)
    return json.dumps(body,separators=(",",":")).encode("utf-8")


def observed(**changes):
    summary={
        "schema":"OBSERVED_HEAP_V1",
        "sampling_interval_ms":1000,
        "sample_count":3,
        "max_samples":1024,
        "state":"SAMPLING",
        "first_free_heap_bytes":32000,
        "latest_free_heap_bytes":31900,
        "latest_largest_free_block_bytes":25000,
        "latest_fragmentation_percent":17,
        "lowest_observed_free_heap_bytes":31850,
        "lowest_observed_largest_free_block_bytes":24000,
        "highest_observed_fragmentation_percent":18,
    }
    summary.update(changes)
    return summary


class FakeResponse:
    def __init__(self,body=None,code=200,content_type="application/json",
                 length=None):
        self.body=status() if body is None else body
        self.code=code
        self.headers=Message()
        self.headers["Content-Type"]=content_type
        if length is not None:
            self.headers["Content-Length"]=str(length)
    def getcode(self):
        return self.code
    def read(self,count):
        return self.body[:count]
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


class FakeOpener:
    def __init__(self,response=None):
        self.response=response if response is not None else FakeResponse()
        self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        return self.response


class HeapReadOnlySnapshotTests(unittest.TestCase):
    def test_offline_is_default_and_never_loads_credentials_or_opens_network(self):
        output=StringIO()
        with patch.object(probe,"read_credentials",side_effect=AssertionError("secrets")), \
             patch.object(probe,"make_status_opener",side_effect=AssertionError("network")), \
             redirect_stdout(output):
            self.assertEqual(probe.main([]),0)
        self.assertIn("OFFLINE ONLY",output.getvalue())

    def test_one_explicit_get_exact_private_ap_status_route(self):
        opener=FakeOpener(FakeResponse(length=len(status())))
        self.assertEqual(probe.read_one_snapshot(opener),{
            "free_heap_bytes":31520,"running_application_bytes":399152})
        self.assertEqual(len(opener.calls),1)
        request,timeout=opener.calls[0]
        self.assertEqual(timeout,4.0)
        self.assertEqual(request.get_method(),"GET")
        self.assertIsNone(request.data)
        self.assertEqual(request.full_url,
                         "http://192.168.4.1/api/v1/bridge/status")
        self.assertEqual(request.get_header("Cache-control"),"no-store")
        self.assertNotIn("/ota/",request.full_url)
        self.assertNotIn("/factory-return",request.full_url)

    def test_exact_installed_review_002_status_without_new_ota_field_is_accepted(self):
        # Historical actual review-002 bridge status has the common no-write
        # indicators but not native_ota_writer_compiled, added in PR #20.
        original=json.loads(status())
        original.pop("native_ota_writer_compiled")
        self.assertEqual(probe.validate_status(json.dumps(original).encode()),{
            "free_heap_bytes":31520,"running_application_bytes":399152})

    def test_optional_candidate_observation_with_actual_bounded_schema(self):
        report=probe.validate_status(status(heap_observation=observed()))
        self.assertEqual(report["free_heap_bytes"],31520)
        self.assertEqual(report["heap_observation"],{
            "state":"SAMPLING","sample_count":3,
            "lowest_observed_free_heap_bytes":31850,
            "lowest_observed_largest_free_block_bytes":24000,
            "highest_observed_fragmentation_percent":18})
        empty={key:value for key,value in observed().items()
               if key not in ("first_free_heap_bytes","latest_free_heap_bytes",
                              "latest_largest_free_block_bytes",
                              "latest_fragmentation_percent",
                              "lowest_observed_free_heap_bytes",
                              "lowest_observed_largest_free_block_bytes",
                              "highest_observed_fragmentation_percent")}
        empty.update(sample_count=0,state="NO_SAMPLES")
        self.assertEqual(probe.validate_status(status(heap_observation=empty))[
            "heap_observation"],{"state":"NO_SAMPLES","sample_count":0})
        full=observed(sample_count=1024,state="SATURATED")
        self.assertEqual(probe.validate_status(status(heap_observation=full))[
            "heap_observation"]["state"],"SATURATED")

    def test_optional_observation_fails_closed_on_bad_counts_states_types_or_extrema(self):
        invalid=[
            None,[],observed(schema="OTHER"),
            observed(sampling_interval_ms=0),observed(max_samples=True),
            observed(sample_count=1025),observed(sample_count=True),
            observed(state="NO_SAMPLES"),observed(sample_count=1024,state="SAMPLING"),
            observed(latest_free_heap_bytes="31900"),
            observed(latest_fragmentation_percent=True),
            observed(latest_largest_free_block_bytes=32000),
            observed(lowest_observed_free_heap_bytes=32100),
            observed(lowest_observed_largest_free_block_bytes=30000),
            observed(highest_observed_fragmentation_percent=16),
            observed(first_free_heap_bytes=0),
            observed(unexpected="raw"),
            observed(sample_count=1,first_free_heap_bytes=32000,
                     latest_free_heap_bytes=31900),
            observed(sample_count=0,state="NO_SAMPLES"),
        ]
        for item in invalid:
            with self.subTest(item=item),self.assertRaises(probe.HeapReadError):
                probe.validate_status(status(heap_observation=item))
        raw=status().decode("utf-8")[:-1]+',"heap_observation":{"schema":"OBSERVED_HEAP_V1","schema":"OBSERVED_HEAP_V1"}}'
        with self.assertRaises(probe.HeapReadError):
            probe.validate_status(raw.encode())

    def test_new_candidate_output_is_only_sanitized_observed_integer_summary(self):
        fake=FakeOpener(FakeResponse(body=status(heap_observation=observed())))
        output=StringIO()
        with patch.object(probe,"read_credentials",
                          return_value=("shino","disposable-fixture-password")), \
             patch.object(probe,"make_status_opener",return_value=fake), \
             redirect_stdout(output):
            self.assertEqual(probe.main([
                "--measure","--credentials-file","private-fixture.txt",
                "--phase","pc_telemetry"]),0)
        report=output.getvalue()
        self.assertIn("READ ONLY OBSERVED | state=SAMPLING | samples=3",report)
        self.assertIn("lowest_observed_free_heap_bytes=31850",report)
        self.assertIn("highest_observed_fragmentation_percent=18",report)
        self.assertNotIn("disposable-fixture-password",report)
        self.assertNotIn("http://",report)
        self.assertEqual(len(fake.calls),1)

    def test_missing_or_true_shared_safety_marker_is_rejected_in_both_versions(self):
        for field in (
            "physical_flash_installation_authorized",
            "physical_flash_or_application_OTA_writes_performed_by_diagnostics",
            "filesystem_migration_writes_compiled",
            "application_littlefs_begin_called",
            "application_eeprom_commit_called",
        ):
            for replacement in (True,None,0):
                body=json.loads(status())
                body.pop("native_ota_writer_compiled")
                body[field]=replacement
                with self.subTest(field=field,replacement=replacement), \
                     self.assertRaises(probe.HeapReadError):
                    probe.validate_status(json.dumps(body).encode())
        # Newer builds must not be allowed to explicitly enable native OTA.
        with self.assertRaises(probe.HeapReadError):
            probe.validate_status(status(native_ota_writer_compiled=True))

    def test_rejects_wrong_or_ambiguous_status_and_oversized_response(self):
        for raw in (
            b"",b"[]",b'{"available_heap_bytes":1,"available_heap_bytes":2}',
            status(mode="FAKE_STATUS"),status(pc_metrics_storage="DISK"),
            status(native_ota_writer_compiled=True),
            status(physical_flash_installation_authorized=True),
            status(available_heap_bytes=True),status(available_heap_bytes=0),
            status(available_heap_bytes=-1),status(available_heap_bytes="40000"),
            status(running_application_bytes=False),
            b" "*4097,
        ):
            with self.subTest(length=len(raw)), self.assertRaises(probe.HeapReadError):
                probe.validate_status(raw)
        for response in (
            FakeResponse(code=302),FakeResponse(content_type="text/html"),
            FakeResponse(length=4097),FakeResponse(length="not-a-number"),
            FakeResponse(body=b" "*4097),
        ):
            with self.subTest(headers=dict(response.headers)), \
                 self.assertRaises(probe.HeapReadError):
                probe.read_one_snapshot(FakeOpener(response))

    def test_status_digest_config_has_no_redirect_or_proxy_and_isolated_realm(self):
        opener=probe.make_status_opener("shino","disposable-fixture-password")
        handler_names={type(handler).__name__ for handler in opener.handlers}
        self.assertIn("HTTPDigestAuthHandler",handler_names)
        self.assertIn("NoRedirect",handler_names)
        proxies=[h for h in opener.handlers if type(h).__name__=="ProxyHandler"]
        self.assertTrue(all(h.proxies=={} for h in proxies))

    def test_manual_one_shot_only_prints_nonsecret_numeric_snapshot(self):
        output=StringIO()
        fake=FakeOpener()
        with patch.object(probe,"read_credentials",
                          return_value=("shino","disposable-fixture-password")), \
             patch.object(probe,"make_status_opener",return_value=fake) as factory, \
             redirect_stdout(output):
            self.assertEqual(probe.main([
                "--measure","--credentials-file","private-fixture.txt",
                "--phase","browser_open"]),0)
        factory.assert_called_once_with("shino","disposable-fixture-password")
        self.assertEqual(len(fake.calls),1)
        report=output.getvalue()
        self.assertIn("phase=browser_open",report)
        self.assertIn("free_heap_bytes=31520",report)
        self.assertIn("running_application_bytes=399152",report)
        self.assertNotIn("disposable-fixture-password",report)
        self.assertNotIn("http://",report)

    def test_live_firmware_status_is_only_read_and_source_is_disconnected(self):
        bridge=(ROOT/"firmware/src/boot/FirstBootBridge.cpp").read_text(
            encoding="utf-8")
        source=(ROOT/"companion/read_fsless_heap.py").read_text(encoding="utf-8")
        self.assertIn('doc["available_heap_bytes"] = ESP.getFreeHeap();',bridge)
        self.assertIn('doc["mode"] = "FIRST_BOOT_BRIDGE";',bridge)
        self.assertIn('server.on("/api/v1/bridge/status", HTTP_GET, sendStatus);',bridge)
        self.assertIn("if (!requireAuth()) return;",bridge)
        self.assertIn('Request(endpoint, method="GET"',source)
        self.assertIn('if not args.measure:',source)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)


if __name__=="__main__":
    unittest.main()
