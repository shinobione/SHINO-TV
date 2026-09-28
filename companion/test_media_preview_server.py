"""Local-only V0.4 HTTP and collector tests; fake GSMTC, no real TV or Spotify."""
import asyncio
from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest

from media_sessions import MediaCapture, MediaSnapshot, MAX_PREVIEW_JPEG
from media_preview_server import (
    BIND_IP, CSP, MediaCache, create_server, run_media_worker,
    STALE_SECONDS,
)


class LiveMediaServerTests(unittest.TestCase):
    def setUp(self):
        self.now = [100.0]
        self.cache = MediaCache(clock=lambda: self.now[0])
        media = MediaSnapshot("PLAYING", "Spotify.exe", "Velvet HAMMER",
                              "ShinoBiWan", "Velvet HAMMER", 44, 229, True)
        self.jpeg = b"\xff\xd8" + b"a" * 100 + b"\xff\xd9"
        self.cache.set_capture(MediaCapture(media, self.jpeg))
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        for name in ("now-playing-live.html", "now-playing-live.mjs", "now_playing.mjs"):
            (root / name).write_text("SAFE STATIC FIXTURE", encoding="utf-8")
        self.server = create_server(self.cache, root=root, port=0)
        self.assertEqual(self.server.server_address[0], BIND_IP)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = BIND_IP + ":" + str(self.port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def call(self, path, *, method="GET", headers=None):
        connection = HTTPConnection(BIND_IP, self.port, timeout=3)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        status = response.status
        head = dict(response.getheaders())
        connection.close()
        return status, head, payload

    def test_known_assets_only_and_browser_security_headers(self):
        for path in ("/now-playing-live.html", "/now-playing-live.mjs", "/now_playing.mjs"):
            status, headers, data = self.call(path)
            self.assertEqual(status, 200)
            self.assertEqual(data, b"SAFE STATIC FIXTURE")
            self.assertIn("no-store", headers["Cache-Control"])
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")
            self.assertEqual(headers["Content-Security-Policy"], CSP)
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        for path in ("/", "/companion/media_preview_server.py", "/.git/config",
                     "/../../credentials.txt", "/now-playing-live.html?bad=true"):
            self.assertEqual(self.call(path)[0], 404, path)

    def test_media_requires_exact_custom_header_and_host(self):
        path = "/api/v1/media/state"
        self.assertEqual(self.call(path)[0], 403)
        self.assertEqual(self.call(path,headers={"X-Shino-Preview":"wrong"})[0],403)
        self.assertEqual(self.call(path,headers={"X-Shino-Preview":"1","Host":"evil.test"})[0],403)
        self.assertEqual(self.call(path,headers={"X-Shino-Preview":"1","Origin":"https://evil.test"})[0],403)
        self.assertEqual(self.call(path,headers={"X-Shino-Preview":"1","Sec-Fetch-Site":"cross-site"})[0],403)
        code, head, body = self.call(path,headers={"X-Shino-Preview":"1"})
        self.assertEqual(code,200)
        self.assertEqual(head["Content-Type"],"application/json; charset=utf-8")
        import json
        snap=json.loads(body)
        self.assertEqual(snap["status"],"READY")
        self.assertEqual(snap["media"]["source"],"Spotify.exe")
        self.assertEqual(snap["media"]["title"],"Velvet HAMMER")
        self.assertEqual(snap["media"]["position_seconds"],44)
        self.assertEqual(snap["media"]["duration_seconds"],229)
        self.assertIsNotNone(snap["cover_revision"])

    def test_image_revision_only_current_small_jpeg_and_revoked_on_update(self):
        snap=self.cache.get_state()
        rev=snap["cover_revision"]
        endpoint="/api/v1/media/cover?revision="
        self.assertEqual(self.call(endpoint+rev)[0],403)
        status,head,body=self.call(endpoint+rev,headers={"X-Shino-Preview":"1"})
        self.assertEqual(status,200)
        self.assertEqual(head["Content-Type"],"image/jpeg")
        self.assertEqual(body,self.jpeg)
        self.assertEqual(self.call(endpoint+"b"*64,headers={"X-Shino-Preview":"1"})[0],404)
        self.assertEqual(self.call(endpoint+"not-hex",headers={"X-Shino-Preview":"1"})[0],400)
        self.assertEqual(self.call(endpoint+rev+"&extra=1",headers={"X-Shino-Preview":"1"})[0],400)
        self.cache.set_capture(MediaCapture(MediaSnapshot("PAUSED","Spotify.exe")))
        self.assertIsNone(self.cache.get_state()["cover_revision"])
        self.assertEqual(self.call(endpoint+rev,headers={"X-Shino-Preview":"1"})[0],404)

    def test_waiting_stale_and_unavailable_scrub_song_and_art(self):
        fresh=MediaCache(clock=lambda:self.now[0])
        self.assertEqual(fresh.get_state()["status"],"WAITING")
        self.now[0]+=STALE_SECONDS+1
        self.assertEqual(self.cache.get_state()["status"],"STALE")
        self.assertEqual(self.cache.get_state()["media"]["title"],"")
        self.assertIsNone(self.cache.get_state()["cover_revision"])
        self.assertIsNone(self.cache.get_cover("a"*64))
        self.cache.set_unavailable()
        self.assertEqual(self.cache.get_state()["status"],"UNAVAILABLE")
        self.assertEqual(self.cache.get_state()["media"]["title"],"")

    def test_cover_over_limit_and_invalid_body_never_cached(self):
        snap=MediaSnapshot("PLAYING","Spotify.exe",title="one",cover_available=True)
        self.cache.set_capture(MediaCapture(snap,b"\xff\xd8"+b"x"*MAX_PREVIEW_JPEG))
        self.assertIsNone(self.cache.get_state()["cover_revision"])
        self.cache.set_capture(MediaCapture(snap,b"bad"))
        self.assertIsNone(self.cache.get_state()["cover_revision"])

    def test_post_and_preflight_disabled(self):
        self.assertEqual(self.call("/api/v1/media/state",method="OPTIONS")[0],405)
        self.assertEqual(self.call("/api/v1/media/state",method="POST")[0],405)
        self.assertEqual(self.call("/api/v1/media/state",method="PUT")[0],405)

    def test_media_collector_separate_fake_without_windows_api(self):
        stop=threading.Event()
        async def fake_collector(*,include_cover):
            self.assertTrue(include_cover)
            stop.set()
            return MediaCapture(MediaSnapshot("PLAYING","FAKE",title="Mock"))
        run_media_worker(self.cache,stop,collector=fake_collector)
        self.assertEqual(self.cache.get_state()["media"]["title"],"Mock")
        self.assertEqual(self.cache.get_state()["media"]["source"],"FAKE")


if __name__=="__main__":
    unittest.main()
