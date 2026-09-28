"""V0.6 deterministic resource/stress checks on HOST emulator only.

Python memory usage and this test-injected auth gate are not ESP8266 measured
heap or real HTTP validation. The logical payload sizes are asserted solely
to prevent a future proposal from accidentally assuming two 8KiB cover buffers.
"""
from dataclasses import replace
from io import BytesIO
import unittest
import zlib

from media_sessions import MediaSnapshot
from media_wire_v1 import (
    COVER_RAW_BYTES, CHUNK_BYTES, CHUNK_COUNT, MAX_METADATA_BYTES,
    MAX_TRANSACTION_SECONDS, OVERLAY_SECONDS, EmulatedReceiver, Packet,
    ProtocolError, prepare
)


class MediaV06ResourceStress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image
        output = BytesIO()
        Image.new("RGB",(192,192),(103,64,152)).save(output,format="JPEG")
        cls.jpeg=output.getvalue()

    def setUp(self):
        self.base = MediaSnapshot("PLAYING","Spotify.exe","Velvet HAMMER",
                                  "ShinoBiWan","Velvet HAMMER",44,229,True)
        self.receiver=EmulatedReceiver()
        self.assertEqual(self.receiver.metrics,(27,62,43,68))

    @staticmethod
    def image_bytes(receiver):
        staged = len(receiver.pending["buffer"]) if receiver.pending else 0
        committed = len(receiver.committed[1]) if (
            receiver.committed and receiver.committed[1]) else 0
        return staged, committed

    @staticmethod
    def send(receiver, prepared, at):
        assert receiver.begin(prepared.metadata,auth_verified=True,now=at)=="STAGED"
        for packet in prepared.packets:
            assert receiver.tile(packet,auth_verified=True,now=at+0.05)=="STAGED"
        return receiver.commit(auth_verified=True,now=at+0.1)

    def test_old_art_released_before_new_8k_staging_buffer(self):
        one=prepare(self.base,self.jpeg,tx="0"*32)
        self.assertEqual(self.send(self.receiver,one,0),"COMMITTED")
        self.assertEqual(self.image_bytes(self.receiver),(0,8192))
        two=prepare(replace(self.base,title="Weapon is FED"),self.jpeg,tx="1"*32)
        self.assertEqual(self.receiver.begin(two.metadata,auth_verified=True,now=3),"STAGED")
        self.assertEqual(self.image_bytes(self.receiver),(8192,0))
        self.assertEqual(self.receiver.view,"PC_HEALTH")
        self.assertEqual(self.receiver.metrics,(27,62,43,68))
        for frame in two.packets:
            self.receiver.tile(frame,auth_verified=True,now=3.1)
            self.assertEqual(self.image_bytes(self.receiver),(8192,0))
        self.assertEqual(self.receiver.commit(auth_verified=True,now=3.2),"COMMITTED")
        self.assertEqual(self.image_bytes(self.receiver),(0,8192))
        self.assertEqual(self.receiver.view,"NOW_PLAYING")

    def test_same_track_progress_does_not_restart_original_deadline(self):
        a=prepare(self.base,self.jpeg,tx="2"*32)
        self.assertEqual(self.send(self.receiver,a,0),"COMMITTED")
        self.assertEqual(self.receiver.until,0.1+OVERLAY_SECONDS)
        # New packets are staged with no previous full cover retained;
        # a verified same-track progress refresh restores the previous timer.
        b=prepare(replace(self.base,position_seconds=48),self.jpeg,tx="3"*32)
        self.assertEqual(self.send(self.receiver,b,2),"COMMITTED")
        self.assertEqual(self.receiver.view,"NOW_PLAYING")
        self.assertEqual(self.receiver.until,0.1+OVERLAY_SECONDS)
        self.assertEqual(self.receiver.tick(0.1+OVERLAY_SECONDS),"PC_HEALTH")
        self.assertEqual(self.receiver.metrics,(27,62,43,68))

    def test_failure_after_verified_song_does_not_restore_obsolete_cover(self):
        one=prepare(self.base,self.jpeg,tx="4"*32)
        self.send(self.receiver,one,0)
        two=prepare(replace(self.base,title="COAL TO DIAMOND"),self.jpeg,tx="5"*32)
        self.receiver.begin(two.metadata,auth_verified=True,now=2)
        self.assertEqual(self.image_bytes(self.receiver),(8192,0))
        broken=replace(two.packets[0],body=b"z"*512,crc32=0)
        with self.assertRaisesRegex(ProtocolError,"TILE_CRC"):
            self.receiver.tile(broken,auth_verified=True,now=2.2)
        self.assertEqual(self.image_bytes(self.receiver),(0,0))
        self.assertEqual(self.receiver.view,"PC_HEALTH")
        self.assertEqual(self.receiver.metrics,(27,62,43,68))

    def test_64_successive_mixed_valid_incomplete_and_coverless_transactions(self):
        # Each cycle has a fresh 128-bit hex id. This does NOT model long-lived
        # network anti-replay; an actual device must bind auth and nonce to peer.
        for index in range(64):
            transaction=f"{index+1000:032x}"
            media=replace(self.base,title="Track "+str(index),position_seconds=index)
            cover=self.jpeg if index%3!=0 else None
            packet=prepare(media,cover,tx=transaction)
            self.assertLessEqual(len(packet.metadata),MAX_METADATA_BYTES)
            if cover:
                self.assertEqual(len(packet.packets),CHUNK_COUNT)
                self.assertEqual(sum(len(p.body) for p in packet.packets),COVER_RAW_BYTES)
            else:
                self.assertEqual(len(packet.packets),0)
            now=float(index*20)
            self.assertEqual(self.receiver.begin(packet.metadata,auth_verified=True,now=now),"STAGED")
            self.assertLessEqual(sum(self.image_bytes(self.receiver)),8192)
            if index%7==5 and cover:
                # Interrupted transfer: no commit and no lingering old cover.
                self.receiver.tile(packet.packets[0],auth_verified=True,now=now+.1)
                self.assertEqual(self.receiver.tick(now+MAX_TRANSACTION_SECONDS+.1),"PC_HEALTH")
                self.assertEqual(self.image_bytes(self.receiver),(0,0))
            else:
                for frame in packet.packets:
                    self.assertEqual(self.receiver.tile(frame,auth_verified=True,now=now+.1),"STAGED")
                self.assertEqual(self.receiver.commit(auth_verified=True,now=now+.2),"COMMITTED")
                self.assertEqual(sum(self.image_bytes(self.receiver)),
                                 COVER_RAW_BYTES if cover else 0)
                self.assertEqual(self.receiver.tick(now+.2+OVERLAY_SECONDS),"PC_HEALTH")
            self.assertEqual(self.receiver.metrics,(27,62,43,68))

    def test_metadata_coverless_has_no_staging_or_flash_side_effect(self):
        packet=prepare(replace(self.base,state="NO_SESSION",title="",artist="",
                               album="",position_seconds=None,duration_seconds=None),
                       None,tx="f"*32)
        self.assertEqual(len(packet.metadata)<=MAX_METADATA_BYTES,True)
        self.assertEqual(packet.packets,())
        self.assertEqual(self.receiver.begin(packet.metadata,auth_verified=True,now=0),"STAGED")
        self.assertEqual(self.image_bytes(self.receiver),(0,0))
        self.assertEqual(self.receiver.commit(auth_verified=True,now=.1),"COMMITTED")
        self.assertEqual(self.receiver.view,"PC_HEALTH")


if __name__=="__main__":
    unittest.main()
