"""Public synthetic owner-packet identity/layout tests. No private file reads."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shino_b51_owner_packet as packet
from shino_b51_owner_packet import verify_installed,staging,LAYOUT
from test_shino_http_ota import fixture


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name);self.raw=fixture()
        self.binary=self.path/"firmware.bin";self.binary.write_bytes(self.raw)
        self.release=dict(schema=1,family="SHINO-StageA",layout="4m2m",protocol="shino-http-ota-1",
                          device="0123456789abcdef",bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),build_id="b"*64)
        self.manifest=self.path/"release.json";self.manifest.write_text(json.dumps(self.release))
        self.report=self.path/"report.json"
        self.proof=dict(self.release,source_commit="c"*40,layout_symbols=LAYOUT)
        self.report.write_text(json.dumps(self.proof))

    def verify(self,**extra):
        pins=dict(expected_sha=self.release["sha256"],expected_build="b"*64,expected_source="c"*40);pins.update(extra)
        return verify_installed(self.binary,self.manifest,self.report,**pins)

    def test_exact_installed_bytes_provenance_and_layout(self):
        self.assertEqual(self.verify(),self.release)

    def test_hash_build_and_source_cannot_be_substituted(self):
        for extra in ({"expected_sha":"0"*64},{"expected_build":"a"*64},{"expected_source":"d"*40}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.verify(**extra)

    def test_corrupt_bin_rejected(self):
        self.binary.write_bytes(self.raw[:-1]+bytes([self.raw[-1]^1]))
        with self.assertRaises(ValueError):self.verify()

    def test_report_layout_and_duplicate_fields_rejected(self):
        self.proof["layout_symbols"]=dict(LAYOUT,_FS_start=0x40300000)
        self.report.write_text(json.dumps(self.proof))
        with self.assertRaises(ValueError):self.verify()
        self.report.write_text('{"source_commit":"'+"c"*40+'","source_commit":"'+"c"*40+'"}')
        with self.assertRaises(ValueError):self.verify()

    def test_actual_installed_size_has_safe_public_successor_geometry(self):
        layout=staging(412848,414096)
        self.assertEqual(layout["staging_end"],0x200000)
        self.assertGreaterEqual(layout["guard_bytes"],4096)
        self.assertGreaterEqual(staging(0xFEFF0,0xFEFF0)["guard_bytes"],4096)
        for sizes in ((0,414096),(412848,0xFEFF1),(0x100000,0xFEFF0)):
            with self.subTest(sizes=sizes),self.assertRaises(ValueError):staging(*sizes)

    def test_fresh_private_packet_gates_with_synthetic_builder(self):
        repo=self.path/"repo";source=repo/"ota/firmware/Normal.cpp";source.parent.mkdir(parents=True)
        source.write_bytes(b"PUBLIC INERT NORMAL SOURCE\n")
        calls=[]
        def git(command,**kwargs):
            if command[1:]==["branch","--show-current"]:return packet.BRANCH+"\n"
            if command[1:]==["status","--porcelain"]:return ""
            if command[1:]==["rev-parse","HEAD"]:return "e"*40+"\n"
            if command[1]=="show":return source.read_bytes()
            raise AssertionError(command)
        def build(directory,private):
            calls.append(private);target=fixture(build_id="d"*64)
            binary=directory/".pio/build"/packet.ENV/"firmware.bin";binary.parent.mkdir(parents=True)
            binary.write_bytes(target);release=dict(self.release,sha256=hashlib.sha256(target).hexdigest(),build_id="d"*64)
            (directory/"release.json").write_text(json.dumps(release))
            return dict(layout_symbols=LAYOUT,source_commit="e"*40,source_dirty=False,firmware="B5.1",static_ram=44904)
        originals={p:p.read_bytes() for p in (self.binary,self.manifest,self.report)}
        output=self.path/"new-packet"
        with patch.object(packet,"ROOT",repo),patch.object(packet,"OWNER",self.path),\
             patch.object(packet.subprocess,"check_output",side_effect=git),\
             patch.object(packet,"load",return_value={"device":self.release["device"]}),\
             patch.object(packet,"build",side_effect=build),patch("socket.socket",side_effect=AssertionError("device contact")):
            result=packet.prepare(output,self.binary,self.manifest,self.report,self.release["sha256"],"b"*64,"c"*40)
            self.assertEqual(result["status"],"B51_PRIVATE_CANDIDATE_OFFLINE_ONLY")
            self.assertFalse(result["physical_authorized"])
            self.assertEqual(calls,[True])
            with self.assertRaises(ValueError):packet.prepare(output,self.binary,self.manifest,self.report,self.release["sha256"],"b"*64,"c"*40)
        self.assertTrue((output/"OWNER-QUALIFICATION.md").is_file())
        for path,data in originals.items():self.assertEqual(path.read_bytes(),data)


if __name__=="__main__":unittest.main()
