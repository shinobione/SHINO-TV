"""Offline contracts for bounded HTTP observation. No sockets or serial."""
import unittest
from unittest.mock import patch

import shino_http_observe as target
from shino_qualify import QualificationFailure

SHA = "c" * 64
BUILD = "b" * 64
BOOT = "a" * 32
DEVICE = "0123456789abcdef"
IDENTITY = {"device": DEVICE}
RELEASE = {"device": DEVICE, "sha256": SHA, "build_id": BUILD, "bytes": 407792}


def status():
    return {
        "protocol": "shino-http-ota-1", "device": DEVICE, "ota_enabled": True,
        "fs_ok": True, "fs_files": 24, "fs_bytes": 181402,
        "nonce": "f" * 32, "boot_id": BOOT,
        "sha256": SHA, "build_id": BUILD, "bytes": 407792,
        "heap": 29552, "block": 27424, "stack": 2048, "frag": 8,
        "metrics_fresh": False,
    }


def fixture():
    return object()


class TestB2HttpObserve(unittest.TestCase):
    def reader(self, io, path, cycle):
        if path == "/api/v1/m9/normal/status":
            return {"mode": "M9_NORMAL_STAGE_A"}
        return status()

    def test_three_bounded_cycles_without_link_is_not_full_qualification(self):
        calls = []
        def read(io, path, cycle):
            calls.append((cycle, path))
            return self.reader(io, path, cycle)
        sleeps = []
        result = target.observe(fixture(), IDENTITY, RELEASE, cycles=3,
                                reader=read, sleep=sleeps.append,
                                clock=lambda: 42.0)
        self.assertEqual(result["status"], "READONLY_HTTP_OBSERVATION_PASS_NOT_QUALIFICATION")
        self.assertEqual(len(calls), 9)
        self.assertEqual(sleeps, [2, 2])
        self.assertFalse(result["metrics_fresh_at_last_read"])
        self.assertFalse(result["physical_acceptance"])
        self.assertEqual(result["automatic_retries"], 0)

    def test_timeout_aborts_without_retry(self):
        calls = []
        def read(io, path, cycle):
            calls.append((cycle, path))
            if cycle == 2 and path == "/api/v1/update/status":
                raise QualificationFailure("NETWORK_TIMEOUT", cycle, "GET " + path)
            return self.reader(io, path, cycle)
        result = target.observe(fixture(), IDENTITY, RELEASE, cycles=3,
                                reader=read, sleep=lambda _: None,
                                clock=lambda: 42.0)
        self.assertEqual(result["reason"], "NETWORK_TIMEOUT")
        self.assertEqual(result["cycle"], 2)
        self.assertEqual(len(calls), 4)
        self.assertEqual(result["successful_gets"], 3)
        self.assertEqual(result["ota_posts"], 0)

    def test_wrong_sha_and_unexpected_reboot_both_stop(self):
        def wrong(io, path, cycle):
            s = self.reader(io, path, cycle)
            if path == "/api/v1/update/status":
                s["sha256"] = "f" * 64
            return s
        r = target.observe(fixture(), IDENTITY, RELEASE, cycles=1,
                           reader=wrong, clock=lambda: 0)
        self.assertEqual(r["reason"], "RELEASE_IDENTITY_MISMATCH")
        def reboot(io, path, cycle):
            s = self.reader(io, path, cycle)
            if cycle == 2 and path == "/api/v1/update/status":
                s["boot_id"] = "d" * 32
            return s
        r = target.observe(fixture(), IDENTITY, RELEASE, cycles=2,
                           reader=reboot, sleep=lambda _: None,
                           clock=lambda: 0)
        self.assertEqual(r["reason"], "UNEXPECTED_REBOOT")

    def test_resource_floor_stops(self):
        def low(io, path, cycle):
            s = self.reader(io, path, cycle)
            if path == "/api/v1/update/status": s["stack"] = 1904
            return s
        r = target.observe(fixture(), IDENTITY, RELEASE, cycles=1,
                           reader=low, clock=lambda: 0)
        self.assertEqual(r["reason"], "STATUS_OR_RESOURCE_FLOOR_INVALID")

    def test_cycles_hard_limit(self):
        with self.assertRaises(ValueError):
            target.observe(fixture(), IDENTITY, RELEASE, cycles=4)

    @patch.object(target, "inspect", return_value=(RELEASE, b""))
    @patch.object(target, "Transport", side_effect=AssertionError("No network without consent"))
    @patch.object(target, "load_identity", side_effect=AssertionError("No private identity without consent"))
    def test_default_is_offline(self, _identity, _transport, _inspect):
        self.assertEqual(target.main(["--bin", "x", "--manifest", "y"]), 0)

    @patch.object(target, "inspect", return_value=(RELEASE, b""))
    @patch.object(target, "load_identity", return_value={"device": "ffffffffffffffff"})
    @patch.object(target, "Transport", side_effect=AssertionError("Must not contact wrong device"))
    def test_wrong_device_blocked_before_socket(self, _transport, _identity, _inspect):
        self.assertEqual(target.main(["--bin", "x", "--manifest", "y",
                                      "--authorize-read"]), 2)


if __name__ == "__main__":
    unittest.main()
