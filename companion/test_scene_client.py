import io
import json
import unittest
from urllib.request import Request
from scene_client import device_endpoint, send_scene, validate_scene


class SceneClientTests(unittest.TestCase):
    def test_all_presets_and_size(self):
        examples = [
            {"kind": "metrics"},
            {"kind": "music", "artist": "SHINOBIWAN", "track": "MACHINE FEVER", "progress": 38},
            {"kind": "agent", "status": "RUNNING", "task": "Compile", "progress": 72},
            {"kind": "release", "artist": "SHINOBIWAN", "track": "TITLE", "days": 12},
        ]
        for payload in examples:
            self.assertEqual(validate_scene(payload), payload)

    def test_rejects_extraneous_fields_out_of_range_and_unicode(self):
        invalid = [
            {"kind": "music", "artist": "a", "track": "b", "progress": 101},
            {"kind": "music", "artist": "a", "track": "b", "progress": True},
            {"kind": "agent", "status": "ON", "task": "Été", "progress": 20},
            {"kind": "release", "artist": "a", "track": "b", "days": -1},
            {"kind": "metrics", "title": "not supported in device protocol"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_scene(payload)

    def test_private_endpoint_only(self):
        self.assertEqual(device_endpoint("http://192.168.1.70"),
                         "http://192.168.1.70/api/v1/shino/scene")
        for url in ("http://8.8.8.8", "https://192.168.1.70", "http://example.com",
                    "http://0.0.0.0", "http://192.168.1.70/update"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                device_endpoint(url)

    def test_mocked_post_exact_contract(self):
        request_seen = []
        class Response(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return None
        def fake_opener(request, timeout):
            request_seen.append((request, timeout))
            return Response(b'{"status":"ok","kind":"music"}')
        payload = {"kind": "music", "artist": "SHINOBIWAN", "track": "MACHINE FEVER", "progress": 38}
        self.assertEqual(send_scene("http://192.168.1.70", "test_token", payload, fake_opener)["status"], "ok")
        request, timeout = request_seen[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(timeout, 3)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test_token")
        self.assertEqual(json.loads(request.data), payload)


if __name__ == "__main__":
    unittest.main()
