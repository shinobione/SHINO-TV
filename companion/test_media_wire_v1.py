"""Strict host-only V0.5 emulation: fake auth, malformed frames, no real TV."""
from dataclasses import replace
from io import BytesIO
import hashlib
import json
import unittest
import zlib

from media_sessions import MediaSnapshot
from media_wire_v1 import (
    COVER_RAW_BYTES, CHUNK_BYTES, CHUNK_COUNT, MAX_METADATA_BYTES,
    MAX_TRANSACTION_SECONDS, OVERLAY_SECONDS, EmulatedReceiver, Packet,
    ProtocolError, canonical_metadata, jpeg_to_rgb565, prepare
)


class WireHostTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        stream = BytesIO()
        Image.new("RGB", (192, 192), (221, 165, 92)).save(stream, "JPEG")
        self.jpeg = stream.getvalue()
        self.media = MediaSnapshot("PLAYING", "Spotify.exe", "Velvet HAMMER",
                                   "ShinoBiWan", "Velvet HAMMER", 44, 229, True)
        self.transfer = prepare(self.media, self.jpeg, tx="a" * 32)
        self.receiver = EmulatedReceiver()

    def begin(self, transfer=None, receiver=None, now=0):
        t = transfer or self.transfer
        r = receiver or self.receiver
        return r.begin(t.metadata, auth_verified=True, now=now)

    def complete(self, transfer=None, receiver=None, now=0):
        t = transfer or self.transfer
        r = receiver or self.receiver
        self.begin(t, r, now=now)
        for item in t.packets:
            self.assertEqual(r.tile(item, auth_verified=True, now=now+1), "STAGED")
        return r.commit(auth_verified=True, now=now+2)

    def test_pc_only_rgb565_exact_size_tile_counts_and_metadata_budget(self):
        raw = self.transfer.raw_cover
        self.assertEqual(COVER_RAW_BYTES, 8192)
        self.assertEqual(len(raw), 8192)
        self.assertEqual(len(self.transfer.metadata) <= MAX_METADATA_BYTES, True)
        self.assertEqual(CHUNK_COUNT, 16)
        self.assertEqual(len(self.transfer.packets), CHUNK_COUNT)
        self.assertEqual([p.index for p in self.transfer.packets], list(range(16)))
        self.assertTrue(all(len(p.body) == CHUNK_BYTES for p in self.transfer.packets))
        self.assertEqual(b"".join(p.body for p in self.transfer.packets), raw)
        record = json.loads(self.transfer.metadata)
        self.assertEqual(record["cover_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record["title"], "Velvet HAMMER")

    def test_rgb565_color_conversion_and_nonjpeg_reject_coverless(self):
        raw = self.transfer.raw_cover
        # dominant gold-like RGB565, little-endian. byte exact conversion
        # checked by a local reconstruction of the top-left JPEG pixel.
        from PIL import Image, ImageOps
        with Image.open(BytesIO(self.jpeg)) as image:
            red, green, blue = ImageOps.fit(image.convert("RGB"),(64,64)).getpixel((0,0))
        packed = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
        self.assertEqual(raw[:2],packed.to_bytes(2,"little"))
        self.assertIsNone(jpeg_to_rgb565(b"not JPEG"))
        self.assertIsNone(jpeg_to_rgb565(b"\xff\xd8"+b"x"*45000))
        self.assertEqual(prepare(self.media,b"not JPEG",tx="b"*32).packets,())

    def test_authenticated_complete_atomic_commit_and_five_second_return(self):
        self.assertEqual(self.complete(),"COMMITTED")
        self.assertEqual(self.receiver.view,"NOW_PLAYING")
        self.assertEqual(self.receiver.metrics,(27,62,43,68))
        self.assertEqual(self.receiver.committed[1],self.transfer.raw_cover)
        self.assertEqual(self.receiver.tick(2+OVERLAY_SECONDS-.01),"NOW_PLAYING")
        self.assertEqual(self.receiver.tick(2+OVERLAY_SECONDS),"PC_HEALTH")

    def test_reject_unauthorized_before_allocating_and_no_secret_credentials(self):
        with self.assertRaisesRegex(ProtocolError,"UNAUTHORIZED"):
            self.receiver.begin(self.transfer.metadata,now=0)
        self.assertIsNone(self.receiver.pending)
        self.assertIsNone(self.receiver.committed)
        self.begin()
        with self.assertRaisesRegex(ProtocolError,"UNAUTHORIZED"):
            self.receiver.tile(self.transfer.packets[0], now=1)
        self.assertIsNone(self.receiver.pending)
        self.assertEqual(self.receiver.view,"PC_HEALTH")
        self.assertEqual(self.receiver.metrics,(27,62,43,68))

    def test_metadata_extra_key_oversize_noncanonical_invalid_types(self):
        bad=json.loads(self.transfer.metadata)
        bad["unexpected"]="yes"
        with self.assertRaises(ProtocolError):
            canonical_metadata(bad)
        bad.pop("unexpected")
        bad["position"]=True
        with self.assertRaises(ProtocolError):
            canonical_metadata(bad)
        bad["position"]=44
        bad["cover_len"]=8193
        with self.assertRaises(ProtocolError):
            canonical_metadata(bad)
        with self.assertRaisesRegex(ProtocolError,"OVERSIZE_METADATA"):
            self.receiver.begin(b" "*513,auth_verified=True)
        with self.assertRaisesRegex(ProtocolError,"INVALID_METADATA"):
            self.receiver.begin(b"{",auth_verified=True)
        # Same fields but not the canonical byte representation is rejected.
        reordered=json.dumps(json.loads(self.transfer.metadata),indent=2).encode("utf-8")
        self.assertLessEqual(len(reordered),MAX_METADATA_BYTES)
        with self.assertRaisesRegex(ProtocolError,"INVALID_METADATA|NONCANONICAL"):
            self.receiver.begin(reordered,auth_verified=True)

    def test_duplicate_same_payload_is_safe_but_conflicting_retry_aborts(self):
        self.begin()
        first=self.transfer.packets[0]
        self.assertEqual(self.receiver.tile(first,auth_verified=True,now=1),"STAGED")
        self.assertEqual(self.receiver.tile(first,auth_verified=True,now=1),"DUPLICATE")
        conflict=replace(first,body=b"x"*512,crc32=zlib.crc32(b"x"*512)&0xffffffff)
        with self.assertRaisesRegex(ProtocolError,"CONFLICTING_RETRY"):
            self.receiver.tile(conflict,auth_verified=True,now=1)
        self.assertIsNone(self.receiver.pending)
        self.assertIsNone(self.receiver.committed)
        self.assertEqual(self.receiver.view,"PC_HEALTH")

    def test_missing_out_of_order_wrong_id_wrong_length_crc_and_digest(self):
        self.begin()
        with self.assertRaisesRegex(ProtocolError,"OUT_OF_ORDER"):
            self.receiver.tile(self.transfer.packets[1],auth_verified=True,now=1)
        self.begin()
        with self.assertRaisesRegex(ProtocolError,"WRONG_TILE_ID"):
            self.receiver.tile(replace(self.transfer.packets[0],tx="f"*32),
                               auth_verified=True,now=1)
        self.begin()
        with self.assertRaisesRegex(ProtocolError,"TILE_LENGTH"):
            self.receiver.tile(replace(self.transfer.packets[0],body=b"a"),
                               auth_verified=True,now=1)
        self.begin()
        with self.assertRaisesRegex(ProtocolError,"TILE_CRC"):
            self.receiver.tile(replace(self.transfer.packets[0],crc32=3),
                               auth_verified=True,now=1)
        self.begin()
        with self.assertRaisesRegex(ProtocolError,"INCOMPLETE"):
            self.receiver.commit(auth_verified=True,now=1)
        self.begin()
        broken=replace(self.transfer.packets[-1],body=b"z"*512,
                       crc32=zlib.crc32(b"z"*512)&0xffffffff)
        for item in self.transfer.packets[:-1]:
            self.receiver.tile(item,auth_verified=True,now=1)
        self.receiver.tile(broken,auth_verified=True,now=1)
        with self.assertRaisesRegex(ProtocolError,"FINAL_SHA_MISMATCH"):
            self.receiver.commit(auth_verified=True,now=2)
        self.assertIsNone(self.receiver.committed)
        self.assertEqual(self.receiver.metrics,(27,62,43,68))

    def test_aborted_expired_transfer_retains_metrics_and_rejects_replay(self):
        self.begin(now=0)
        self.assertEqual(self.receiver.tick(MAX_TRANSACTION_SECONDS+0.1),"PC_HEALTH")
        self.assertIsNone(self.receiver.pending)
        self.assertEqual(self.receiver.metrics,(27,62,43,68))
        self.assertEqual(self.complete(now=20),"COMMITTED")
        self.assertEqual(self.receiver.committed[0]["title"],"Velvet HAMMER")
        with self.assertRaisesRegex(ProtocolError,"REPLAYED_TRANSFER"):
            self.begin(now=23)
        self.assertEqual(self.receiver.view,"PC_HEALTH")
        self.assertIsNone(self.receiver.pending)

    def test_coverless_state_and_pause_do_not_fake_new_overlay(self):
        paused=prepare(replace(self.media,state="PAUSED",cover_available=False),
                       None,tx="e"*32)
        self.assertEqual(paused.packets,())
        self.assertEqual(self.begin(paused),"STAGED")
        self.assertEqual(self.receiver.commit(auth_verified=True,now=1),"COMMITTED")
        self.assertEqual(self.receiver.view,"PC_HEALTH")
        self.assertIsNone(self.receiver.committed[1])
        playing=prepare(self.media,None,tx="c"*32)
        self.begin(playing,now=5)
        self.assertEqual(self.receiver.commit(auth_verified=True,now=6),"COMMITTED")
        self.assertEqual(self.receiver.view,"NOW_PLAYING")
        self.assertIsNone(self.receiver.committed[1])
        progress=prepare(replace(self.media,position_seconds=50),None,tx="d"*32)
        self.begin(progress,now=7)
        self.assertEqual(self.receiver.commit(auth_verified=True,now=8),"COMMITTED")
        self.assertEqual(self.receiver.until,11)
        self.assertEqual(self.receiver.tick(11),"PC_HEALTH")

    def test_long_utf8_metadata_never_exceeds_envelope_limit(self):
        very_long=replace(self.media,title="界"*120,artist="É"*120,album="界"*120,
                          source="界"*120)
        packet=prepare(very_long,None,tx="1"*32)
        self.assertLessEqual(len(packet.metadata),MAX_METADATA_BYTES)
        document=json.loads(packet.metadata)
        self.assertLessEqual(len(document["title"]),60)
        self.assertLessEqual(len(document["artist"]),60)
        self.assertEqual(canonical_metadata(document),packet.metadata)


if __name__=="__main__":
    unittest.main()
