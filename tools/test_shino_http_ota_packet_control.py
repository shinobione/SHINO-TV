"""Inert physical-command seams; no serial object, real subprocess or network."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from shino_http_ota_packet_control import run


class PacketControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);helpers=self.root/"helpers";helpers.mkdir()
        helper=helpers/"inert.py";helper.write_text("# inert\n")
        self.image=bytes([0xe9])*64000;self.candidate=self.root/"A2.bin";self.candidate.write_bytes(self.image)
        raw=self.image+bytes([0x5a])*(0x400000-len(self.image))
        self.ref=self.root/"historical-POST.bin";self.ref.write_bytes(raw)
        self.pre=self.root/"PRE-4MiB.bin";self.post=self.root/"POST-4MiB.bin"
        self.data=dict(candidate_sha256=hashlib.sha256(self.image).hexdigest(),
            source_sha256_lf={"inert.py":hashlib.sha256(helper.read_bytes().replace(b"\r\n",b"\n")).hexdigest()},
            fresh_pre_argv=["INERT_READ",str(self.pre)],fresh_post_argv=["INERT_READ",str(self.post)],
            writer_internal_argv=["INERT_WRITE","--execute"],
            physical_control=dict(candidate=str(self.candidate),helper_directory="helpers",
                owner_go={k:"EXACT_OWNER_"+k for k in ("pre","write","post")},
                reference=dict(path=str(self.ref),sha256=hashlib.sha256(raw).hexdigest(),
                    installed_sha256=hashlib.sha256(self.image).hexdigest(),installed_bytes=len(self.image))))
        self.book=self.root/"commands.json";self.save();self.calls=[]

    def save(self):
        self.book.write_text(json.dumps(self.data),encoding="utf-8")
        self.sha=hashlib.sha256(self.book.read_bytes()).hexdigest()

    def runner(self,argv,**kwargs):
        self.calls.append(argv)
        if argv[0]=="INERT_READ":Path(argv[-1]).write_bytes(self.ref.read_bytes())
        return SimpleNamespace(returncode=0)

    def do(self,operation,runner=None):
        return run(self.book,operation,self.sha,True,"EXACT_OWNER_"+operation,runner or self.runner)

    def pre_captured(self):self.do("pre")

    def test_print_only_every_action_does_not_run_or_reserve(self):
        for action in ("pre","write","post"):
            result=run(self.book,action,self.sha,runner=self.runner)
            self.assertEqual(result["status"],"PRINT_ONLY_NO_PORT_OPEN")
        self.assertFalse(self.calls);self.assertFalse(list(self.root.glob("*.attempt")))

    def test_wrong_book_go_helper_or_candidate_before_contact(self):
        with self.assertRaises(ValueError):run(self.book,"pre","0"*64,True,"EXACT_OWNER_pre",self.runner)
        with self.assertRaises(ValueError):run(self.book,"pre",self.sha,True,"WRONG",self.runner)
        (self.root/"helpers/inert.py").write_text("changed")
        with self.assertRaises(ValueError):self.do("pre")
        self.assertFalse(self.calls)

    def test_complete_sequence_has_one_call_and_marker_per_operation(self):
        self.pre_captured();self.do("write");self.do("post")
        self.assertEqual(len(self.calls),3)
        for action in ("pre","write","post"):
            with self.assertRaises(ValueError):self.do(action)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(self.post.read_bytes(),self.pre.read_bytes())

    def test_existing_backup_never_overwritten(self):
        self.pre.write_bytes(b"KEEP")
        with self.assertRaises(ValueError):self.do("pre")
        self.assertEqual(self.pre.read_bytes(),b"KEEP");self.assertFalse(self.calls)

    def test_unknown_write_blocks_post_and_every_repeat(self):
        self.pre_captured()
        def unknown(argv,**kwargs):self.calls.append(argv);raise OSError("RAW-SECRET-MUST-NOT-ESCAPE")
        with self.assertRaises(ValueError):self.do("write",unknown)
        for action in ("write","post","pre"):
            with self.assertRaises(ValueError):self.do(action)
        self.assertEqual(len(self.calls),2)
        self.assertNotIn("RAW-SECRET",(self.root/"UART-write-result.json").read_text())

    def test_pre_without_capture_receipt_never_opens_writer(self):
        self.pre.write_bytes(self.ref.read_bytes())
        with self.assertRaises(ValueError):self.do("write")
        self.assertFalse(self.calls)

    def test_wrong_running_image_or_device_flash_fingerprint_before_write(self):
        for at in (0,0x200000,0x3fa000,0x3fffff):
            with self.subTest(at=at):
                self.pre.write_bytes(self.ref.read_bytes())
                with self.pre.open("r+b") as p:p.seek(at);p.write(b"\x33")
                (self.root/"UART-pre-result.json").write_text('{"completed":true}')
                with self.assertRaises(ValueError):self.do("write")
        self.assertFalse(self.calls)

    def test_historical_failed_ota_staging_difference_is_allowed(self):
        self.pre_captured()
        with self.pre.open("r+b") as p:p.seek(0x190000);p.write(b"\x11")
        self.do("write");self.assertEqual(len(self.calls),2)

    def test_unacknowledged_post_is_not_started(self):
        self.pre_captured()
        with self.assertRaises(ValueError):self.do("post")
        self.assertEqual(len(self.calls),1)

    def test_changed_candidate_prevents_any_physical_action(self):
        self.candidate.write_bytes(b"BAD")
        with self.assertRaises(ValueError):self.do("pre")
        self.assertFalse(self.calls)


if __name__=="__main__":unittest.main()
