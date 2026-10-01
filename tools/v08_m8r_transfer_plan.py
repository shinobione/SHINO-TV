"""Finite qualification transfer, injected I/O only; never contacts a device itself.

Issue Begin + first tile before starting (two live challenges maximum). Reuse
necessary issue-control responses to verify the preceding packet. No extra
diagnostic snapshots, idle-slot waits, sleeps or body retries in the transaction.
Native Commit verification is mandatory after the socket closes; close alone is
not success. Telemetry checks read an already maintained observation snapshot.
"""
from dataclasses import dataclass
import json
import unittest

DEADLINE_MS = 8000  # Native deadline unchanged; client uses an earlier boundary.
REMAINING_PACKET_RESERVE_MS = 750


class StopTransfer(RuntimeError):
    pass


def bounded_control(request, renew):
    """Retry only explicit 401; every challenge replaces cached auth state.

    request returns (status, sanitized result). renew consumes the challenge
    internally; neither headers nor secrets are returned or logged by this plan.
    A timeout or other status never causes a write/body retry.
    """
    for _ in range(4):
        status, result = request()
        if status == 200:
            return result
        if status != 401:
            raise StopTransfer('CONTROL_HTTP_FAILURE')
        renew()
    raise StopTransfer('CONTROL_HTTP_401_BOUND')


def transfer(packets, *, issue, send_once, verify_previous, terminal, check, now):
    """Run one complete signed transaction; exceptions require bounded cleanup.

    Calls are injectable so this exact plan is tested without network/device I/O.
    The caller supplies tx-specific authenticated Abort/expiry cleanup on Stop.
    send_once must enforce its existing per-request timeout and never retry.
    """
    if len(packets) < 2 or packets[0]['op'] != 1 or packets[-1]['op'] != 3:
        raise ValueError('Complete Begin/tiles/Commit required')
    check()
    issue(packets[0])
    issue(packets[1])
    check()
    start = now()  # Before Begin transmission: conservative native-time bound.
    send_once(packets[0])
    previous = packets[0]
    for index, packet in enumerate(packets[1:], 1):
        check()
        if now() - start + REMAINING_PACKET_RESERVE_MS > DEADLINE_MS:
            raise StopTransfer('CLIENT_DEADLINE_RESERVE')
        if index > 1:
            control = issue(packet)
            verify_previous(control, previous, index)
            check()
            if now() - start + REMAINING_PACKET_RESERVE_MS > DEADLINE_MS:
                raise StopTransfer('CLIENT_DEADLINE_RESERVE')
        send_once(packet)
        previous = packet
    elapsed = now() - start
    if elapsed >= DEADLINE_MS:
        raise StopTransfer('CLIENT_DEADLINE')
    check()
    terminal(previous)  # Native result/resources after Commit, outside deadline.
    return elapsed


@dataclass(frozen=True)
class Costs:
    name: str
    media_transport_ms: int
    media_jitter_ms: int
    control_ms: int
    control_jitter_ms: int
    explicit_401_roundtrips: int = 0


PROFILES = (
    # Historical closed sockets: media 625-672 ms (48:640-657), protected
    # control 16-94 ms. Quiet 660/95 brackets 48; stress 715/100 brackets both.
    Costs('quiet_48_bound', 35, 30, 40, 55),
    Costs('one_Digest_interaction', 35, 30, 40, 55, 2),
    Costs('transport_stress', 70, 50, 60, 40, 2),
)


def simulate(width, cost):
    tiles = width * width * 2 // 512
    # Begin is included conservatively; native timer starts after its validation.
    media = 595 + cost.media_transport_ms + cost.media_jitter_ms
    controls = max(0, tiles - 1) + 1 if tiles else 0
    active = (tiles + 2) * media + controls * (cost.control_ms + cost.control_jitter_ms)
    active += cost.explicit_401_roundtrips * (cost.control_ms + cost.control_jitter_ms)
    post_begin = active - media
    return {'width': width, 'profile': cost.name, 'ecdsa_ms_each': 595,
            'conservative_begin_send_to_commit_ms': active,
            'post_begin_close_to_commit_ms': post_begin,
            'conservative_margin_ms': DEADLINE_MS - active,
            'post_begin_margin_ms': DEADLINE_MS - post_begin,
            'reserve_gate': active + REMAINING_PACKET_RESERVE_MS < DEADLINE_MS}


class PlanTests(unittest.TestCase):
    def test_finite_plan_has_two_preissued_no_waits_or_body_retries(self):
        events = []; clock = [0]
        packets = [{'op': 1}, *[{'op': 2} for _ in range(4)], {'op': 3}]
        def issue(p):
            events.append(('issue', p['op'])); clock[0] += 95; return {'ok': True}
        def send(p):
            events.append(('send', p['op'])); clock[0] += 660
        def terminal(p):
            events.append(('terminal', p['op'])); clock[0] += 2000
        elapsed = transfer(packets, issue=issue, send_once=send,
            verify_previous=lambda q,p,count: self.assertTrue(q['ok']),
            terminal=terminal, check=lambda: None, now=lambda: clock[0])
        self.assertEqual(events[:3], [('issue',1),('issue',2),('send',1)])
        self.assertEqual(sum(e[0]=='issue' for e in events), len(packets))
        self.assertEqual(sum(e[0]=='send' for e in events), len(packets))
        self.assertEqual(elapsed, simulate(32, PROFILES[0])['conservative_begin_send_to_commit_ms'])
        self.assertEqual(events[-1], ('terminal',3))

    def test_every_401_refreshes_without_idle_slot(self):
        statuses = iter([401,401,200]); renewals=[]
        self.assertEqual(bounded_control(lambda:(next(statuses),'safe'),lambda:renewals.append(1)), 'safe')
        self.assertEqual(len(renewals), 2)
        with self.assertRaisesRegex(StopTransfer,'401_BOUND'):
            bounded_control(lambda:(401,None),lambda:None)

    def test_network_failure_is_not_retried(self):
        calls=[]
        def failing():
            calls.append(1); raise TimeoutError('sanitized timeout')
        with self.assertRaises(TimeoutError): bounded_control(failing,lambda:None)
        self.assertEqual(calls,[1])

    def test_telemetry_pause_stops_before_more_bytes(self):
        sent=[];checks=[0]
        def check():
            checks[0]+=1
            if checks[0]==3: raise StopTransfer('TELEMETRY_STALE')
        with self.assertRaisesRegex(StopTransfer,'TELEMETRY_STALE'):
            transfer([{'op':1},{'op':2},{'op':3}],issue=lambda p:None,
                send_once=lambda p:sent.append(p['op']),verify_previous=lambda q,p,count:None,
                terminal=lambda p:None,check=check,now=lambda:0)
        self.assertEqual(sent,[1])

    def test_deadline_reserve_stops_without_last_body(self):
        clock=[0];sent=[]
        def send(p): clock[0]+=7400;sent.append(p['op'])
        with self.assertRaisesRegex(StopTransfer,'DEADLINE_RESERVE'):
            transfer([{'op':1},{'op':3}],issue=lambda p:None,send_once=send,
                verify_previous=lambda q,p,count:None,terminal=lambda p:None,
                check=lambda:None,now=lambda:clock[0])
        self.assertEqual(sent,[1])

    def test_48_remains_experimental_32_fallback(self):
        self.assertTrue(all(simulate(32,p)['reserve_gate'] for p in PROFILES))
        self.assertFalse(all(simulate(48,p)['reserve_gate'] for p in PROFILES))


def report():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PlanTests)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    return {'tests':result.testsRun,'failed':len(result.failures)+len(result.errors),
            'deadline_ms':DEADLINE_MS,'reserve_ms':REMAINING_PACKET_RESERVE_MS,
            'timing_kind':'bounded_model_not_physical_measurement',
            'profiles':[simulate(w,p) for w in (32,48) for p in PROFILES],
            '48_status':'EXPERIMENTAL__TIMING_MARGIN_NOT_DEMONSTRATED',
            '32_status':'PHYSICALLY_VALIDATED_FALLBACK',
            'device_contacts':0,'device_writes':0}


if __name__ == '__main__': print(json.dumps(report(),indent=2))
