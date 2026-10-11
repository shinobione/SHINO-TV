"""Offline contract tests for B5 LAN provisioning and future OTA client."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
from shino_b5_lan_update import LanTransport,UpdateError
from shino_b5_provision import provision,ProvisionHold


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
            value=provision(reader,"MyHome24","ExamplePass123")
            self.assertEqual(value,"SDK_CREDENTIALS_VERIFIED_STA_CONNECTION_NOT_YET_PROVEN")
            sock.assert_not_called()
        self.assertEqual(len(reader.requests),2)
        self.assertTrue(reader.requests[0].full_url.endswith("/api/v1/lan/intent"))
        self.assertTrue(reader.requests[1].full_url.endswith("/api/v1/lan/provision"))
        self.assertEqual(reader.requests[1].get_header("X-shino-lan-intent"),"a"*32)

    def test_lost_provision_reply_does_not_retry(self):
        reader=Reader({"intent":"a"*32},URLError("lost"))
        with self.assertRaises(ProvisionHold):
            provision(reader,"MyHome24","ExamplePass123")
        self.assertEqual(len(reader.requests),2)


if __name__=="__main__":
    unittest.main()
