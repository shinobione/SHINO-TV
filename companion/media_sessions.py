"""SHINO // LINK V0.2 — PC-ONLY Windows media-session reader.

No connection to the SmallTV, HTTP server, Spotify API, tokens, microphone,
playback controls or filesystem writes unless --cover-preview is explicit.
All media failure paths are isolated from the existing PC metrics sender.
Requires optional Windows-only PyWinRT packages for a live probe.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

MAX_TITLE = 120
MAX_ARTIST = 120
MAX_ALBUM = 120
MAX_SOURCE = 120
MAX_COVER_BYTES = 1024 * 1024
MAX_ARTWORK_PIXELS = 4_000_000
PREVIEW_SIZE = 192
MAX_PREVIEW_JPEG = 40 * 1024
STATES = frozenset({"PLAYING", "PAUSED", "STOPPED", "CHANGING", "CLOSED", "UNKNOWN"})
POLL_SECONDS = 3.0


@dataclass(frozen=True)
class MediaSnapshot:
    state: str
    source: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    position_seconds: int | None = None
    duration_seconds: int | None = None
    cover_available: bool = False

    def public_data(self) -> dict:
        return {
            "state": self.state, "source": self.source,
            "title": self.title, "artist": self.artist, "album": self.album,
            "position_seconds": self.position_seconds,
            "duration_seconds": self.duration_seconds,
            "cover_available": self.cover_available,
        }


@dataclass(frozen=True)
class MediaCapture:
    snapshot: MediaSnapshot
    preview_jpeg: bytes | None = None


def bounded_text(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    # Media tags are untrusted, may include terminal control or BiDi direction
    # overrides. Never execute or interpret media metadata as commands/markup.
    stripped = "".join(
        " " if ch.isspace() else ch for ch in value
        if ch.isprintable() and ord(ch) not in range(0x202A, 0x202F)
        and ord(ch) not in range(0x2066, 0x206A)
    )
    return re.sub(r" +", " ", stripped).strip()[:limit]


def playback_state(status) -> str:
    name = getattr(status, "name", None)
    if not isinstance(name, str):
        return "UNKNOWN"
    name = name.upper()
    return name if name in STATES else "UNKNOWN"


def elapsed_seconds(value) -> int | None:
    if value is None:
        return None
    try:
        seconds = int(value.total_seconds())
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
    return seconds if 0 <= seconds <= 86400 * 7 else None


def convert_properties(source, props, playback, timeline) -> MediaSnapshot:
    state = playback_state(getattr(playback, "playback_status", None))
    title = bounded_text(getattr(props, "title", ""), MAX_TITLE)
    artist = bounded_text(getattr(props, "artist", ""), MAX_ARTIST)
    album = bounded_text(getattr(props, "album_title", ""), MAX_ALBUM)
    duration = None
    position = None
    if timeline is not None:
        start = elapsed_seconds(getattr(timeline, "start_time", None))
        end = elapsed_seconds(getattr(timeline, "end_time", None))
        absolute_position = elapsed_seconds(getattr(timeline, "position", None))
        if start is not None and end is not None and end >= start:
            duration = end - start
            if absolute_position is not None:
                position = min(max(absolute_position - start, 0), duration)
    return MediaSnapshot(
        state=state,
        source=bounded_text(source, MAX_SOURCE),
        title=title, artist=artist, album=album,
        position_seconds=position, duration_seconds=duration,
        cover_available=bool(getattr(props, "thumbnail", None)),
    )


def select_session(current, sessions) -> object | None:
    # A background paused browser should not displace another actually
    # playing source. Otherwise use Windows' selected current session.
    candidates = list(sessions or ())
    if current is not None and all(current is not item for item in candidates):
        candidates.insert(0, current)
    for session in candidates:
        try:
            if playback_state(session.get_playback_info().playback_status) == "PLAYING":
                return session
        except Exception:
            continue
    return current if current is not None else (candidates[0] if candidates else None)


async def read_thumbnail_bytes(thumbnail, reader_type=None) -> bytes | None:
    """Read only a single bounded WinRT stream on PC; never transfer to TV."""
    if thumbnail is None:
        return None
    if reader_type is None:
        from winrt.windows.storage.streams import DataReader
        reader_type = DataReader
    stream = await thumbnail.open_read_async()
    size = getattr(stream, "size", None)
    if type(size) is not int or not 0 < size <= MAX_COVER_BYTES:
        return None
    reader = reader_type(stream.get_input_stream_at(0))
    count = await reader.load_async(size)
    if type(count) is not int or count != size:
        return None
    buffer = bytearray(size)
    reader.read_bytes(buffer)
    return bytes(buffer)


def artwork_to_preview(raw: bytes | None) -> bytes | None:
    if not raw or len(raw) > MAX_COVER_BYTES:
        return None
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(BytesIO(raw)) as original:
            width, height = original.size
            if not (0 < width <= 4096 and 0 < height <= 4096
                    and width * height <= MAX_ARTWORK_PIXELS):
                return None
            original.load()
            corrected = ImageOps.exif_transpose(original)
            image = ImageOps.fit(corrected.convert("RGB"), (PREVIEW_SIZE, PREVIEW_SIZE),
                                 method=Image.Resampling.LANCZOS)
        for quality in (78, 65, 50):
            output = BytesIO()
            image.save(output, format="JPEG", quality=quality,
                       optimize=True, progressive=False, exif=b"")
            if output.tell() <= MAX_PREVIEW_JPEG:
                return output.getvalue()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return None
    return None


async def capture(manager=None, *, include_cover: bool = False,
                  reader_type=None) -> MediaCapture:
    if manager is None:
        if os.name != "nt":
            return MediaCapture(MediaSnapshot(state="UNAVAILABLE"))
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    current = manager.get_current_session()
    session = select_session(current, manager.get_sessions())
    if session is None:
        return MediaCapture(MediaSnapshot(state="NO_SESSION"))
    playback = session.get_playback_info()
    try:
        props = await session.try_get_media_properties_async()
    except Exception:
        # A transient media metadata error is not a PC metrics failure.
        props = None
    try:
        timeline = session.get_timeline_properties()
    except Exception:
        timeline = None
    snap = convert_properties(
        getattr(session, "source_app_user_model_id", ""), props, playback, timeline)
    image = None
    if include_cover and snap.cover_available:
        try:
            image = artwork_to_preview(
                await read_thumbnail_bytes(props.thumbnail, reader_type=reader_type))
        except Exception:
            image = None
    return MediaCapture(snap, image)


def preview_path() -> Path:
    home = os.environ.get("LOCALAPPDATA")
    root = Path(home) if home else Path.home() / "AppData" / "Local"
    return root / "SHINO-TV" / "media-preview.jpg"


def save_preview(path: Path, image: bytes | None) -> bool:
    """Only used by explicit --cover-preview. One local PC file, never the Git tree."""
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Preview output may not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    if image is None:
        # Revoke previous artwork on no-session, track without cover, or error.
        if path.exists():
            path.unlink()
        return False
    if not image.startswith(b"\xff\xd8") or len(image) > MAX_PREVIEW_JPEG:
        raise ValueError("Invalid JPEG preview")
    temp = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".media-",
                                         suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(image)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        temp = None
        return True
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def demo_capture() -> MediaCapture:
    # Explicit deterministic fixture, NOT a claim about actual Spotify state.
    return MediaCapture(MediaSnapshot(
        "PLAYING", "DEMO_WINDOWS_SESSION", "Demo — Machine Fever",
        "SHINOBIWAN", "Demo preview", 31, 215, False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="Fixture only: zero OS/media/network access")
    mode.add_argument("--once", action="store_true", help="One live Windows media session read")
    mode.add_argument("--watch", action="store_true", help="Watch current session every ~3s; Ctrl+C stops")
    parser.add_argument("--cover-preview", action="store_true",
                        help="Explicitly read/resize available thumbnail and save ONE PC-local JPEG")
    args = parser.parse_args(argv)
    if args.demo and args.cover_preview:
        parser.error("Demo mode does not write a preview")
    if args.cover_preview and os.name != "nt":
        parser.error("Live preview requires Windows")
    previous = None
    while True:
        try:
            result = demo_capture() if args.demo else asyncio.run(
                capture(include_cover=args.cover_preview))
            data = result.snapshot.public_data()
            fingerprint = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if fingerprint != previous:
                print(json.dumps(data, ensure_ascii=False), flush=True)
                previous = fingerprint
            if args.cover_preview:
                saved = save_preview(preview_path(), result.preview_jpeg)
                print("PC-LOCAL artwork preview: " +
                      (str(preview_path()) if saved else "not available"), flush=True)
        except KeyboardInterrupt:
            print("Media observer stopped.", flush=True)
            return 0
        except ImportError:
            print("Media module not installed. See companion/requirements-media.txt.",
                  file=sys.stderr)
            return 2
        except Exception:
            # No traceback, metadata, paths, raw WinRT/system exception or tokens.
            print('{"state":"UNAVAILABLE","reason":"MEDIA_READ_FAILED"}', flush=True)
            if args.cover_preview:
                save_preview(preview_path(), None)
            if not args.watch:
                return 1
        if not args.watch:
            return 0
        try:
            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("Media observer stopped.", flush=True)
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
