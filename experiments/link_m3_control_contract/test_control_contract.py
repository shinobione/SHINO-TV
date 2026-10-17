"""M3-A offline contract tests. All target/device/auth are in-memory fakes.

Host SUCCESS must NEVER be interpreted as real firmware Digest/HTTP success.
"""
import builtins
from dataclasses import FrozenInstanceError
import json
import socket
import unittest
from unittest.mock import patch

from control_contract import (
    ACK_MAX, CAPABILITIES_MAX, COMMAND_MAX, MAX_REVISION, MODE_POST, PROTOCOL,
    STATUS_MAX, AdmissionDenied, Binding, ContractError, FakeDevice,
    LabTransport, LinkFailure, Mode, Outcome, Scene, Session, SimulatedAuth,
    State, _encode, ack, capabilities, command, parse_command, status,
)


BIND = Binding("192.168.1.46", "1234567890abcdef",
               "1234567890abcdef1234567890abcdef")
NEWBOOT = "abcdef1234567890abcdef1234567890"
TX1 = "00000000000000000000000000000001"
TX2 = "00000000000000000000000000000002"
TX3 = "00000000000000000000000000000003"


def raw(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()


class Faults(LabTransport):
    def __init__(self, device, *, at=None):
        super().__init__(device)
        self.at = at

    def get_capabilities(self):
        if self.at == "before_caps":
            raise TimeoutError("caps unavailable")
        value = super().get_capabilities()
        if self.at == "bad_caps":
            return b'{"protocol":"unrelated"}'
        return value

    def get_status(self):
        if self.at == "before_status":
            raise LinkFailure("GET failure")
        value = super().get_status()
        if self.at == "after_post_get" and self.posts:
            raise LinkFailure("readback failure")
        if self.at == "readback_false" and self.posts:
            packet = status(value)
            packet["last_tx"] = TX2
            return raw(packet)
        if self.at == "wrong_readback_boot" and self.posts:
            packet = status(value)
            packet["boot"] = NEWBOOT
            return raw(packet)
        return value

    def post_mode(self, value):
        if self.at == "before_post":
            self.posts += 1
            raise LinkFailure("request not sent; client cannot prove that")
        response = super().post_mode(value)
        if self.at == "after_post":
            raise LinkFailure("ACK lost after application")
        if self.at == "ack_modified":
            packet = ack(response)
            packet["tx"] = TX2
            return raw(packet)
        if self.at == "ack_false":
            packet = ack(response)
            packet["accepted"] = False
            return raw(packet)
        if self.at == "ack_wrong_boot":
            packet = ack(response)
            packet["boot"] = NEWBOOT
            return raw(packet)
        return response


class ParsingAndSecurityTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice(BIND)

    def test_contract_is_proposed_and_non_ota(self):
        self.assertEqual(PROTOCOL, "shino-display-control-1")
        self.assertEqual(MODE_POST, "/api/v1/display/mode")
        self.assertTrue(all(x < 512 for x in (
            COMMAND_MAX, CAPABILITIES_MAX, ACK_MAX, STATUS_MAX)))

    def test_all_four_modes_are_distinct_and_round_trip(self):
        for mode in Mode:
            with self.subTest(mode=mode):
                wire = command(mode, BIND, 5, TX1)
                self.assertLessEqual(len(wire), COMMAND_MAX)
                parsed = parse_command(wire)
                self.assertEqual(parsed["mode"], mode.value)
                self.assertEqual(parsed["boot"], BIND.boot)
                self.assertEqual(parsed["device"], BIND.device)
                self.assertEqual(parsed["revision"], 5)
                self.assertEqual(parsed["tx"], TX1)
                self.assertEqual(command(mode, BIND, 5, TX1), wire)
                self.assertEqual(set(parsed), {
                    "protocol", "device", "boot", "revision", "mode", "tx"})

    def test_all_response_schemas_are_closed_and_bounded(self):
        c = capabilities(self.device.get_capabilities())
        self.assertEqual(c["modes"], [x.value for x in Mode])
        s = status(self.device.get_status())
        self.assertIsNone(s["last_tx"])
        a = ack(self.device.post(command(Mode.MUSIC, BIND, 0, TX1)))
        self.assertTrue(a["accepted"])
        self.assertEqual(a["revision"], 1)
        st = status(self.device.get_status())
        self.assertEqual(st["last_tx"], TX1)
        self.assertEqual(st["scene"], Scene.OFFLINE.value)
        self.assertEqual(st["mode"], Mode.MUSIC.value)

    def test_reject_unknown_fields_missing_fields_and_json_duplicates(self):
        cmd = parse_command(command(Mode.AUTO, BIND, 0, TX1))
        for mutation in (
            dict(cmd, extra=True),
            {k: v for k, v in cmd.items() if k != "tx"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                parse_command(raw(mutation))
        text = command(Mode.AUTO, BIND, 0, TX1)
        duplicates = text.replace(b'"mode":"AUTO"', b'"mode":"AUTO","mode":"MUSIC"')
        with self.assertRaises(ContractError):
            parse_command(duplicates)
        with self.assertRaises(ContractError):
            status(b'{"revision":0,"revision":1}')
        with self.assertRaises(ContractError):
            ack(b'{"accepted":true,"accepted":true}')

    def test_invalid_types_protocol_mode_and_revision(self):
        request = parse_command(command(Mode.AUTO, BIND, 0, TX1))
        for field, invalid in (
            ("protocol", "other"), ("mode", "REBOOT"), ("mode", None),
            ("revision", -1), ("revision", True), ("revision", 1.0),
            ("revision", MAX_REVISION + 1), ("device", "x"),
            ("boot", "0" * 32), ("tx", "A" * 32),
        ):
            with self.subTest(field=field, invalid=invalid):
                invalid_req = dict(request, **{field: invalid})
                with self.assertRaises(ContractError):
                    parse_command(raw(invalid_req))
        for bad in ("MUSIC", None, 4):
            with self.assertRaises(ContractError):
                command(bad, BIND, 0, TX1)

    def test_malformed_json_unicode_nonfinite_and_bounded_body(self):
        for payload in (
            b"", b"[1]", b"null", b"\xff", b"{", b"[]" * 500,
            b'{"revision":NaN}', b'{"revision":1e309}', b" " * (COMMAND_MAX + 1),
        ):
            with self.subTest(payload=payload[:20]), self.assertRaises(ContractError):
                parse_command(payload)
        with self.assertRaises(ContractError):
            parse_command("unicode not bytes")
        with self.assertRaises(ContractError):
            status(b"x" * (STATUS_MAX + 1))
        with self.assertRaises(ContractError):
            capabilities(b"x" * (CAPABILITIES_MAX + 1))
        with self.assertRaises(ContractError):
            ack(b"x" * (ACK_MAX + 1))

    def test_binding_must_be_private_ipv4_and_external_immutable(self):
        for bad in (
            "8.8.8.8", "127.0.0.1", "224.0.0.1", "0.0.0.0", "::1",
            "192.168.01.46", "", None,
        ):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                Binding(bad, BIND.device, BIND.boot)
        with self.assertRaises(ContractError):
            Binding(BIND.host, "notidentity", BIND.boot)
        with self.assertRaises(ContractError):
            Binding(BIND.host, BIND.device, "0" * 32)
        with self.assertRaises(FrozenInstanceError):
            BIND.host = "192.168.1.90"

    def test_digest_and_prebody_gate_before_reading_body(self):
        for auth in (SimulatedAuth(False, True), SimulatedAuth(True, False),
                     SimulatedAuth(False, False)):
            fake = FakeDevice(BIND, auth=auth)
            with self.subTest(auth=auth):
                with self.assertRaises(AdmissionDenied):
                    fake.post(b"{" + b"Z" * 400)
                self.assertEqual(fake.body_reads, 0)
                self.assertEqual(fake.commits, 0)
                with self.assertRaises(AdmissionDenied):
                    fake.get_status()
                with self.assertRaises(AdmissionDenied):
                    fake.get_capabilities()
        for invalid in ((1, True), (True, "yes")):
            with self.assertRaises(ContractError):
                SimulatedAuth(*invalid)

    def test_boot_replay_idempotence_stale_cas_and_conflict(self):
        first = command(Mode.MONITORING, BIND, 0, TX1)
        a = self.device.post(first)
        self.assertEqual(self.device.post(first), a)
        self.assertEqual(self.device.commits, 1)
        with self.assertRaises(AdmissionDenied):
            self.device.post(command(Mode.MUSIC, BIND, 0, TX1))
        with self.assertRaises(AdmissionDenied):
            self.device.post(command(Mode.MONITORING, BIND, 0, TX2))
        with self.assertRaises(AdmissionDenied):
            self.device.post(command(Mode.MONITORING, BIND, 1, TX1))
        self.device.post(command(Mode.MUSIC, BIND, 1, TX2))
        with self.assertRaises(AdmissionDenied):
            self.device.post(first)
        self.assertEqual(self.device.commits, 2)

    def test_reboot_changes_boot_and_invalidates_old_transaction(self):
        self.device.post(command(Mode.MUSIC, BIND, 0, TX1))
        with self.assertRaises(ContractError):
            self.device.reboot(BIND.boot)
        self.device.reboot(NEWBOOT)
        self.assertEqual(self.device.commits, 1)  # cumulative lab counter
        self.assertIsNone(status(self.device.get_status())["last_tx"])
        with self.assertRaises(AdmissionDenied):
            self.device.post(command(Mode.MUSIC, BIND, 1, TX2))
        self.assertEqual(status(self.device.get_status())["revision"], 0)

    def test_revision_exhaustion_fail_closed(self):
        self.device.revision = MAX_REVISION
        with self.assertRaises(AdmissionDenied):
            self.device.post(command(Mode.MUSIC, BIND, MAX_REVISION, TX1))
        self.assertEqual(self.device.commits, 0)


class ControlSessionTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice(BIND)

    def test_success_all_modes_ack_then_independent_readback(self):
        for mode in Mode:
            with self.subTest(mode=mode):
                fake = FakeDevice(BIND)
                transport = LabTransport(fake)
                session = Session(BIND, transport)
                result = session.execute(mode, TX1)
                self.assertEqual(result.state, State.CONFIRMED)
                self.assertEqual(result.confirmed_scene, Scene.OFFLINE)
                self.assertEqual(result.reason, "ACK_AND_READBACK_SIMULATED")
                self.assertEqual(result.mode, mode)
                self.assertEqual(transport.posts, 1)
                self.assertEqual(fake.commits, 1)
                self.assertEqual(fake.gets, 3)  # capabilities/status/status

    def test_session_requires_explicit_new_intent_and_fails_duplicate(self):
        t = LabTransport(self.device)
        s = Session(BIND, t)
        self.assertEqual(s.execute(Mode.AUTO, TX1).state, State.CONFIRMED)
        with self.assertRaises(ContractError):
            s.execute(Mode.MUSIC, TX2)
        self.assertEqual(t.posts, 1)
        self.assertEqual(Session(BIND, t).execute(Mode.MUSIC, TX2).state,
                         State.CONFIRMED)
        self.assertEqual(self.device.commits, 2)

    def test_no_preflight_write_on_any_invalid_request(self):
        t = LabTransport(self.device)
        for bad in ("AUTO", None, False):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                Session(BIND, t).execute(bad, TX1)
        for bad in ("0" * 32, "x" * 32, "", None):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                Session(BIND, t).execute(Mode.AUTO, bad)
        self.assertEqual(t.posts, 0)
        self.assertEqual(self.device.gets, 0)

    def test_host_binding_mismatch_rejected_before_io(self):
        other = Binding("192.168.1.47", BIND.device, BIND.boot)
        with self.assertRaises(ContractError):
            Session(other, LabTransport(self.device))
        self.assertEqual(self.device.gets, 0)

    def test_wrong_device_or_boot_preflight_never_posts(self):
        for binding in (
            Binding(BIND.host, "1111111111111111", BIND.boot),
            Binding(BIND.host, BIND.device, NEWBOOT),
        ):
            with self.subTest(binding=binding):
                t = LabTransport(self.device)
                s = Session(binding, t)
                r = s.execute(Mode.AUTO, TX1)
                self.assertEqual(r.state, State.HOLD)
                self.assertEqual(t.posts, 0)
                self.assertEqual(self.device.commits, 0)

    def test_auth_failure_before_post_never_parses_body(self):
        self.device.auth = SimulatedAuth(False, False)
        t = LabTransport(self.device)
        r = Session(BIND, t).execute(Mode.MUSIC, TX1)
        self.assertEqual(r.state, State.HOLD)
        self.assertFalse(r.post_attempted)
        self.assertEqual(self.device.body_reads, 0)
        self.assertEqual(t.posts, 0)

    def test_all_get_failures_before_post_are_hold_no_retry(self):
        for fault in ("before_caps", "bad_caps", "before_status"):
            with self.subTest(fault=fault):
                t = Faults(self.device, at=fault)
                r = Session(BIND, t).execute(Mode.MONITORING, TX1)
                self.assertEqual((r.state, r.reason),
                                 (State.HOLD, "PREFLIGHT_UNKNOWN"))
                self.assertFalse(r.post_attempted)
                self.assertEqual(t.posts, 0)

    def test_precommit_rejection_is_distinct_from_network_401(self):
        t = LabTransport(self.device)
        self.device.revision = 4
        # Simulate a concurrent writer between preflight and POST.
        class Raced(LabTransport):
            def post_mode(self, frame):
                self.device.revision += 1
                return super().post_mode(frame)
        t = Raced(self.device)
        r = Session(BIND, t).execute(Mode.AUTO, TX1)
        self.assertEqual((r.state, r.reason, r.post_attempted),
                         (State.REJECTED, "LAB_PRECOMMIT_REFUSAL", True))
        self.assertEqual(self.device.commits, 0)
        self.assertEqual(t.posts, 1)

    def test_post_before_and_after_commit_uncertain_no_retry(self):
        for fault, expected_commits in (("before_post", 0), ("after_post", 1)):
            with self.subTest(fault=fault):
                fake = FakeDevice(BIND)
                t = Faults(fake, at=fault)
                session = Session(BIND, t)
                r = session.execute(Mode.CLOCK_WEATHER, TX1)
                self.assertEqual((r.state, r.post_attempted),
                                 (State.HOLD, True))
                self.assertEqual(t.posts, 1)
                self.assertEqual(fake.commits, expected_commits)
                with self.assertRaises(ContractError):
                    session.execute(Mode.CLOCK_WEATHER, TX1)
                # Read-only investigation is permitted but cannot retransmit.
                observation = session.read_only_reconcile()
                self.assertEqual(observation["revision"], expected_commits)
                self.assertEqual(t.posts, 1)

    def test_bad_ack_and_bad_readback_all_hold_after_one_post(self):
        for fault in ("after_post_get", "readback_false", "wrong_readback_boot",
                      "ack_modified", "ack_false", "ack_wrong_boot"):
            with self.subTest(fault=fault):
                fake = FakeDevice(BIND)
                t = Faults(fake, at=fault)
                s = Session(BIND, t)
                outcome = s.execute(Mode.MUSIC, TX1)
                self.assertEqual(outcome.state, State.HOLD)
                self.assertTrue(outcome.post_attempted)
                self.assertEqual(t.posts, 1)
                self.assertEqual(fake.commits, 1)

    def test_reboot_after_preflight_refused_no_retry(self):
        fake = FakeDevice(BIND)
        class BootRaced(LabTransport):
            def post_mode(self, frame):
                fake.reboot(NEWBOOT)
                return super().post_mode(frame)
        t = BootRaced(fake)
        result = Session(BIND, t).execute(Mode.AUTO, TX1)
        self.assertEqual(result.state, State.REJECTED)
        self.assertEqual(t.posts, 1)
        self.assertEqual(fake.commits, 0)

    def test_reconcile_read_only_never_marks_prior_hold_confirmed(self):
        fake = FakeDevice(BIND)
        t = Faults(fake, at="after_post")
        session = Session(BIND, t)
        r = session.execute(Mode.MUSIC, TX1)
        self.assertEqual(r.state, State.HOLD)
        report = session.read_only_reconcile()
        self.assertEqual(report["last_tx"], TX1)
        self.assertEqual(session.last_outcome.state, State.HOLD)
        self.assertEqual(t.posts, 1)
        fake.reboot(NEWBOOT)
        self.assertIsNone(session.read_only_reconcile())
        self.assertEqual(t.posts, 1)

    def test_revision_exhaustion_preflight_is_rejected_without_post(self):
        self.device.revision = MAX_REVISION
        t = LabTransport(self.device)
        r = Session(BIND, t).execute(Mode.AUTO, TX1)
        self.assertEqual((r.state, r.post_attempted),
                         (State.REJECTED, False))
        self.assertEqual(t.posts, 0)

    def test_reject_injected_real_network_adapter(self):
        class Dangerous:
            host = BIND.host
            def post_mode(self, frame):
                raise AssertionError("NEVER CALLED")
        with self.assertRaises(ContractError):
            Session(BIND, Dangerous())

    def test_no_socket_file_os_or_network_access_during_flow(self):
        fake = FakeDevice(BIND)
        transport = LabTransport(fake)
        with patch.object(socket, "socket", side_effect=AssertionError("network")), \
             patch.object(socket, "create_connection", side_effect=AssertionError("network")), \
             patch.object(builtins, "open", side_effect=AssertionError("filesystem")):
            res = Session(BIND, transport).execute(Mode.MONITORING, TX1)
        self.assertEqual(res.state, State.CONFIRMED)


if __name__ == "__main__":
    unittest.main()
