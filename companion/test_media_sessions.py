"""GSMTC PC-only provider tests: fake Windows sessions, no actual Windows/API or TV."""
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from media_sessions import (
    MAX_COVER_BYTES, MAX_PREVIEW_JPEG, MediaSnapshot, artwork_to_preview,
    bounded_text, capture, convert_properties, demo_capture, elapsed_seconds,
    playback_state, read_thumbnail_bytes, save_preview, select_session,
)


@dataclass
class Value:
    name: str


class Prop:
    def __init__(self, title="Track", artist="Artist", album_title="Album", thumbnail=None):
        self.title = title
        self.artist = artist
        self.album_title = album_title
        self.thumbnail = thumbnail


class Playback:
    def __init__(self, state):
        self.playback_status = Value(state)


class Timeline:
    def __init__(self, start=0, end=180, position=30):
        self.start_time = timedelta(seconds=start)
        self.end_time = timedelta(seconds=end)
        self.position = timedelta(seconds=position)


class Session:
    def __init__(self, state="PAUSED", source="Spotify.exe", props=None,
                 timeline=None, media_failure=False):
        self.playback = Playback(state)
        self.source_app_user_model_id = source
        self.props = props if props is not None else Prop()
        self.timeline = timeline or Timeline()
        self.media_failure = media_failure

    def get_playback_info(self):
        return self.playback

    async def try_get_media_properties_async(self):
        if self.media_failure:
            raise ValueError("never print sensitive provider errors")
        return self.props

    def get_timeline_properties(self):
        return self.timeline


class Manager:
    def __init__(self, current=None, sessions=()):
        self.current, self.sessions = current, sessions

    def get_current_session(self):
        return self.current

    def get_sessions(self):
        return list(self.sessions)


class Thumbnail:
    def __init__(self, stream):
        self.stream = stream

    async def open_read_async(self):
        return self.stream


class Stream:
    def __init__(self, value: bytes, override_size=None):
        self.value = value
        self.size = override_size if override_size is not None else len(value)

    def get_input_stream_at(self, offset):
        assert offset == 0
        return self


class Reader:
    def __init__(self, stream):
        self.stream = stream

    async def load_async(self, count):
        return len(self.stream.value)

    def read_bytes(self, buffer):
        buffer[:] = self.stream.value


class MediaTests(unittest.TestCase):
    def test_selected_playing_session_over_paused_current(self):
        paused = Session("PAUSED", "browser")
        playing = Session("PLAYING", "Spotify.exe")
        manager = Manager(paused, [paused, playing])
        self.assertIs(select_session(manager.current, manager.sessions), playing)
        result = asyncio.run(capture(manager))
        self.assertEqual(result.snapshot.source, "Spotify.exe")
        self.assertEqual(result.snapshot.state, "PLAYING")
        self.assertEqual(result.snapshot.title, "Track")
        self.assertEqual(result.snapshot.position_seconds, 30)
        self.assertEqual(result.snapshot.duration_seconds, 180)
        self.assertIsNone(result.preview_jpeg)

    def test_no_session_and_no_media_properties(self):
        result = asyncio.run(capture(Manager()))
        self.assertEqual(result.snapshot.state, "NO_SESSION")
        self.assertFalse(result.snapshot.cover_available)
        result = asyncio.run(capture(Manager(Session(media_failure=True))))
        self.assertEqual(result.snapshot.state, "PAUSED")
        self.assertEqual(result.snapshot.title, "")
        self.assertFalse(result.snapshot.cover_available)

    def test_clamps_untrusted_metadata_controls_and_progress(self):
        value = "foo\n\x1b[31m\u202e" + ("x" * 400)
        self.assertEqual(bounded_text(value, 12), "foo[31mxxxxx")
        prop = Prop(title=value, artist="  AC / DC\t  ", thumbnail=object())
        snap = convert_properties("app\x00" + "x" * 200, prop, Playback("PLAYING"),
                                  Timeline(start=10, end=80, position=200))
        self.assertLessEqual(len(snap.title), 120)
        self.assertEqual(snap.artist, "AC / DC")
        self.assertEqual(snap.position_seconds, 70)
        self.assertEqual(snap.duration_seconds, 70)
        self.assertTrue(snap.cover_available)
        self.assertLessEqual(len(snap.source), 120)
        self.assertNotIn("\u202e", snap.title)
        self.assertEqual(playback_state(None), "UNKNOWN")

    def test_missing_or_bad_timeline_never_fakes_progress(self):
        bad = Timeline(start=200, end=100, position=155)
        snap = convert_properties("", Prop(), Playback("PAUSED"), bad)
        self.assertIsNone(snap.duration_seconds)
        self.assertIsNone(snap.position_seconds)
        self.assertIsNone(elapsed_seconds(timedelta(days=100)))
        self.assertIsNone(elapsed_seconds(object()))

    def test_cover_read_has_input_byte_cap(self):
        self.assertIsNone(asyncio.run(read_thumbnail_bytes(None, Reader)))
        self.assertIsNone(asyncio.run(read_thumbnail_bytes(
            Thumbnail(Stream(b"x", override_size=MAX_COVER_BYTES + 1)), Reader)))
        self.assertEqual(asyncio.run(read_thumbnail_bytes(
            Thumbnail(Stream(b"12345")), Reader)), b"12345")

    def test_cover_decode_and_private_output_lifecycle(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("optional PIL missing in no-tray Linux test environment")
        source = BytesIO()
        Image.new("RGB", (320, 200), (30, 70, 100)).save(source, "PNG")
        data = artwork_to_preview(source.getvalue())
        self.assertIsNotNone(data)
        self.assertLessEqual(len(data), MAX_PREVIEW_JPEG)
        with Image.open(BytesIO(data)) as picture:
            self.assertEqual(picture.size, (192, 192))
            self.assertEqual(picture.format, "JPEG")
        self.assertIsNone(artwork_to_preview(b"bad"))
        self.assertIsNone(artwork_to_preview(b"x" * (MAX_COVER_BYTES + 1)))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private" / "cover.jpg"
            self.assertTrue(save_preview(path, data))
            self.assertEqual(path.read_bytes(), data)
            self.assertFalse(save_preview(path, None))
            self.assertFalse(path.exists())
            with self.assertRaises(ValueError):
                save_preview(path, b"not-jpeg")

    def test_optional_media_cover_failure_cannot_fail_metadata(self):
        session = Session("PLAYING", props=Prop(thumbnail=Thumbnail(
            Stream(b"invalid-image"))))
        # Fail decode if PIL isn't installed: still get metadata and source.
        result = asyncio.run(capture(Manager(session), include_cover=True,
                                     reader_type=Reader))
        self.assertEqual(result.snapshot.state, "PLAYING")
        self.assertTrue(result.snapshot.cover_available)
        self.assertIsNone(result.preview_jpeg)

    def test_fixed_demo_never_misrepresents_live_session(self):
        result = demo_capture()
        self.assertEqual(result.snapshot.source, "DEMO_WINDOWS_SESSION")
        self.assertIn("SHINOBIWAN", result.snapshot.artist)
        self.assertIsNone(result.preview_jpeg)


if __name__ == "__main__":
    unittest.main()
