"""Offline contract tests for B5 LAN provisioning and future OTA client."""
import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError,HTTPError
from shino_b5_lan_update import LanTransport,UpdateError
from shino_b5_provision import provision as send_provision,ProvisionHold,ROOT,API,preflight,ProvisionDigest


class Response:
    def __init__(self,data):
        self.body=json.dumps(data).encode()
        self.status=200
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.body[:n]


class Reader:
    def __init__(self,*values):
        self.values=list(values)
        self.requests=[]
    def open(self,req,timeout):
        self.requests.append(req)
        response=self.values.pop(0)
        if isinstance(response,Exception):raise response
        return Response(response)


class LanClientTests(unittest.TestCase):
    def setUp(self):
        self.identity={"digest_password":"offline-fake-digest"}
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.marker=Path(self.directory.name)/"operation.attempt"

    def provision(self,reader,ssid,password):
        return send_provision(reader,ssid,password,attempt_marker=self.marker)

    def test_offline_numeric_private_host_only(self):
        with patch("socket.socket",side_effect=AssertionError("network")) as socket:
            with self.assertRaises(UpdateError):
                LanTransport(self.identity,"192.168.4.1")
            with self.assertRaises(Exception):
                LanTransport(self.identity,"8.8.8.8")
            transport=LanTransport(self.identity,"192.168.1.82")
            self.assertEqual(transport.host,"192.168.1.82")
            socket.assert_not_called()

    def test_requires_exact_sta_online_address(self):
        transport=LanTransport(self.identity,"192.168.1.82")
        for row,expected in (
          ({"state":"STA_ONLINE","sta_online":True,"lan_ip":"192.168.1.82"},True),
          ({"state":"STA_CONNECTING","sta_online":False,"lan_ip":"192.168.1.82"},False),
          ({"state":"STA_ONLINE","sta_online":True,"lan_ip":"192.168.1.83"},False),
          ({"state":"STA_ONLINE","sta_online":"true","lan_ip":"192.168.1.82"},False)):
            with self.subTest(row=row):
                transport.reader=Reader(row)
                self.assertIs(transport.lan_online(),expected)

    def test_uncertain_status_blocks_before_upload(self):
        transport=LanTransport(self.identity,"192.168.1.82")
        transport.reader=Reader(URLError("offline"))
        self.assertFalse(transport.lan_online())

    def test_provision_uses_exact_one_intent_then_one_post(self):
        reader=Reader({"intent":"a"*32},{"saved":True,"readback_verified":True})
        with patch("socket.socket",side_effect=AssertionError("network")) as sock:
            value=self.provision(reader,"MyHome24","ExamplePass123")
            self.assertEqual(value,"SDK_CREDENTIALS_VERIFIED_STA_CONNECTION_NOT_YET_PROVEN")
            sock.assert_not_called()
        self.assertEqual(len(reader.requests),2)
        self.assertTrue(reader.requests[0].full_url.endswith("/api/v1/lan/intent"))
        self.assertTrue(reader.requests[1].full_url.endswith("/api/v1/lan/provision"))
        self.assertEqual(reader.requests[1].get_header("X-shino-lan-intent"),"a"*32)

    def test_rejected_provision_reports_only_http_and_device_code(self):
        # This is the failure the owner saw previously as a generic HOLD.
        detail=b'{"error":"PROVISION_HOLD"}'
        rejected=HTTPError(ROOT+API+"/provision",409,"rejected",{},io.BytesIO(detail))
        reader=Reader({"intent":"a"*32},rejected)
        with self.assertRaisesRegex(ProvisionHold,
              r"/provision: HTTP 409 / PROVISION_HOLD") as raised:
            self.provision(reader,"Freebox-Test","SensitiveTestPassword123")
        self.assertNotIn("SensitiveTestPassword123",str(raised.exception))
        self.assertEqual(len(reader.requests),2)

    def test_digest_rejection_is_distinguished_from_wifi_password(self):
        rejected=HTTPError(ROOT+API+"/intent",401,"auth",{},io.BytesIO(b""))
        reader=Reader(rejected)
        with self.assertRaisesRegex(ProvisionHold,
              r"/intent: HTTP 401 / NO_DEVICE_ERROR_CODE"):
            self.provision(reader,"TestSSID","SensitiveTestPassword123")
        self.assertEqual(len(reader.requests),1)

    def test_device_body_cannot_inject_secrets_into_diagnostic(self):
        rejected=HTTPError(ROOT+API+"/provision",403,"auth",{},
              io.BytesIO(b'{"error":"SECRET=SensitiveTestPassword123"}'))
        reader=Reader({"intent":"a"*32},rejected)
        with self.assertRaises(ProvisionHold) as raised:
            self.provision(reader,"Freebox-Test","SensitiveTestPassword123")
        self.assertIn("HTTP 403 / NO_DEVICE_ERROR_CODE",str(raised.exception))
        self.assertNotIn("SensitiveTestPassword123",str(raised.exception))
        self.assertEqual(len(reader.requests),2)

    def test_lost_provision_reply_does_not_retry(self):
        reader=Reader({"intent":"a"*32},URLError("lost"))
        with self.assertRaises(ProvisionHold):
            self.provision(reader,"MyHome24","ExamplePass123")
        self.assertEqual(len(reader.requests),2)

    def test_marker_blocks_restart_after_lost_reply(self):
        reader=Reader({"intent":"a"*32},URLError("lost"))
        with self.assertRaises(ProvisionHold):self.provision(reader,"TestSSID","FakePassword123")
        self.assertTrue(self.marker.exists())
        with self.assertRaises(ProvisionHold):self.provision(reader,"TestSSID","FakePassword123")
        self.assertEqual(len(reader.requests),2)
        self.assertNotIn("FakePassword123",self.marker.read_text())
        self.assertNotIn("TestSSID",self.marker.read_text())

    def test_uppercase_secret_shaped_device_code_is_not_disclosed(self):
        rejected=HTTPError(ROOT+API+"/provision",409,"hold",{},io.BytesIO(b'{"error":"FAKEPRIVATEPASSWORD"}'))
        with self.assertRaisesRegex(ProvisionHold,"NO_DEVICE_ERROR_CODE"):
            self.provision(Reader({"intent":"a"*32},rejected),"TestSSID","FakePassword123")

    def test_old_b5_or_unknown_storage_cannot_start_another_write(self):
        for status in ({"state":"NO_SAVED_WIFI"},
                       {"firmware":"B5.1","state":"NO_SAVED_WIFI","credential_state":"UNKNOWN"}):
            reader=Reader({"sha256":"a"*64,"build_id":"b"*64},status)
            with self.assertRaises(ProvisionHold):preflight(reader,"a"*64,"b"*64)
            self.assertEqual(len(reader.requests),2)

    def test_preflight_reuses_already_saved_without_password_or_post(self):
        reader=Reader({"sha256":"a"*64,"build_id":"b"*64},
                      {"firmware":"B5.1","credential_state":"VERIFIED","state":"STA_CONNECTING"})
        self.assertEqual(preflight(reader,"a"*64,"b"*64),"ALREADY_SAVED_NO_POST")
        self.assertTrue(all(x.get_method()=="GET" for x in reader.requests))

    def test_exact_running_identity_required_before_intent(self):
        reader=Reader({"sha256":"c"*64,"build_id":"b"*64})
        with self.assertRaises(ProvisionHold):preflight(reader,"a"*64,"b"*64)
        self.assertEqual(len(reader.requests),1)

    def test_digest_never_retries_a_post_on_401(self):
        from urllib.request import Request,HTTPPasswordMgrWithDefaultRealm
        handler=ProvisionDigest(HTTPPasswordMgrWithDefaultRealm(),ROOT)
        req=Request(ROOT+API+"/provision",data=b"public fake",method="POST")
        with patch.object(handler,"retry_http_digest_auth",side_effect=AssertionError("POST replay")) as retry:
            with self.assertRaises(HTTPError):handler.http_error_401(req,io.BytesIO(),401,"auth",{})
            retry.assert_not_called()

    def test_numeric_flags_cannot_claim_verified_storage(self):
        reader=Reader({"intent":"a"*32},{"saved":1,"readback_verified":1})
        with self.assertRaises(ProvisionHold):self.provision(reader,"TestSSID","FakePassword123")
        self.assertTrue(self.marker.exists())

    def test_marker_reservation_failure_blocks_the_post(self):
        reader=Reader({"intent":"a"*32})
        with patch("shino_b5_provision.reserve",side_effect=OSError("public simulated disk fault")):
            with self.assertRaises(OSError):self.provision(reader,"TestSSID","FakePassword123")
        self.assertEqual(len(reader.requests),1)


if __name__=="__main__":
    unittest.main()
