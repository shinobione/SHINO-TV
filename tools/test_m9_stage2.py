"""Phase F deterministic local fixtures only; never uses a serial executor."""
import ast
import hashlib
import importlib.metadata
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m9_stage2_fs_candidate import (
    FS_START, FS_END, FS_BYTES, FLASH_END, FS_BLOCK, FS_PAGE, ENVIRONMENT,
    Stage2Error, geometry, reviewed_source, prepare_source, inspect, local_path,
)
from m9_stage2_readback_verify import verify_stage2
from m9_stage2_executor import raw_write_bounds, render_packet
from m9_executor_preflight import FROZEN_SHA, FROZEN_BYTES, inspect_sources

REPO = Path(__file__).resolve().parents[1]


class Stage2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.image, self.pre, self.post = (self.root / n for n in ("fs.bin", "pre.bin", "post.bin"))
        self.payload = b"\x5a" * FS_BYTES
        self.before = b"\x31" * FLASH_END
        self.after = self.before[:FS_START] + self.payload + self.before[FS_END:]
        for p, b in ((self.image, self.payload), (self.pre, self.before), (self.post, self.after)):
            p.write_bytes(b)
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.ini = REPO / "firmware/platformio.ini"
        self.data = REPO / "firmware/data"

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self):
        return verify_stage2(self.image, self.pre, self.post, self.sha)

    def copy_source(self):
        target = self.root / "data"
        shutil.copytree(self.data, target)
        return target

    def fs_fixture(self, *, changed=None, extra=False, block=FS_BLOCK):
        from littlefs import LittleFS
        files = reviewed_source(self.data)
        fs = LittleFS(block_size=block, block_count=FS_BYTES // block,
                      read_size=FS_PAGE, prog_size=FS_PAGE, disk_version=0x00020000)
        for directory in ("/web", "/web/css", "/web/js"):
            fs.mkdir(directory)
        for name, body in sorted(files.items()):
            with fs.open("/" + name, "wb") as dest:
                dest.write(body if name != changed else b"changed")
        if extra:
            with fs.open("/private.txt", "wb") as dest:
                dest.write(b"synthetic private asset")
        self.image.write_bytes(fs.context.buffer)
        fs.unmount()
        self.sha = hashlib.sha256(self.image.read_bytes()).hexdigest()

    def candidate(self):
        return inspect(self.image, self.sha, self.data, self.ini)

    def test_exact_4m2m_geometry(self):
        g = geometry(self.ini)
        self.assertEqual((g["environment"], g["target"], g["end_exclusive"], g["image_bytes"]),
                         (ENVIRONMENT, 0x200000, 0x3FA000, 2072576))
        self.assertEqual((g["sector_count"], g["fs_block_bytes"], g["fs_page_bytes"]), (506,8192,256))

    def test_inherited_default_4m3m_is_rejected(self):
        ini = self.root / "bad.ini"
        ini.write_text(self.ini.read_text().replace("eagle.flash.4m2m.ld", "eagle.flash.4m3m.ld"))
        with self.assertRaises(ValueError):
            geometry(ini)

    def test_synthetic_preservation_pass_no_device_authority(self):
        r = self.verify()
        self.assertEqual((r["lower_protected_bytes_compared"], r["tail_protected_bytes_compared"]), (2097152,24576))
        self.assertTrue(r["filesystem_exact"])
        self.assertFalse(r["pre_fs_equality_required"])
        self.assertFalse(r["device_claims"])
        self.assertFalse(r["physical_authorization"])
        self.assertFalse(r["physical_capture_freshness_proven"])
        self.assertFalse(r["filesystem_package_qualification_proven_by_this_comparison"])
        self.assertNotIn("pre_sha256", r)
        self.assertNotIn("post_sha256", r)

    def test_protected_boundary_mutations_fail(self):
        for offset in (0, FS_START-1, FS_END, FLASH_END-1):
            with self.subTest(offset=offset):
                altered = bytearray(self.after)
                altered[offset] ^= 1
                self.post.write_bytes(altered)
                with self.assertRaisesRegex(ValueError, "protected"):
                    self.verify()

    def test_fs_payload_boundary_mutations_fail(self):
        for offset in (FS_START, FS_END-1):
            with self.subTest(offset=offset):
                altered = bytearray(self.after)
                altered[offset] ^= 1
                self.post.write_bytes(altered)
                with self.assertRaisesRegex(ValueError, "filesystem payload"):
                    self.verify()

    def test_wrong_hash_fails(self):
        self.sha = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.verify()

    def test_malformed_hash_fails(self):
        for value in ("", "g"*64, "0"*63):
            self.sha = value
            with self.assertRaises(ValueError):
                self.verify()

    def test_wrong_image_lengths_fail(self):
        for size in (FS_BYTES-1, FS_BYTES+1, 4096):
            self.image.write_bytes(b"x"*size)
            with self.assertRaisesRegex(ValueError, "2072576"):
                self.verify()

    def test_wrong_pre_lengths_fail(self):
        for size in (FLASH_END-1, FLASH_END+1):
            self.pre.write_bytes(b"x"*size)
            with self.assertRaisesRegex(ValueError, "4194304"):
                self.verify()

    def test_wrong_post_lengths_fail(self):
        for size in (FLASH_END-1, FLASH_END+1):
            self.post.write_bytes(b"x"*size)
            with self.assertRaisesRegex(ValueError, "4194304"):
                self.verify()

    def test_image_symlink_fails(self):
        link = self.root / "linked.bin"
        try:
            link.symlink_to(self.image)
        except OSError as exc:
            if os.name != "nt" or exc.winerror != 1314:
                raise
            # Windows may deny creating links. Exercise the same rejection with
            # mocked link metadata; Linux CI uses an actual symlink above.
            original = Path.is_symlink
            with patch.object(Path, "is_symlink", lambda p: p == self.image or original(p)):
                with self.assertRaisesRegex(ValueError, "Symlink"):
                    verify_stage2(self.image, self.pre, self.post, self.sha)
        else:
            with self.assertRaisesRegex(ValueError, "Symlink"):
                verify_stage2(link, self.pre, self.post, self.sha)

    def test_source_symlink_fails(self):
        data = self.copy_source()
        try:
            (data / "linked").symlink_to(self.data, target_is_directory=True)
        except OSError as exc:
            if os.name != "nt" or exc.winerror != 1314:
                raise
            original = Path.is_symlink
            with patch.object(Path, "is_symlink", lambda p: p == data / "web" or original(p)):
                with self.assertRaisesRegex(ValueError, "Symlink"):
                    reviewed_source(data)
        else:
            with self.assertRaisesRegex(ValueError, "Symlink"):
                reviewed_source(data)

    def test_unreviewed_platform_core_rejected(self):
        ini = self.root / "bad-core.ini"
        ini.write_text(self.ini.read_text().replace("3.30102.0", "3.30101.0"))
        with self.assertRaisesRegex(ValueError, "platform/Core"):
            geometry(ini)

    def test_alias_readbacks_fail(self):
        with self.assertRaisesRegex(ValueError, "independent"):
            verify_stage2(self.image, self.pre, self.pre, self.sha)

    def test_hardlinked_readbacks_fail(self):
        link = self.root / "alias.bin"
        link.hardlink_to(self.pre)
        with self.assertRaisesRegex(ValueError, "independent"):
            verify_stage2(self.image, self.pre, link, self.sha)

    def test_network_and_device_paths_fail(self):
        for path in (r"\\server\share\fs.bin", r"\\.\COM1"):
            with self.assertRaisesRegex(ValueError, "Network/device"):
                local_path(Path(path))

    def test_reviewed_source_exact_inventory(self):
        files = reviewed_source(self.data)
        self.assertEqual(len(files), 24)
        self.assertEqual(json.loads(files["config.json"]),
                         {"wifi_ssid":"", "wifi_password":"", "api_token":"", "lcd_rotation":0})

    def test_seed_secret_rejected(self):
        data = self.copy_source()
        config = {"wifi_ssid":"", "wifi_password":"synthetic-secret", "api_token":"", "lcd_rotation":0}
        (data / "config.json").write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "non-secret"):
            reviewed_source(data)

    def test_seed_wrong_default_type_rejected(self):
        data = self.copy_source()
        config = {"wifi_ssid":"", "wifi_password":"", "api_token":"", "lcd_rotation":False}
        (data / "config.json").write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            reviewed_source(data)

    def test_arbitrary_private_asset_rejected(self):
        data = self.copy_source()
        (data / "credentials.txt").write_text("synthetic-secret")
        with self.assertRaisesRegex(ValueError, "private"):
            reviewed_source(data)

    def test_changed_secret_in_allowed_asset_rejected(self):
        data = self.copy_source()
        (data / "web/js/wifiHandler.js").write_text('password="synthetic-secret"')
        with self.assertRaisesRegex(ValueError, "asset changed"):
            reviewed_source(data)

    def test_generic_updater_artifact_rejected(self):
        data = self.copy_source()
        (data / "web/js/otaUploadHandler.js").write_text("fetch('/api/v1/ota/fs')")
        with self.assertRaises(ValueError):
            reviewed_source(data)

    def test_missing_reviewed_file_rejected(self):
        data = self.copy_source()
        (data / "web/index.html").unlink()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            reviewed_source(data)

    def test_oversized_reviewed_asset_rejected(self):
        data = self.copy_source()
        (data / "web/index.html").write_bytes(b"x"*200001)
        with self.assertRaisesRegex(ValueError, "oversized"):
            reviewed_source(data)

    def test_new_build_source_only_no_overwrite(self):
        output = self.root / "prepared"
        self.assertEqual(prepare_source(self.data, output, self.ini)["files"],24)
        self.assertEqual(int((output/"config.json").stat().st_mtime),1704067200)
        with self.assertRaises(FileExistsError):
            prepare_source(self.data, output, self.ini)

    def test_independent_parser_exact_contents_read_only(self):
        self.fs_fixture()
        r = self.candidate()
        self.assertTrue(r["image_inventory_exact"])
        self.assertFalse(r["parser_autoformat"])
        self.assertEqual(r["parser_writes"],0)
        self.assertFalse(r["physical_authorization"])

    def test_parser_rejects_corrupt_image_without_autoformat(self):
        with self.assertRaisesRegex(ValueError, "parsing failed"):
            self.candidate()
        self.assertEqual(self.image.read_bytes(),self.payload)

    def test_parser_rejects_changed_content(self):
        self.fs_fixture(changed="web/index.html")
        with self.assertRaises(ValueError):
            self.candidate()

    def test_parser_rejects_private_image_file(self):
        self.fs_fixture(extra=True)
        with self.assertRaisesRegex(ValueError, "private entry"):
            self.candidate()

    def test_parser_rejects_wrong_block_geometry(self):
        self.fs_fixture(block=4096)
        with self.assertRaises(ValueError):
            self.candidate()

    def test_raw_bounds_padded_last_block_and_whole_retry(self):
        model = raw_write_bounds()
        self.assertEqual((model["erase_start"],model["erase_end_inclusive"]),(FS_START,FS_END-1))
        self.assertEqual(model["last_payload_bytes_default"],8192)
        self.assertEqual(len(model["attempts"]),2)
        self.assertEqual(model["attempts"][0],model["attempts"][1])
        for attempt in model["attempts"]:
            for start,end in attempt["writes"]:
                self.assertTrue(FS_START <= start <= end <= FS_END)
        for start,end in model["erase_operations_max"]:
            self.assertTrue(FS_START <= start < end <= FS_END)

    def test_replayed_wire_block_cannot_extend_beyond_tail(self):
        r = raw_write_bounds(deliveries=[16384]*129)
        self.assertEqual(r["attempts"][0]["end_exclusive"],FS_END)
        self.assertFalse(r["retry_payload_idempotence_proven"])

    def test_wrong_raw_address_or_size_rejected(self):
        for address,size in ((0,FS_BYTES),(FS_START+4096,FS_BYTES),(FS_START,FS_BYTES+4096)):
            with self.assertRaises(ValueError):
                raw_write_bounds(address,size)

    def test_exact_stage2_template_and_separate_rollback(self):
        r = render_packet()
        stage2 = next(s for s in r["steps"] if s["step"]=="D")
        self.assertIn('write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x200000 "<FS_IMAGE>"',stage2["template"])
        self.assertNotIn("0x000000",stage2["template"])
        self.assertNotIn("0x3FA000",stage2["template"])
        self.assertNotIn("erase-all",json.dumps(r))
        self.assertNotIn("http",json.dumps(r).lower())
        self.assertFalse(r["automatic_rollback"])
        self.assertFalse(r["physical_authorization"])
        for s in r["steps"]:
            if s["authorization"] != "LOCAL FILES ONLY":
                self.assertTrue(s["template"].startswith("# NOT AUTHORIZED BY PHASE F"))
            if 'write-flash' in s["template"] and s["step"] != "D":
                self.assertTrue(s["rollback_separate_authority"])
        boot = next(s for s in r["steps"] if s["step"]=="H")["template"]
        self.assertIn("release GPIO0 while powered",boot)

    def test_no_device_executor_in_new_tooling(self):
        forbidden={"serial","esptool","socket","requests","urllib","http","subprocess"}
        for name in ("m9_stage2_fs_candidate.py","m9_stage2_executor.py","m9_stage2_readback_verify.py"):
            tree=ast.parse((REPO/"tools"/name).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    self.assertFalse(forbidden & {n.name.split('.')[0] for n in node.names})
                elif isinstance(node,ast.ImportFrom):
                    self.assertNotIn(node.module.split('.')[0],forbidden)
                elif isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                    self.assertNotIn(node.func.id,{"exec","eval","__import__"})

    def test_stage1_freeze_and_normal_profile_hold_unchanged(self):
        self.assertEqual(FROZEN_BYTES,399168)
        self.assertEqual(FROZEN_SHA,"cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011")
        source=(REPO/"firmware/platformio.ini").read_text()
        self.assertNotIn("SHINO_BOOT_PROFILE=1",source)

    def test_pinned_original_header_function_leaves_nonboot_raw_bytes_unchanged(self):
        root=Path(importlib.metadata.distribution("esptool").locate_file("esptool"))
        inspect_sources(root)  # exact complete package pin BEFORE evaluating one pure function
        tree=ast.parse((root/"cmds.py").read_text(encoding="utf-8"))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_update_image_flash_params")
        namespace={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),"pinned_header_function","exec"),namespace)
        target=type("NonDeviceOffset",(),{"BOOTLOADER_FLASH_OFFSET":0})()
        for flags in (("keep","keep","keep"),("40m","dio","4MB")):
            self.assertIs(namespace[fn.name](target,FS_START,*flags,self.payload),self.payload)


if __name__ == "__main__":
    unittest.main()
